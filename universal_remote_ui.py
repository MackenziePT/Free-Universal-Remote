"""Universal Remote Windows application. First-party tkinter UI, no remote-control app dependency."""
from __future__ import annotations

import json
import os
import sys
import queue
import threading
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from http.client import HTTPConnection, HTTPException

from native_jobs import TaskManager
from remote_core import grant_allowed, load_config
from public_runtime import get_private_powershell_setup_path, install_private_powershell
from dependency_preflight import check_dependencies, has_missing_required_dependencies
from help_center import diagnose, friendly_text, guidance, issue_for_exception, safe_diagnostic_report
from guided_steps import build_steps, next_action, completed_local_count
from connection_doctor import check_current_local_engine

PRODUCT_VERSION = "1.0.0-rc5.1-dev"
BG = "#0A0F1D"
SIDEBAR = "#10182A"
PANEL = "#151F32"
PANEL_ALT = "#1B2940"
TEXT = "#EAF0FA"
MUTED = "#91A0B6"
ACCENT = "#4BCAFF"
GREEN = "#58DEA7"
RED = "#F27584"
STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UniversalRemote"
HERE = Path(__file__).resolve().parent


def local_mcp_config() -> dict:
    """A safe client-side stdio snippet, never credentials or private file paths."""
    if getattr(sys, "frozen", False):
        location = Path(sys.executable).resolve().parent.parent / "Agent" / "UniversalRemoteAgent-Preview.exe"
        if not location.is_file():
            raise FileNotFoundError("Agente MCP autónomo não encontrado. Repara a instalação.")
        command, args = str(location), []
    else:
        location = HERE / "public_agent.py"
        if not location.is_file():
            raise FileNotFoundError("public_agent.py não encontrado na árvore de desenvolvimento")
        command, args = sys.executable, [str(location)]
    return {"mcpServers": {"universal-remote": {"command": command, "args": args}}}


def local_agent_available() -> bool:
    try:
        local_mcp_config()
        return True
    except (OSError, ValueError):
        return False


def read_status():
    connection = None
    try:
        # Explicit loopback HTTP avoids proxy handlers, remote hosts and URL schemes.
        connection = HTTPConnection("127.0.0.1", 8080, timeout=0.6)
        connection.request("GET", "/readyz")
        response = connection.getresponse()
        return response.status == 200 and response.read(32).strip() == b"ready"
    except (OSError, HTTPException, ValueError):
        return False
    finally:
        if connection is not None:
            connection.close()


