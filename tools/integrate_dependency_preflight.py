"""Make dependency detection useful and understandable in the actual Windows UI."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def replace(relative,old,new):
    path=root/relative
    source=path.read_text(encoding="utf-8")
    if old not in source:raise RuntimeError("Missing in "+relative+": "+old[:110])
    source=source.replace(old,new)
    path.write_text(source,encoding="utf-8",newline="\n")
    print("UPDATED",relative)

replace("public_gui.py",
    "from public_paths import config_path,config_for_root,default_workspace,write_initial_config,product_home,PRIVILEGED",
    "from public_paths import config_path,config_for_root,default_workspace,write_initial_config,product_home,PRIVILEGED\n"
    "from dependency_preflight import check_dependencies, has_missing_required_dependencies")
replace("public_gui.py",
    '            self._text(body,"Por defeito não existe acesso privilegiado nem qualquer ligação remota ativa.",11,MUTED)',
    '            self._text(body,"Python e bibliotecas já incluídos na aplicação. Não precisas de instalar nada manualmente.",11,ACCENT)\n'
    '            self._text(body,"Por defeito não existe acesso privilegiado nem qualquer ligação remota ativa.",10,MUTED)')
replace("public_gui.py",
    '        tk.Button(nav,text=("Concluir e abrir" if self.step==2 else "Continuar"),',
    '        tk.Button(nav,text=("Concluir e abrir" if self.step==4 else "Continuar"),')
replace("public_gui.py",
    '''    def _next(self):
        if self.step==1:''',
    '''    def _next(self):
        if self.step==0:
            checks=check_dependencies()
            if has_missing_required_dependencies(checks):
                missing="\\n".join("• "+row.title+": "+row.detail
                                  for row in checks if row.required and not row.ok)
                messagebox.showerror("É preciso reparar a instalação",
                                     "O Universal Remote detetou componentes em falta:\\n\\n"+missing,
                                     parent=self)
                return
        if self.step==1:''')
replace("universal_remote_ui.py",
    "from public_runtime import get_private_powershell_setup_path, install_private_powershell",
    "from public_runtime import get_private_powershell_setup_path, install_private_powershell\n"
    "from dependency_preflight import check_dependencies, has_missing_required_dependencies")
replace("universal_remote_ui.py",
    'STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HarmonyRemoteMCP"',
    'STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UniversalRemote"')
replace("universal_remote_ui.py",
    '''        self._make_shell()
        self.show("Início")
        self.after(2800, self._heartbeat)''',
    '''        self._make_shell()
        self.protocol("WM_DELETE_WINDOW", self._shutdown)
        self.show("Início")
        self.after(2800, self._heartbeat)''')
replace("universal_remote_ui.py",
    '''    def _make_shell(self):''',
    '''    def _shutdown(self):
        """Stop local monitoring on exit; persistent tasks remain controlled by the task manager."""
        try:
            self.jobs.close()
        finally:
            self.destroy()

    def _show_dependency_status(self):
        """Explain prerequisites in plain language. Never installs anything silently."""
        results=check_dependencies()
        text="\\n\\n".join(
            ("✓ " if row.ok else "⚠ ") + row.title + "\\n" + row.detail
            for row in results
        )
        if has_missing_required_dependencies(results):
            messagebox.showwarning("Instalação incompleta",
                                   text+"\\n\\nAbre o instalador e escolhe Reparar.",parent=self)
        else:
            messagebox.showinfo("Instalação verificada",
                                text+"\\n\\nNão precisas de instalar Python ou bibliotecas.",
                                parent=self)

    def _make_shell(self):''')
replace("universal_remote_ui.py",
    '''        ready = read_status()
        local = local_agent_available()
        if not local:
            label, tint = "●  Agente MCP local em falta", RED
        elif ready:
            label, tint = "●  MCP local pronto · túnel ativo no PC", GREEN
        else:
            label, tint = "●  MCP local pronto · túnel opcional", GREEN''',
    '''        # Do not confuse a foreign listener on port 8080 (e.g. a previous
        # installed release) with this product's actual authenticated pairing.
        local = local_agent_available()
        if not local:
            label, tint = "●  Ligação local: reparação necessária", RED
        else:
            label, tint = "●  Motor local instalado · ligação remota não configurada", GREEN''')
replace("universal_remote_ui.py",
    '''        tunnel = read_status()
        self.status_detail.configure(
            text=("●  MCP local disponível" if local else "●  Agente MCP local indisponível")
                 + (" · túnel ativo localmente" if tunnel else " · ligação remota por configurar") + suffix,
            fg=GREEN if local else RED)''',
    '''        self.status_detail.configure(
            text=("●  Motor MCP local disponível" if local else "●  Motor de ligação em falta")
                 + " · ligação remota por configurar" + suffix,
            fg=GREEN if local else RED)''')
replace("universal_remote_ui.py",
    '''        self._label(self.content,
                    "O Universal Remote é o motor de execução. As outras aplicações "
                    "servem como referências, não como dependências.",
                    11, MUTED, wraplength=660).pack(anchor="w", pady=6)''',
    '''        self._button(self.content, "Verificar componentes instalados",
                     self._show_dependency_status).pack(anchor="w", pady=7)
        self._label(self.content,
                    "Python e bibliotecas estão incluídos no programa; não precisas de instalá-los.",
                    10, MUTED, wraplength=660).pack(anchor="w", pady=4)''')
replace("universal_remote_ui.py",
    '''        self._button(box, "Copiar configuração MCP", self._copy_config, accent=True).pack(anchor="w")''',
    '''        controls = tk.Frame(box,bg=PANEL)
        controls.pack(anchor="w",fill="x")
        self._button(controls, "Copiar configuração MCP", self._copy_config, accent=True).pack(side="left",padx=(0,9))
        self._button(controls, "Verificar instalação", self._show_dependency_status).pack(side="left")''')
print("FIRST_RUN_AND_UI_DEPENDENCY_CHECKS_INTEGRATED")
