"""Refactor UI connection status to not misstate remote connectivity or use developer Python."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/"universal_remote_ui.py"
s=p.read_text(encoding="utf-8")
def change(old,new):
    global s
    if old not in s:raise RuntimeError(old[:180])
    s=s.replace(old,new)

change("import os\nfrom pathlib import Path","import os\nimport sys\nfrom pathlib import Path")
needle="\n\ndef read_status():"
assert needle in s
s=s.replace(needle,'''

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
'''+needle)
change('''        self.live.config(text="●  Túnel pronto" if ready else "●  Túnel indisponível",
                         fg=GREEN if ready else RED)''',
       '''        local = local_agent_available()
        if not local:
            label, tint = "●  Agente MCP local em falta", RED
        elif ready:
            label, tint = "●  MCP local pronto · túnel ativo no PC", GREEN
        else:
            label, tint = "●  MCP local pronto · túnel opcional", GREEN
        self.live.config(text=label, fg=tint)''')
change('''        self.status_detail.configure(
            text=("●  Ligação privada pronta" if read_status() else "●  Ligação privada não detetada") + suffix,
            fg=GREEN if read_status() else RED)''',
       '''        local = local_agent_available()
        tunnel = read_status()
        self.status_detail.configure(
            text=("●  MCP local disponível" if local else "●  Agente MCP local indisponível")
                 + (" · túnel ativo localmente" if tunnel else " · ligação remota por configurar") + suffix,
            fg=GREEN if local else RED)''')
change('''        self._label(box, "Ligação de saída já configurada. O estado é mostrado no topo da aplicação.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=8)''',
       '''        self._label(box, "A ligação remota não é ativada automaticamente. Para ChatGPT remoto, "
                    "é necessário emparelhar uma conta e configurar um transporte privado autenticado. "
                    "O estado HTTP local não confirma que um cliente remoto está ligado.",
                    10, MUTED, wraplength=630).pack(anchor="w", pady=8)''')
change('''        config = {
            "mcpServers": {
                "universal-remote": {
                    "command": str(HERE / ".venv" / "Scripts" / "python.exe"),
                    "args": [str(HERE / "launch_server.py")],
                    "env": {"HARMONY_MCP_CONFIG": str(HERE / "config.json")}
                }
            }
        }
        self.clipboard_clear()
        self.clipboard_append(json.dumps(config, indent=2, ensure_ascii=False))
        messagebox.showinfo("Configuração copiada", "Configuração MCP local copiada para a área de transferência.")''',
       '''        try:
            config = local_mcp_config()
            self.clipboard_clear()
            self.clipboard_append(json.dumps(config, indent=2, ensure_ascii=False))
        except Exception as exc:
            messagebox.showerror("Agente local indisponível", str(exc))
            return
        messagebox.showinfo("Configuração copiada",
                            "Configuração MCP local copiada. Não contém credenciais. "
                            "Importa-a nas definições de um cliente MCP compatível.")''')
p.write_text(s,encoding="utf-8",newline="\n")
print("MCP_UI_PUBLIC_INSTALL_FIXED")