def grant_local(config, capabilities, minutes):
    """Only called after a visible, locally accepted GUI confirmation."""
    if minutes not in (15, 60):
        raise ValueError("Unsupported duration")
    caps = sorted(set(capabilities))
    if not caps or any(x not in {"writes", "shell", "screen", "input"} for x in caps):
        raise ValueError("Invalid capability selection")
    for name in caps:
        if not getattr(config, "enable_" + name):
            raise ValueError("Capability is not enabled in local policy: " + name)
    STATE.mkdir(parents=True, exist_ok=True)
    target = Path(config.grants_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    expires = int(time.time()) + 60 * minutes
    raw = json.dumps({"expires_at": expires, "capabilities": caps}, separators=(",", ":"))
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                     dir=target.parent, prefix=".consent-",
                                     suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return caps, expires


def revoke_local(config=None):
    target = Path(config.grants_path) if config is not None else STATE / "grants.json"
    target.unlink(missing_ok=True)


def emergency_revoke_and_stop(config, jobs) -> dict:
    """Locally revoke new calls, then attempt to stop every registered active job.

    This is best effort. In-flight remote requests and untracked child processes
    are not guaranteed to terminate; report inability to verify instead of
    displaying a misleading success message.
    """
    revoke_local(config)
    stopped = []
    failures = {}
    try:
        for _ in range(2):
            running = jobs.running_jobs()
            if not running:
                break
            for task in running:
                job_id = task["job_id"]
                try:
                    status = jobs.stop(job_id)["status"]
                    if status in ("stopped", "exited", "exited_unobserved"):
                        if job_id not in stopped:
                            stopped.append(job_id)
                        failures.pop(job_id, None)
                    else:
                        failures[job_id] = "state " + str(status)
                except Exception as exc:
                    failures[job_id] = type(exc).__name__
        remaining = [task["job_id"] for task in jobs.running_jobs()]
    except Exception as exc:
        return {"revoked": True, "stopped": stopped, "remaining": [],
                "errors": ["Cannot verify active task inventory: " + type(exc).__name__]}
    return {"revoked": True, "stopped": stopped, "remaining": remaining,
            "errors": [job_id + ": " + failures.get(job_id, "still running")
                       for job_id in remaining]}


class UniversalRemoteApp(tk.Tk):
    def __init__(self, start_page="Início"):
        super().__init__()
        self.title("Universal Remote  •  Aplicação para IA")
        self.geometry("1040x690")
        self.minsize(840, 570)
        self.configure(bg=BG)
        self.config_data = load_config()
        self.jobs = TaskManager(STATE / "jobs")
        self.nav_buttons = {}
        self._pwsh_results = queue.Queue()
        self._pwsh_worker = None
        self._engine_results = queue.Queue()
        self._engine_worker = None
        self._engine_status = "A verificação local vai começar automaticamente."
        self._engine_result_code = None
        self.page = ""
        self._make_shell()
        self.protocol("WM_DELETE_WINDOW", self._shutdown)
        self.show(start_page)
        self.after(1100, self._test_engine_local)
        self.after(2800, self._heartbeat)

    def _shutdown(self):
        """Stop local monitoring on exit; persistent tasks remain controlled by the task manager."""
        try:
            self.jobs.close()
        finally:
            self.destroy()

    def _show_dependency_status(self):
        """Explain prerequisites in plain language. Never installs anything silently."""
        results=check_dependencies()
        text="\n\n".join(
            ("✓ " if row.ok else "⚠ ") + row.title + "\n" + row.detail
            for row in results
        )
        if has_missing_required_dependencies(results):
            self.show("Ajuda")
        else:
            messagebox.showinfo("Instalação verificada",
                                text+"\n\nNão precisas de instalar Python ou bibliotecas.",
                                parent=self)

    def _make_shell(self):
        top = tk.Frame(self, bg=BG, height=83)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="◈   UNIVERSAL REMOTE", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 19)).pack(side="left", padx=30, pady=24)
        self.live = tk.Label(top, text="A verificar...", bg=BG, fg=MUTED,
                             font=("Segoe UI", 10))
        self.live.pack(side="right", padx=32)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=SIDEBAR, width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="PAINEL DE CONTROLO", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22, pady=(27, 16))
        for name, symbol in (("Início", "⌂"), ("Guia", "✓"), ("Conexões", "◇"),
                             ("Acesso", "⛨"), ("Tarefas", "▣"),
                             ("Janelas", "▦"), ("Atividade", "≡"), ("Ajuda", "?")):
            button = tk.Button(side, text=f" {symbol}    {name}", anchor="w",
                               bg=SIDEBAR, fg=TEXT, activebackground=PANEL_ALT,
                               activeforeground=TEXT, relief="flat", border=0,
                               padx=18, pady=12, font=("Segoe UI", 12),
                               command=lambda n=name: self.show(n))
            button.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[name] = button
        tk.Label(side, text="RC5  ·  INDEPENDENTE\nMCP aberto  ·  Windows",
                 bg=SIDEBAR, fg=MUTED, justify="left",
                 font=("Segoe UI", 9)).pack(side="bottom", anchor="w", padx=24, pady=25)
        self.content_host = tk.Frame(body, bg=BG)
        self.content_host.pack(side="left", fill="both", expand=True, padx=30, pady=(12, 20))
        self.content = self.content_host
        self._content_canvas = None
        self.bind("<MouseWheel>", self._on_main_mousewheel, add="+")
        self.bind("<Prior>", lambda event: self._scroll_main_page(-1), add="+")
        self.bind("<Next>", lambda event: self._scroll_main_page(1), add="+")

        footer = tk.Frame(self, bg=BG, height=34)
        footer.pack(fill="x")
        tk.Label(footer, text="Controlo local  ·  Liga qualquer IA compatível  ·  Sem Desktop Commander",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=28)

    def _heartbeat(self):
        if not self.winfo_exists():
            return
        # Do not confuse a foreign listener on port 8080 (e.g. a previous
        # installed release) with this product's actual authenticated pairing.
        local = local_agent_available()
        if not local:
            label, tint = "●  Ligação local: reparação necessária", RED
        else:
            label, tint = "●  Motor local instalado · ligação remota por confirmar", GREEN
        self.live.config(text=label, fg=tint)
        if self.page == "Início":
            self._overview_status()
        self.after(5000, self._heartbeat)

    def _clear(self):
        for child in self.content_host.winfo_children():
            child.destroy()
        self.content = self.content_host
        self._content_canvas = None

    def _scroll_main_page(self, direction: int):
        canvas = self._content_canvas
        if canvas is not None and canvas.winfo_exists():
            canvas.yview_scroll(direction, "units")

    def _on_main_mousewheel(self, event):
        if self._content_canvas is not None and self._content_canvas.winfo_exists():
            delta = getattr(event, "delta", 0)
            if delta:
                self._scroll_main_page(-1 if delta > 0 else 1)

    def _prepare_scrollable_main_page(self):
        """Static content remains reachable at high DPI; sidebar stays fixed."""
        canvas = tk.Canvas(self.content_host, bg=BG, highlightthickness=0,
                           borderwidth=0)
        scroll = tk.Scrollbar(self.content_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(window, width=event.width))
        self.content = inner
        self._content_canvas = canvas

    def _heading(self, title, subtitle):
        tk.Label(self.content, text=title, bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 24)).pack(anchor="w", pady=(8, 1))
        tk.Label(self.content, text=subtitle, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), wraplength=710, justify="left").pack(anchor="w", pady=(0, 22))

    def _card(self, parent=None, padding=17):
        frame = tk.Frame(parent or self.content, bg=PANEL, padx=padding, pady=padding,
                         highlightthickness=1, highlightbackground="#25354D")
        return frame

    @staticmethod
    def _label(parent, text, size=11, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI Semibold" if bold else "Segoe UI", size),
                        justify="left", anchor="w", **kwargs)

    def _button(self, parent, text, command, accent=False, danger=False):
        color = RED if danger else (ACCENT if accent else PANEL_ALT)
        fg = BG if accent else TEXT
        return tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                         activebackground=color, activeforeground=fg,
                         relief="flat", padx=16, pady=10,
                         cursor="hand2", font=("Segoe UI Semibold", 10))

    def show(self, page):
        self.page = page
        for name, button in self.nav_buttons.items():
            button.configure(bg=PANEL_ALT if name == page else SIDEBAR,
                             fg=ACCENT if name == page else TEXT)
        self._clear()
        if page in {"Início", "Guia", "Conexões", "Acesso", "Ajuda"}:
            self._prepare_scrollable_main_page()
        {"Início": self._home, "Guia": self._guide, "Conexões": self._connections,
         "Acesso": self._access, "Tarefas": self._tasks,
         "Janelas": self._windows, "Atividade": self._activity,
         "Ajuda": self._help}[page]()

    def _home(self):
        self._heading("A tua IA, no teu computador.",
                      "Trabalho direto, ferramentas próprias e acesso controlado por ti.")
        card = self._card()
        card.pack(fill="x", pady=(0, 14))
        self.status_detail = self._label(card, "", 13, GREEN, bold=True)
        self.status_detail.pack(anchor="w")
        self._label(card, "Universal Remote  " + PRODUCT_VERSION + "   •   Windows local + MCP",
                    10, MUTED).pack(anchor="w", pady=(7, 0))
        self._overview_status()
        steps = build_steps(check_dependencies(), local_agent_available(),
                            engine_health=self._engine_result_code)
        suggested = next_action(steps)
        recommendation = self._card()
        recommendation.pack(fill="x", pady=(0, 13))
        self._label(recommendation,"O teu próximo passo",12,ACCENT,bold=True).pack(anchor="w")
        self._label(recommendation,suggested.title,14,TEXT,bold=True).pack(anchor="w",pady=(6,3))
        self._label(recommendation,suggested.summary,10,MUTED,wraplength=630).pack(anchor="w",pady=(0,9))
        self._button(recommendation,"Começar com o guia passo a passo",
                     lambda:self.show("Guia"),accent=True).pack(anchor="w")
        panels = tk.Frame(self.content, bg=BG)
        panels.pack(fill="x", pady=(5, 20))
        for name, detail in (
            ("Conexões", "ChatGPT e outras IAs por MCP"),
            ("Acesso", "Permissões e revogação imediata"),
            ("Tarefas", "Execução longa, logs e controlo"),
        ):
            c = self._card(panels, padding=14)
            c.pack(side="left", fill="both", expand=True, padx=(0, 9))
            self._label(c, name, 12, TEXT, bold=True).pack(anchor="w")
            self._label(c, detail, 9, MUTED, wraplength=155).pack(anchor="w", pady=(6, 8))
            self._button(c, "Abrir", lambda n=name: self.show(n)).pack(anchor="w")
        self._button(self.content, "Ajuda e resolução de problemas",
                     lambda: self.show("Ajuda"), accent=True).pack(anchor="w", pady=7)
        self._button(self.content, "Verificar componentes instalados",
                     self._show_dependency_status).pack(anchor="w", pady=7)
        self._label(self.content,
                    "Python e bibliotecas estão incluídos no programa; não precisas de instalá-los.",
                    10, MUTED, wraplength=660).pack(anchor="w", pady=4)

    def _overview_status(self):
        if not hasattr(self, "status_detail") or not self.status_detail.winfo_exists():
            return
        grants = [x for x in ("writes", "shell", "screen", "input") if grant_allowed(self.config_data, x)]
        suffix = "  ·  " + (", ".join(grants) if grants else "Acesso privilegiado revogado")
        local = local_agent_available()
        self.status_detail.configure(
            text=("●  Motor MCP local disponível" if local else "●  Motor de ligação em falta")
                 + " · ligação remota por confirmar" + suffix,
            fg=GREEN if local else RED)

    def _guide(self):
        """A guided, read-only start path; remote connectivity is never guessed."""
        self._heading("Vamos pôr tudo a funcionar",
                      "Segue os passos por ordem. Explico o que falta e levo-te ao sítio certo.")
        steps = build_steps(check_dependencies(), local_agent_available(),
                            engine_health=self._engine_result_code)
        state = self._card()
        state.pack(fill="x",pady=(0,13))
        self._label(state,"Preparação no teu computador",13,TEXT,bold=True).pack(anchor="w")
        local_done=completed_local_count(steps)
        self._label(state,f"{local_done} de 2 verificações locais concluídas automaticamente.",
                    11,GREEN if local_done==2 else MUTED,wraplength=625).pack(anchor="w",pady=(7,7))
        self._label(state,"A ligação remota ao ChatGPT é verificada separadamente. "
                    "Não damos acesso sem tua autorização.",
                    10,MUTED,wraplength=625).pack(anchor="w")
        self._engine_label=self._label(state,self._engine_status,10,ACCENT,wraplength=625)
        self._engine_label.pack(anchor="w",pady=(8,7))
        self._button(state,"Testar o motor local agora",self._test_engine_local).pack(anchor="w")
        next_step=next_action(steps)
        for item in steps:
            card=self._card()
            card.pack(fill="x",pady=(0,12))
            symbol = "✓" if item.state=="done" else ("!" if item.state=="action" else "→")
            fg=GREEN if item.state=="done" else (RED if item.state=="action" else ACCENT)
            self._label(card,f"{symbol}  PASSO {item.number} — {item.title}",
                        13,fg,bold=True).pack(anchor="w")
            self._label(card,item.summary,11,TEXT,wraplength=625).pack(anchor="w",pady=(8,4))
            self._label(card,item.detail,10,MUTED,wraplength=625).pack(anchor="w",pady=(0,12))
            if item.number == next_step.number:
                self._label(card,"Sugerido agora",9,ACCENT,bold=True).pack(anchor="w",pady=(0,6))
            self._button(card,item.button,
                         lambda target=item.destination:self.show(target),
                         accent=(item.number==next_step.number)).pack(anchor="w")
        extra=self._card()
        extra.pack(fill="x",pady=(0,15))
        self._label(extra,"E se eu não perceber alguma coisa?",12,TEXT,bold=True).pack(anchor="w")
        self._label(extra,"Abre a Ajuda. Encontrarás explicações simples e opções de reparação. "
                    "As funções avançadas são opcionais e ficam separadas.",
                    10,MUTED,wraplength=630).pack(anchor="w",pady=(5,10))
        self._button(extra,"Preciso de ajuda",lambda:self.show("Ajuda")).pack(anchor="w")

    def _connections(self):
        self._heading("Conexões", "Um único motor; vários agentes de IA compatíveis com MCP.")
        box = self._card()
        box.pack(fill="x", pady=(0, 14))
        self._label(box, "ChatGPT  •  Túnel privado", 14, TEXT, bold=True).pack(anchor="w")
        self._label(box,"Para ligar: 1. Abre o assistente abaixo e configura o teu túnel "
                    "privado. 2. No ChatGPT, abre Plugins → + → Adicionar servidor MCP "
                    "personalizado → Túnel. 3. Confirma a autorização da conta. "
                    "4. Pede ao ChatGPT para verificar a comunicação.",
                    10,TEXT,wraplength=630).pack(anchor="w",pady=(9,6))
        from tunnel_manager import is_provisioned, read_status
        tunnel_state=STATE/"tunnel"
        info=read_status(tunnel_state)
        if is_provisioned(tunnel_state):
            state_text=info["detail"]
            if info["code"]=="UNKNOWN":
                state_text="Túnel configurado, ainda sem atividade local confirmada."
        else:
            state_text="Ainda não configurado. O assistente pede apenas os dados oficiais do túnel."
        self._label(box,"Estado do túnel: "+state_text,10,ACCENT,
                    wraplength=630).pack(anchor="w",pady=(7,7))
        self._button(box,"Ligar ao ChatGPT — assistente guiado",
                     self._open_tunnel_setup,accent=True).pack(anchor="w",pady=(2,9))
        self._button(box,"Copiar link de abertura rápida",
                     self._copy_connect_link).pack(anchor="w",pady=(0,9))
        self._button(box,"Abrir ChatGPT (site oficial)",self._open_chatgpt).pack(anchor="w",pady=(0,9))
        self._button(box,"Testar o motor local",self._test_engine_local).pack(anchor="w",pady=(0,9))
        self._label(box,self._engine_status,10,MUTED,wraplength=630).pack(anchor="w",pady=(0,6))
        self._button(box,"Voltar ao guia",lambda:self.show("Guia")).pack(anchor="w",pady=(0,10))
        self._label(box, "A ligação remota não é ativada automaticamente. Para ChatGPT remoto, "
                    "é necessário emparelhar uma conta e configurar um transporte privado autenticado. "
                    "O estado HTTP local não confirma que um cliente remoto está ligado.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=8)
        self._button(box, "Gerir dispositivos emparelhados", self._manage_pairing).pack(anchor="w", pady=(5,9))
        box = self._card()
        box.pack(fill="x")
        self._label(box, "Outras IAs  •  MCP local padrão", 14, TEXT, bold=True).pack(anchor="w")
        self._label(box, "Copia a configuração local para um cliente MCP compatível. "
                    "Não contém palavras-passe, chaves ou tokens.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(8, 12))
        controls = tk.Frame(box,bg=PANEL)
        controls.pack(anchor="w",fill="x")
        self._button(controls, "Copiar configuração MCP", self._copy_config, accent=True).pack(side="left",padx=(0,9))
        self._button(controls, "Verificar instalação", self._show_dependency_status).pack(side="left")
        self._label(box, "Para serviços de IA remotos é necessário um transporte autenticado "
                    "compatível. Não se expõem portas do computador à Internet.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(16, 0))
        extra = self._card()
        extra.pack(fill="x", pady=(14,0))
        self._label(extra, "PowerShell  ·  Ferramentas de diagnóstico", 13, TEXT, bold=True).pack(anchor="w")
        self._label(extra, "A aplicação funciona sem PowerShell pré-instalado. "
                    "Para ferramentas de diagnóstico e terminal PowerShell, podes obter "
                    "automaticamente a versão estável mais recente da Microsoft. "
                    "A cópia fica privada na aplicação; não altera o PowerShell do Windows.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(7, 11))
        self._button(extra, "Verificar ou atualizar PowerShell", self._prepare_powershell).pack(anchor="w")
        self._pwsh_status = self._label(extra, "", 9, MUTED)
        self._pwsh_status.pack(anchor="w", pady=(8,0))

    def _open_tunnel_setup(self):
        try:
            from tunnel_setup_ui import show_tunnel_setup
            if getattr(sys,"frozen",False):
                root=Path(sys.executable).resolve().parent.parent
                agent=root/"Agent"/"UniversalRemoteAgent-Preview.exe"
            else:
                root=HERE
                agent=root/"evidence"/"qa"/"public-portable-prototype"/"UniversalRemoteAgent-Preview"/"UniversalRemoteAgent-Preview.exe"
            show_tunnel_setup(self,state=STATE/"tunnel",agent=agent,
                              client=root/"bin"/"tunnel-client.exe",
                              sidecar=(root/"Tunnel"/"UniversalRemoteTunnel-Preview.exe"
                                       if getattr(sys,"frozen",False) else
                                       root/"evidence"/"qa"/"public-portable-prototype"/"UniversalRemoteTunnel-Preview"/"UniversalRemoteTunnel-Preview.exe"))
        except (OSError,ValueError):
            self._notify_error(RuntimeError("tunnel setup unavailable"),context="pairing")

    def _copy_connect_link(self):
        """Share the same safe URI handled by the signed/preview installer."""
        uri="universal-remote://connect"
        self.clipboard_clear()
        self.clipboard_append(uri)
        messagebox.showinfo("Link copiado",
            "Cola universal-remote://connect na barra do Explorador ou em "
            "Win + R, depois de instalares o Universal Remote. "
            "A autorização inicial continua sob o teu controlo.",
            parent=self)

    def _open_chatgpt(self):
        # The official website is opened only after a deliberate click.
        # This does not create, authorize or claim a ChatGPT MCP connection.
        import webbrowser
        webbrowser.open("https://chatgpt.com/")

    def _test_engine_local(self):
        """Non-blocking, read-only local checks; no Internet or privilege changes."""
        if self._engine_worker is not None and self._engine_worker.is_alive():
            return
        self._engine_status="A testar o motor local, sem alterar configurações..."
        self._update_engine_label()
        def worker():
            try:
                result=check_current_local_engine()
                self._engine_results.put(result)
            except Exception:
                # No exception arguments or paths in UI/log output.
                from connection_doctor import EngineResult
                self._engine_results.put(EngineResult(
                    "ERROR","Não foi possível verificar o motor",
                    "Abre a Ajuda e tenta novamente. Não é preciso usar comandos."))
        self._engine_worker=threading.Thread(target=worker,daemon=True,name="urm-local-check")
        self._engine_worker.start()
        self.after(250,self._poll_engine_check)

    def _update_engine_label(self):
        label=getattr(self,"_engine_label",None)
        if label is not None and label.winfo_exists():
            label.configure(text=self._engine_status)

    def _poll_engine_check(self):
        if not self.winfo_exists():
            return
        try:
            result=self._engine_results.get_nowait()
        except queue.Empty:
            self.after(250,self._poll_engine_check)
            return
        self._engine_status=result.title+". "+result.detail
        self._engine_result_code=result.code
        self._update_engine_label()
        if result.code != "READY":
            codes={"SETUP":"SETUP_INCOMPLETE","MISSING":"AGENT_MISSING",
                   "BLOCKED":"SECURITY_BLOCKED","TIMEOUT":"UNKNOWN_ERROR",
                   "ERROR":"UNKNOWN_ERROR"}
            self._last_issue=guidance(codes.get(result.code,"UNKNOWN_ERROR"))
        if self.page in {"Conexões","Guia","Início"}:
            self.show(self.page)
        # An authenticated remote ChatGPT session is never inferred here.

    def _prepare_powershell(self, approved=False):
        if self._pwsh_worker is not None and self._pwsh_worker.is_alive():
            return
        if not approved and not messagebox.askyesno("PowerShell da Microsoft",
              "Queres verificar e, se necessário, descarregar a versão estável mais recente do PowerShell?\n\n"
              "O download é feito do repositório oficial Microsoft e a assinatura e SHA-256 "
              "são verificadas. Não altera o PowerShell instalado globalmente."):
            return
        if hasattr(self, "_pwsh_status") and self._pwsh_status.winfo_exists():
            self._pwsh_status.configure(text="A verificar a versão oficial e a assinatura Microsoft...")
        def background():
            try:
                location = install_private_powershell()
                self._pwsh_results.put(("ok",str(location)))
            except Exception as ex:
                self._pwsh_results.put(("error",str(ex)))
        self._pwsh_worker=threading.Thread(target=background,daemon=True,name="urm-pwsh-provision")
        self._pwsh_worker.start()
        self.after(400,self._poll_powershell)

    def _poll_powershell(self):
        try:
            state,detail=self._pwsh_results.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(400,self._poll_powershell)
            return
        if state=="ok":
            messagebox.showinfo("PowerShell pronto",
                                "PowerShell verificado e disponível para o Universal Remote.\n"+detail)
        else:
            self._notify_error(RuntimeError("optional component"), context="powershell")
        if self.winfo_exists() and self.page=="Conexões":
            self.show("Conexões")

    def _manage_pairing(self):
        try:
            from pairing_management_ui import show_pairing_window
            show_pairing_window(self, STATE / "security")
        except Exception as exc:
            self._notify_error(exc, context="pairing")

    def _copy_config(self):
        try:
            config = local_mcp_config()
            self.clipboard_clear()
            self.clipboard_append(json.dumps(config, indent=2, ensure_ascii=False))
        except Exception as exc:
            self._notify_error(exc, context="installation")
            return
        messagebox.showinfo("Configuração copiada",
                            "Configuração MCP local copiada. Não contém credenciais. "
                            "Importa-a nas definições de um cliente MCP compatível.")

    def _notify_error(self, error: BaseException, context: str = ""):
        """Friendly, actionable problem dialog with no raw paths or secret data."""
        item=issue_for_exception(error,context=context)
        self._last_issue=item
        message=friendly_text(item)+"\n\nQueres abrir a Ajuda para veres os próximos passos?"
        if messagebox.askyesno(item.title,message,parent=self,icon="warning"):
            self.show("Ajuda")

    def _retry_help(self):
        self._last_issue=None
        self.show("Ajuda")

    def _copy_help_report(self):
        summary=safe_diagnostic_report(getattr(self,"_help_issues",()))
        self.clipboard_clear()
        self.clipboard_append(summary)
        messagebox.showinfo("Resumo copiado",
                            "Copiei apenas os códigos dos problemas, sem palavras-passe, "
                            "ficheiros pessoais nem chaves.",parent=self)

    def _help(self):
        """Visible support with clear instructions; diagnosis itself never changes Windows."""
        self._heading("Ajuda e resolução de problemas",
                      "Explicações simples e passos seguros. Não precisas de usar comandos.")
        checks=check_dependencies()
        detected=diagnose(checks,local_agent_available())
        previous=getattr(self,"_last_issue",None)
        self._help_issues=((previous,)+detected if previous is not None and
                           previous.code not in {x.code for x in detected} else detected)
        actions=self._card()
        actions.pack(fill="x",pady=(0,13))
        self._label(actions,"O que podes fazer agora",13,TEXT,bold=True).pack(anchor="w")
        self._label(actions,"Verificar novamente não altera ficheiros nem permissões.",
                    10,MUTED,wraplength=620).pack(anchor="w",pady=(5,12))
        bar=tk.Frame(actions,bg=PANEL)
        bar.pack(fill="x")
        self._button(bar,"Verificar novamente",self._retry_help,
                     accent=True).pack(side="left",padx=(0,8))
        self._button(bar,"Copiar resumo sem dados pessoais",
                     self._copy_help_report).pack(side="left")
        for item in self._help_issues:
            box=self._card()
            box.pack(fill="x",pady=(0,12))
            color=RED if item.severity=="error" else (GREEN if item.code=="LOCAL_OK" else ACCENT)
            self._label(box,item.title,14,color,bold=True).pack(anchor="w",pady=(0,7))
            self._label(box,item.explanation,10,TEXT,wraplength=630).pack(anchor="w",pady=(0,11))
            self._label(box,"Como resolver:",10,MUTED,bold=True).pack(anchor="w",pady=(0,5))
            for n,step in enumerate(item.steps,1):
                self._label(box,f"{n}. {step}",10,TEXT,wraplength=630).pack(
                    anchor="w",pady=(0,5))
            if item.page and item.page!="Ajuda":
                self._button(box,item.button or "Abrir",
                             lambda page=item.page:self.show(page)).pack(anchor="w",pady=(7,0))
        note=self._card()
        note.pack(fill="x",pady=(0,12))
        self._label(note,"Se aparecer um aviso de segurança",12,TEXT,bold=True).pack(anchor="w")
        self._label(note,"Não desatives o Defender, a firewall ou o antivírus. "
                    "Confirma o editor e a origem do ficheiro. Se não os reconheces, cancela. "
                    "A verificação local não confirma o emparelhamento remoto.",
                    10,MUTED,wraplength=630).pack(anchor="w",pady=(7,0))

    def _access(self):
        self._heading("Acesso e permissões", "Apenas tu decides o que uma IA pode fazer neste computador.")
        c = self._card()
        c.pack(fill="x", pady=(0, 14))
        current = [n for n in ("writes", "shell", "screen", "input") if grant_allowed(self.config_data, n)]
        self._label(c, "Sessão atual: " + (", ".join(current) if current else "sem acesso privilegiado"),
                    12, GREEN if current else MUTED, bold=True).pack(anchor="w", pady=(0, 12))
        self.mode = tk.StringVar(value="Desenvolvimento")
        modes = {
            "Ficheiros": "Criar, copiar e editar ficheiros permitidos",
            "Desenvolvimento": "Ficheiros + terminal + tarefas de IA",
            "Controlo total": "Terminal, ficheiros, ecrã, teclado e rato"
        }
        for name, detail in modes.items():
            row = tk.Frame(c, bg=PANEL)
            row.pack(fill="x", pady=3)
            tk.Radiobutton(row, text=name, variable=self.mode, value=name,
                           bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT,
                           activebackground=PANEL, activeforeground=ACCENT,
                           font=("Segoe UI", 11)).pack(side="left")
            self._label(row, "  " + detail, 9, MUTED).pack(side="left")
        actions = tk.Frame(c, bg=PANEL)
        actions.pack(fill="x", pady=(14, 0))
        self._button(actions, "Autorizar 15 min", lambda: self._grant(15), accent=True).pack(side="left", padx=(0, 8))
        self._button(actions, "1 hora", lambda: self._grant(60)).pack(side="left", padx=(0, 8))
        self._label(actions, "Máximo 60 minutos por sessão; renova com confirmação local.", 9, MUTED).pack(side="left", padx=(7, 0))
        control = self._card()
        control.pack(fill="x")
        self._label(control, "Interrupção imediata", 13, TEXT, bold=True).pack(anchor="w")
        self._label(control, "Revoga novas ações e a leitura remota de logs. Tarefas existentes continuam até serem paradas.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=(8, 12))
        self._button(control, "Revogar acesso agora", self._revoke, danger=True).pack(anchor="w")
        self._button(control, "EMERGÊNCIA: revogar e parar tarefas",
                     self._emergency_stop, danger=True).pack(anchor="w", pady=(10, 0))

    def _grant(self, minutes):
        caps = {"Ficheiros": ["writes"], "Desenvolvimento": ["writes", "shell"],
                "Controlo total": ["writes", "shell", "screen", "input"]}[self.mode.get()]
        warning = "Queres autorizar " + ", ".join(caps) + f" durante {minutes} minutos?\n\n"
        warning += "Terminal e controlo gráfico podem aceder a dados fora das pastas permitidas."
        if not messagebox.askyesno("Autorização local", warning, icon="warning"):
            return
        proof = simpledialog.askstring("Confirmar no teu Windows", "Escreve AUTORIZAR para confirmar:",
                                       parent=self)
        if proof != "AUTORIZAR":
            messagebox.showinfo("Cancelado", "Acesso não concedido.")
            return
        try:
            grant_local(self.config_data, caps, minutes)
            self.show("Acesso")
        except Exception as exc:
            self._notify_error(exc, context="permissions")

    def _revoke(self):
        if messagebox.askyesno("Revogar acesso", "Revogar agora as permissões privilegiadas?"):
            revoke_local(self.config_data)
            self.show("Acesso")

    def _emergency_stop(self):
        warning = ("Bloquear novas ações remotas e tentar terminar todas as tarefas "
                   "iniciadas pelo Universal Remote?\n\n"
                   "As tarefas interrompidas podem perder trabalho não guardado. "
                   "Este botão não termina aplicações que não foram lançadas "
                   "pelo gestor de tarefas do Universal Remote.")
        if not messagebox.askyesno("Interrupção de emergência", warning, icon="warning"):
            return
        try:
            report = emergency_revoke_and_stop(self.config_data, self.jobs)
            self.show("Acesso")
            if report["errors"] or report["remaining"]:
                messagebox.showwarning(
                    "Revogado; algumas tarefas necessitam de atenção",
                    f"Tarefas paradas: {len(report['stopped'])}\n"
                    f"Ainda ativas: {len(report['remaining'])}\n"
                    f"Erros: {len(report['errors'])}.\n"
                    "Verifica a página Tarefas e o Gestor de Tarefas do Windows.")
            else:
                messagebox.showinfo("Acesso revogado",
                    f"Novas ações remotas bloqueadas; {len(report['stopped'])} tarefas paradas.")
        except Exception as exc:
            self._notify_error(exc, context="permissions")

    def _tasks(self):
        self._heading("Tarefas da IA", "Processos iniciados pelo Universal Remote; estado persistente após reconexões.")
        c = self._card()
        c.pack(fill="both", expand=True)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("URM.Treeview", background=PANEL_ALT, fieldbackground=PANEL_ALT,
                        foreground=TEXT, rowheight=29, borderwidth=0)
        style.configure("URM.Treeview.Heading", background=PANEL, foreground=TEXT)
        self.task_table = ttk.Treeview(c, columns=("name", "state", "pid"),
                                       show="headings", height=8, style="URM.Treeview")
        for key, label, width in (("name", "Tarefa", 230), ("state", "Estado", 145), ("pid", "PID", 75)):
            self.task_table.heading(key, text=label)
            self.task_table.column(key, width=width)
        self.task_table.pack(fill="both", expand=True)
        controls = tk.Frame(c, bg=PANEL)
        controls.pack(fill="x", pady=(10, 8))
        self._button(controls, "Atualizar", self._refresh_tasks).pack(side="left", padx=(0, 8))
        self._button(controls, "Ver saída", self._show_output).pack(side="left", padx=(0, 8))
        self._button(controls, "Parar selecionada", self._stop_task, danger=True).pack(side="left")
        self.task_output = tk.Text(c, height=7, bg="#080D18", fg="#BCD3E8",
                                   insertbackground=TEXT, wrap="word", relief="flat",
                                   font=("Consolas", 9))
        self.task_output.pack(fill="x", pady=(8, 0))
        self._refresh_tasks()

    def _selected_id(self):
        selected = self.task_table.selection()
        return selected[0] if selected else None

    def _refresh_tasks(self):
        if not hasattr(self, "task_table"):
            return
        for row in self.task_table.get_children():
            self.task_table.delete(row)
        for job in self.jobs.list_jobs(limit=50):
            self.task_table.insert("", "end", iid=job["job_id"],
                                   values=(job["label"], job["status"], job["pid"]))

    def _show_output(self):
        job_id = self._selected_id()
        if not job_id:
            return
        try:
            data = self.jobs.output(job_id, 0, 32768)
            self.task_output.delete("1.0", "end")
            self.task_output.insert("end", data["text"])
        except Exception as exc:
            self._notify_error(exc, context="task")

    def _stop_task(self):
        job_id = self._selected_id()
        if job_id and messagebox.askyesno("Interromper tarefa", "Terminar esta tarefa e os subprocessos associados?"):
            try:
                self.jobs.stop(job_id)
                self._refresh_tasks()
            except Exception as exc:
                self._notify_error(exc, context="task")

    def _windows(self):
        self._heading("Janelas do Windows", "Identificação direta de janelas pelo Win32, sem outra aplicação remota.")
        c = self._card()
        c.pack(fill="both", expand=True)
        self.window_listbox = tk.Listbox(c, bg=PANEL_ALT, fg=TEXT, selectbackground="#285470",
                                         relief="flat", font=("Segoe UI", 11))
        self.window_listbox.pack(fill="both", expand=True)
        self.window_rows = []
        controls = tk.Frame(c, bg=PANEL)
        controls.pack(fill="x", pady=(11, 0))
        self._button(controls, "Atualizar janelas", self._refresh_windows).pack(side="left", padx=(0, 8))
        self._button(controls, "Trazer à frente", self._focus_selected).pack(side="left")
        self._refresh_windows()

    def _refresh_windows(self):
        from native_windows import window_list
        self.window_listbox.delete(0, "end")
        self.window_rows = window_list(80)
        for window in self.window_rows:
            self.window_listbox.insert("end", f"PID {window['pid']:>6}   {window['title'][:86]}")

    def _focus_selected(self):
        from native_windows import focus_window
        sel = self.window_listbox.curselection()
        if sel:
            row = self.window_rows[sel[0]]
            try:
                focus_window(row["handle"], row["pid"])
            except Exception as exc:
                self._notify_error(exc, context="windows")

    def _activity(self):
        self._heading("Atividade", "Histórico técnico de ferramentas, sem guardar argumentos nem credenciais.")
        c = self._card()
        c.pack(fill="both", expand=True)
        # Reserve the refresh control before the expandable viewer; otherwise
        # Tk may shrink the button to 1x1 at 200% DPI.
        self._button(c, "Atualizar", lambda: self.show("Atividade")).pack(
            side="bottom", anchor="w", pady=(9, 0))
        viewer = tk.Text(c, bg="#080D18", fg="#BCD3E8", insertbackground=TEXT,
                         wrap="word", relief="flat", font=("Consolas", 9))
        viewer.pack(side="top", fill="both", expand=True)
        log = STATE / "logs" / "operations.log"
        if log.is_file():
            with log.open(encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-120:]
            viewer.insert("1.0", "".join(lines))
        else:
            viewer.insert("1.0", "Sem registos de atividade nesta instalação.")
        viewer.configure(state="disabled")


def main():
    UniversalRemoteApp().mainloop()


if __name__ == "__main__":
    main()
