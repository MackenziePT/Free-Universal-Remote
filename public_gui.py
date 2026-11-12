"""Universal Remote Windows first-run onboarding and standalone desktop entrypoint."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
from public_paths import config_path,config_for_root,default_workspace,write_initial_config,product_home,PRIVILEGED
from dependency_preflight import check_dependencies, has_missing_required_dependencies, powershell_check
from help_center import friendly_text, guidance, issue_for_exception

def recommended_first_run_permissions() -> dict[str,bool]:
    """Prepare capabilities for later owner-granted sessions; grant none."""
    return {name:True for name in PRIVILEGED}

BG="#0A0F1D";PANEL="#151F32";FG="#EAF0FA";MUTED="#A6B7D0";ACCENT="#75D9FF"
DESCRIPTION={
    "writes":("Modificar ficheiros","Criar, mover e eliminar ficheiros nas pastas autorizadas"),
    "shell":("Executar comandos","Executar tarefas com os teus privilégios Windows, potencialmente fora das pastas"),
    "screen":("Ver o ecrã","Permitir capturas do ambiente de trabalho mediante autorização local"),
    "input":("Controlar rato e teclado","Permitir cliques e escrita com autorização temporária"),
}

class Onboarding(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Universal Remote | Primeira configuração")
        self.configure(bg=BG)
        self.geometry("760x605")
        self.minsize(660,540)
        self.resizable(True,True)
        self.step=0
        self.selection=tk.StringVar(value=str(default_workspace()))
        self.options={name:tk.BooleanVar(value=ready) for name,ready in
                      recommended_first_run_permissions().items()}
        self.prepare_full_control=tk.BooleanVar(value=True)
        # Optional tools are prepared on first run only when not already present.
        self.prepare_powershell=tk.BooleanVar(value=False)
        self.completed=False
        self.show_advanced=tk.BooleanVar(value=False)
        self.bind('<MouseWheel>', self._on_mousewheel)
        self.bind('<Prior>', lambda event: self._scroll_canvas.yview_scroll(-1,'pages'))
        self.bind('<Next>', lambda event: self._scroll_canvas.yview_scroll(1,'pages'))
        self._render()

    def _text(self,parent,value,size=11,color=FG,weight="normal",wrap=625):
        x=tk.Label(parent,text=value,font=("Segoe UI",size,weight),
                   fg=color,bg=parent["bg"],wraplength=wrap,justify="left",anchor="w")
        x.pack(anchor="w",fill="x",pady=(0,10))
        return x

    def _render(self):
        for x in self.winfo_children():x.destroy()
        head=tk.Frame(self,bg=BG,padx=40,pady=26);head.pack(fill="x")
        self._text(head,"◈   UNIVERSAL REMOTE",18,ACCENT,"bold")
        self._text(head,f"CONFIGURAÇÃO INICIAL · PASSO {self.step+1} DE 3",10,MUTED,"bold")
        nav=tk.Frame(self,bg=BG,padx=38,pady=8)
        # Reserve bottom navigation first, before the scrollable content can expand.
        nav.pack(side="bottom",fill="x",pady=(0,12))
        # Scrollable content keeps all options reachable at 125%-200% text/DPI.
        # The navigation bar is outside the canvas and stays visible.
        shell=tk.Frame(self,bg=PANEL)
        shell.pack(fill="both",expand=True,padx=38,pady=(0,18))
        canvas=tk.Canvas(shell,bg=PANEL,highlightthickness=0,borderwidth=0)
        scrollbar=tk.Scrollbar(shell,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right",fill="y")
        canvas.pack(side="left",fill="both",expand=True)
        body=tk.Frame(canvas,bg=PANEL,padx=32,pady=26)
        window=canvas.create_window((0,0),window=body,anchor="nw")
        body.bind("<Configure>",lambda event:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda event:canvas.itemconfigure(window,width=event.width))
        self._scroll_canvas=canvas
        if self.step==0:
            self._text(body,"Bem-vindo! Escolhe a tua pasta.",22,FG,"bold")
            self._text(body,"Só precisas de uma pasta de trabalho. O Universal Remote "
                       "não partilha o teu disco inteiro.",11,MUTED)
            self._text(body,"Esta pasta é recomendada e já está selecionada:",11,ACCENT,"bold")
            entry=tk.Entry(body,textvariable=self.selection,font=("Segoe UI",11),
                           bg="#0A1222",fg=FG,insertbackground=FG,relief="flat")
            entry.pack(fill="x",ipady=12,pady=(8,14))
            tk.Button(body,text="Escolher outra pasta (opcional)",command=self._pick,
                      bg="#223C5C",fg=FG,relief="flat",
                      activebackground="#315C7D",font=("Segoe UI",11),
                      padx=16,pady=10).pack(anchor="w")
            self._text(body,"Python e componentes necessários já vêm incluídos. "
                       "Não precisas de instalar nada à parte.",11,MUTED)
            self._text(body,"Só vamos guardar a pasta após confirmares no último passo.",
                       10,MUTED)
        elif self.step==1:
            self._text(body,"Preparar o controlo do Windows",20,FG,"bold")
            self._text(body,"Ecrã, rato/teclado, ficheiros e terminal ficam prontos "
                       "para sessões que tu aproves. Nenhuma sessão é autorizada "
                       "automaticamente.",11,MUTED)
            tk.Checkbutton(body,
                           text="Preparar todas as capacidades (recomendado)",
                           variable=self.prepare_full_control,
                           command=self._toggle_ready,
                           bg=PANEL,fg=FG,selectcolor="#17314A",
                           activebackground=PANEL,activeforeground=FG,
                           font=("Segoe UI",11),takefocus=True).pack(anchor="w",pady=(8,8))
            self._text(body,"Podes limitar capacidades em Opções avançadas. "
                       "A autorização efetiva terá confirmação local.",11,ACCENT)
            tk.Checkbutton(body,text="Mostrar permissões avançadas (opcional)",
                           variable=self.show_advanced,command=self._toggle_advanced,
                           bg=PANEL,fg=FG,selectcolor="#17314A",
                           activebackground=PANEL,activeforeground=FG,
                           font=("Segoe UI",11),takefocus=True).pack(anchor="w",pady=(8,12))
            if self.show_advanced.get():
                for name in PRIVILEGED:
                    title,detail=DESCRIPTION[name]
                    line=tk.Frame(body,bg=PANEL)
                    line.pack(anchor="w",fill="x",pady=(5,4))
                    tk.Checkbutton(line,text=title,variable=self.options[name],
                                   font=("Segoe UI",11,"bold"),bg=PANEL,fg=FG,
                                   selectcolor="#17314A",activebackground=PANEL,
                                   activeforeground=FG,takefocus=True).pack(anchor="w")
                    self._text(line,detail,9,MUTED)
        else:
            self._text(body,"Confirmar e começar",22,FG,"bold")
            self._text(body,"Pasta autorizada:",11,ACCENT,"bold")
            self._text(body,self.selection.get(),11,FG)
            enabled=[DESCRIPTION[k][0] for k,v in self.options.items() if v.get()]
            self._text(body,"Capacidades que poderás autorizar temporariamente:",11,ACCENT,"bold")
            self._text(body,(", ".join(enabled) if enabled else "Nenhuma — apenas leitura"),11,FG)
            self._text(body,"Ferramenta avançada opcional: "+("preparação selecionada"
                          if self.prepare_powershell.get() else "sem preparação automática"),11,MUTED)
            self._text(body,"Preparar capacidades não concede sessões privilegiadas. "
                       "O acesso exige autorização local, pode ser revogado e "
                       "não abre portas na Internet nem ativa o arranque automático.",11,MUTED)

        if self.step>0:
            tk.Button(nav,text="Voltar",command=self._back,bg="#243047",fg=FG,relief="flat",
                      font=("Segoe UI",11),padx=20,pady=10).pack(side="left")
        tk.Button(nav,text=("Concluir e abrir" if self.step==2 else "Continuar"),
                  command=self._next,bg=ACCENT,fg="#061326",activebackground="#92E4FF",relief="flat",
                  font=("Segoe UI",11,"bold"),padx=22,pady=10).pack(side="right")

    def _on_mousewheel(self,event):
        if not getattr(self,'_scroll_canvas',None) or not self._scroll_canvas.winfo_exists():
            return
        delta=getattr(event,'delta',0)
        if delta:
            self._scroll_canvas.yview_scroll(-1 if delta>0 else 1,'units')

    def _toggle_ready(self):
        # A single explicit first-run choice only prepares policy; it never
        # creates a temporary grant or opens a remote tunnel.
        for option in self.options.values():
            option.set(self.prepare_full_control.get())
        self._render()

    def _toggle_advanced(self):
        # Collapsing advanced options does not silently revoke or add policy.
        self._render()

    def _pick(self):
        folder=filedialog.askdirectory(title="Escolhe a pasta que autorizas",mustexist=False)
        if folder:self.selection.set(folder)

    def _back(self):
        self.step-=1;self._render()

    def _next(self):
        if self.step==0:
            checks=check_dependencies()
            if has_missing_required_dependencies(checks):
                missing="\n".join("• "+row.title+": "+row.detail
                                  for row in checks if row.required and not row.ok)
                messagebox.showerror("É preciso reparar a instalação",
                                     "O Universal Remote detetou componentes em falta:\n\n"+missing,
                                     parent=self)
                return
        if self.step==0:
            try:config_for_root(self.selection.get())
            except Exception as exc:
                messagebox.showerror("Esta pasta não pode ser utilizada",
                    "Escolhe uma pasta normal dentro dos teus Documentos ou do Ambiente de Trabalho. "
                    "Não seleciones o disco inteiro, pastas de rede ou pastas protegidas da aplicação. "
                    "A pasta sugerida é a opção mais simples.",parent=self)
                return
        if self.step<2:
            self.step+=1;self._render()
            return
        try:
            perms={k:v.get() for k,v in self.options.items()}
            policy=write_initial_config(self.selection.get(),perms)
            os.environ["HARMONY_MCP_CONFIG"]=str(policy)
            self.completed=True
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Não foi possível concluir",
                "A configuração não foi guardada. Volta ao passo da pasta e verifica "
                "se tens autorização para criar ficheiros. Podes tentar novamente "
                "sem perder o que selecionaste.",parent=self)

def report_startup_failure(error: Exception) -> None:
    """Explain launch failures without writing commands, secrets or exception arguments."""
    import traceback
    from datetime import datetime, timezone
    frames = [{"module": Path(frame.filename).name, "line": frame.lineno,
               "function": frame.name}
              for frame in traceback.extract_tb(error.__traceback__)[-12:]]
    record = {"utc": datetime.now(timezone.utc).isoformat(),
              "type": type(error).__name__, "frames": frames}
    try:
        logdir = product_home() / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        path = logdir / "startup-errors.jsonl"
        if path.is_file() and path.stat().st_size > 1048576:
            os.replace(path, logdir / "startup-errors.previous.jsonl")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    item = issue_for_exception(error, context="startup")
    explanation = (friendly_text(item) + "\n\nCódigo: " + item.code +
                   "\nO relatório técnico local não guarda palavras-passe, argumentos nem conteúdos.")
    try:
        messagebox.showerror("Falha de arranque — Universal Remote", explanation)
    except Exception:
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, explanation,
                                                  "Universal Remote", 0x10)
            except Exception:
                pass


def activation_destination(arguments: list[str]) -> str:
    """Accept only documented, non-privileged entrypoints."""
    if not arguments:
        return "Início"
    if arguments == ["universal-remote://connect"]:
        return "Conexões"
    if arguments == ["universal-remote://open"]:
        return "Início"
    raise ValueError("Ligação de abertura inválida")

def main()->int:
    policy=config_path()
    if "--self-test" in sys.argv:
        # Runtime-only probe: disposable config, no persistent grants, no live desktop.
        import tempfile
        with tempfile.TemporaryDirectory(prefix="universal-remote-public-qa-") as temp:
            original=os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"]=temp
            try:
                folder=Path(temp)/"workspace"
                file=write_initial_config(folder)
                os.environ["HARMONY_MCP_CONFIG"]=str(file)
                import universal_remote_ui as ui
                ui.STATE=product_home()
                app=ui.UniversalRemoteApp()
                try:
                    app.withdraw()
                    for page in ("Início","Guia","Conexões","Acesso","Tarefas","Janelas","Atividade","Ajuda"):
                        app.show(page);app.update_idletasks()
                finally:
                    app.jobs.close();app.destroy()
            finally:
                if original is None:os.environ.pop("LOCALAPPDATA",None)
                else:os.environ["LOCALAPPDATA"]=original
        return 0
    try:
        destination=activation_destination(sys.argv[1:])
    except ValueError:
        return 2
    prepare_powershell=False
    first_run=False
    if not policy.exists():
        wizard=Onboarding()
        wizard.mainloop()
        if not wizard.completed:return 1
        first_run=True
        prepare_powershell=wizard.prepare_powershell.get()
    os.environ["HARMONY_MCP_CONFIG"]=str(policy)
    import universal_remote_ui as ui
    ui.STATE=product_home()
    app=ui.UniversalRemoteApp(start_page=("Guia" if first_run and destination=="Início"
                                           else destination))
    if destination=="Conexões":
        # Deliberate click/activation opens the guide, never grants a remote session.
        app.after(450,app._open_tunnel_setup)
    if prepare_powershell:
        # Already selected and explained in the first-run wizard.
        # Run in a worker and keep the UI responsive; failure is non-fatal.
        app.after(700,lambda:app._prepare_powershell(approved=True))
    app.mainloop()
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        report_startup_failure(exc)
        raise SystemExit(2)
