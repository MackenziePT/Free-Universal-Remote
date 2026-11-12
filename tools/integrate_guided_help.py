"""One-pass, idempotent UX integration; no live-agent installation changes."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/"universal_remote_ui.py"
ENTRY=ROOT/"public_gui.py"

def replace_exact(src: str, old: str, new: str, context: str) -> str:
    if new in src:
        print("ALREADY_PRESENT",context)
        return src
    found=src.count(old)
    if found != 1:
        raise RuntimeError(f"{context}: expected exactly one original anchor, found {found}")
    return src.replace(old,new,1)

ui=UI.read_text(encoding="utf-8")
steps=[
("import help",
'from dependency_preflight import check_dependencies, has_missing_required_dependencies',
'from dependency_preflight import check_dependencies, has_missing_required_dependencies\nfrom help_center import diagnose, friendly_text, guidance, issue_for_exception, safe_diagnostic_report'),
("sidebar help",
'("Janelas", "▦"), ("Atividade", "≡")):',
'("Janelas", "▦"), ("Atividade", "≡"), ("Ajuda", "?")):'),
("scrollable help",
'if page in {"Início", "Conexões", "Acesso"}:',
'if page in {"Início", "Conexões", "Acesso", "Ajuda"}:'),
("route help",
'"Janelas": self._windows, "Atividade": self._activity}[page]()',
'"Janelas": self._windows, "Atividade": self._activity,\n         "Ajuda": self._help}[page]()'),
("home help button",
'        self._button(self.content, "Verificar componentes instalados",',
'        self._button(self.content, "Ajuda e resolução de problemas",\n                     lambda: self.show("Ajuda"), accent=True).pack(anchor="w", pady=7)\n        self._button(self.content, "Verificar componentes instalados",'),
("status accurate",
'●  Motor local instalado · ligação remota não configurada',
'●  Motor local instalado · ligação remota por confirmar'),
("dependency help",
'            messagebox.showwarning("Instalação incompleta",\n                                   text+"\\n\\nAbre o instalador e escolhe Reparar.",parent=self)',
'            self.show("Ajuda")'),
("power shell guidance",
'            messagebox.showerror("Não foi possível preparar",detail)',
'            self._notify_error(RuntimeError("optional component"), context="powershell")'),
("pairing guidance",
'            messagebox.showerror("Emparelhamento indisponível", str(exc), parent=self)',
'            self._notify_error(exc, context="pairing")'),
("config guidance",
'            messagebox.showerror("Agente local indisponível", str(exc))',
'            self._notify_error(exc, context="installation")'),
("grant guidance",
'            messagebox.showerror("Permissão recusada", str(exc))',
'            self._notify_error(exc, context="permissions")'),
("task output guidance",
'            messagebox.showerror("Falha a ler saída", str(exc))',
'            self._notify_error(exc, context="task")'),
("task stop guidance",
'                messagebox.showerror("Falha ao terminar", str(exc))',
'                self._notify_error(exc, context="task")'),
("window focus guidance",
'                messagebox.showerror("Não foi possível ativar", str(exc))',
'                self._notify_error(exc, context="windows")')
]
for name,old,new in steps:
    ui=replace_exact(ui,old,new,name)

methods="    def _notify_error(self, error: BaseException, context: str = \"\"):\n        \"\"\"Friendly, actionable problem dialog with no raw paths or secret data.\"\"\"\n        item=issue_for_exception(error,context=context)\n        message=friendly_text(item)+\"\\n\\nQueres abrir a Ajuda para veres os próximos passos?\"\n        if messagebox.askyesno(item.title,message,parent=self,icon=\"warning\"):\n            self.show(\"Ajuda\")\n\n    def _copy_help_report(self):\n        summary=safe_diagnostic_report(getattr(self,\"_help_issues\",()))\n        self.clipboard_clear()\n        self.clipboard_append(summary)\n        messagebox.showinfo(\"Resumo copiado\",\n                            \"Copiei apenas os códigos dos problemas, sem palavras-passe, \"\n                            \"ficheiros pessoais nem chaves.\",parent=self)\n\n    def _help(self):\n        \"\"\"Visible support with clear instructions; diagnosis itself never changes Windows.\"\"\"\n        self._heading(\"Ajuda e resolução de problemas\",\n                      \"Explicações simples e passos seguros. Não precisas de usar comandos.\")\n        checks=check_dependencies()\n        self._help_issues=diagnose(checks,local_agent_available())\n        actions=self._card()\n        actions.pack(fill=\"x\",pady=(0,13))\n        self._label(actions,\"O que podes fazer agora\",13,TEXT,bold=True).pack(anchor=\"w\")\n        self._label(actions,\"Verificar novamente não altera ficheiros nem permissões.\",\n                    10,MUTED,wraplength=620).pack(anchor=\"w\",pady=(5,12))\n        bar=tk.Frame(actions,bg=PANEL)\n        bar.pack(fill=\"x\")\n        self._button(bar,\"Verificar novamente\",lambda:self.show(\"Ajuda\"),\n                     accent=True).pack(side=\"left\",padx=(0,8))\n        self._button(bar,\"Copiar resumo sem dados pessoais\",\n                     self._copy_help_report).pack(side=\"left\")\n        for item in self._help_issues:\n            box=self._card()\n            box.pack(fill=\"x\",pady=(0,12))\n            color=RED if item.severity==\"error\" else (GREEN if item.code==\"LOCAL_OK\" else ACCENT)\n            self._label(box,item.title,14,color,bold=True).pack(anchor=\"w\",pady=(0,7))\n            self._label(box,item.explanation,10,TEXT,wraplength=630).pack(anchor=\"w\",pady=(0,11))\n            self._label(box,\"Como resolver:\",10,MUTED,bold=True).pack(anchor=\"w\",pady=(0,5))\n            for n,step in enumerate(item.steps,1):\n                self._label(box,f\"{n}. {step}\",10,TEXT,wraplength=630).pack(\n                    anchor=\"w\",pady=(0,5))\n            if item.page and item.page!=\"Ajuda\":\n                self._button(box,item.button or \"Abrir\",\n                             lambda page=item.page:self.show(page)).pack(anchor=\"w\",pady=(7,0))\n        note=self._card()\n        note.pack(fill=\"x\",pady=(0,12))\n        self._label(note,\"Se aparecer um aviso de segurança\",12,TEXT,bold=True).pack(anchor=\"w\")\n        self._label(note,\"Não desatives o Defender, a firewall ou o antivírus. \"\n                    \"Confirma o editor e a origem do ficheiro. Se não os reconheces, cancela. \"\n                    \"A verificação local não confirma o emparelhamento remoto.\",\n                    10,MUTED,wraplength=630).pack(anchor=\"w\",pady=(7,0))\n\n"
ui=replace_exact(ui,'    def _access(self):',methods+'    def _access(self):',"help method");
entry=ENTRY.read_text(encoding="utf-8")
entry=replace_exact(entry,
'from dependency_preflight import check_dependencies, has_missing_required_dependencies, powershell_check',
'from dependency_preflight import check_dependencies, has_missing_required_dependencies, powershell_check\nfrom help_center import friendly_text, guidance, issue_for_exception',
"entry imports")
# Replace only the existing explanatory paragraph, keeping logging and fallback.
start = entry.index('    explanation = (')
end = entry.index('    try:\n        messagebox.showerror(', start)
entry = (entry[:start]
         + '    item = issue_for_exception(error, context="startup")\n'
         + '    explanation = (friendly_text(item) + "\\n\\nCódigo: " + item.code +\n'
         + '                   "\\nO relatório técnico local não guarda palavras-passe, argumentos nem conteúdos.")\n'
         + entry[end:])
UI.write_text(ui,encoding="utf-8")
ENTRY.write_text(entry,encoding="utf-8")
print("GUIDED_ERROR_UI_PATCH_PASS",len(ui.splitlines()),len(entry.splitlines()))
