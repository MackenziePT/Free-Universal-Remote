"""Apply the novice-friendly guide to RC5.1 source only.

Fail before writing either source if any expected anchor has changed.
No writes to the currently installed RC5.0.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ui_file = ROOT / "universal_remote_ui.py"
entry_file = ROOT / "public_gui.py"
ui = ui_file.read_text(encoding="utf-8")
entry = entry_file.read_text(encoding="utf-8")

def patch(src: str, old: str, new: str, name: str) -> str:
    if new in src and old not in src:
        return src
    count=src.count(old)
    if count!=1:
        raise RuntimeError(f"{name}: need one matching anchor, found {count}")
    return src.replace(old,new,1)

ui = patch(ui,
    'from help_center import diagnose, friendly_text, guidance, issue_for_exception, safe_diagnostic_report',
    'from help_center import diagnose, friendly_text, guidance, issue_for_exception, safe_diagnostic_report\n'
    'from guided_steps import build_steps, next_action, completed_local_count',
    "guide imports")
ui = patch(ui,
    '    def __init__(self):\n        super().__init__()',
    '    def __init__(self, start_page="Início"):\n        super().__init__()',
    "start_page argument")
ui = patch(ui,
    '        self.show("Início")\n        self.after(2800, self._heartbeat)',
    '        self.show(start_page)\n        self.after(2800, self._heartbeat)',
    "start_page activation")
ui = patch(ui,
    'for name, symbol in (("Início", "⌂"), ("Conexões", "◇"),',
    'for name, symbol in (("Início", "⌂"), ("Guia", "✓"), ("Conexões", "◇"),',
    "sidebar guided page")
ui = patch(ui,
    'if page in {"Início", "Conexões", "Acesso", "Ajuda"}:',
    'if page in {"Início", "Guia", "Conexões", "Acesso", "Ajuda"}:',
    "scroll")
ui = patch(ui,
    '{"Início": self._home, "Conexões": self._connections,',
    '{"Início": self._home, "Guia": self._guide, "Conexões": self._connections,',
    "page dispatch")
ui = patch(ui,
    '        self._overview_status()\n        panels = tk.Frame(self.content, bg=BG)',
    '''        self._overview_status()
        steps = build_steps(check_dependencies(), local_agent_available())
        suggested = next_action(steps)
        recommendation = self._card()
        recommendation.pack(fill="x", pady=(0, 13))
        self._label(recommendation,"O teu próximo passo",12,ACCENT,bold=True).pack(anchor="w")
        self._label(recommendation,suggested.title,14,TEXT,bold=True).pack(anchor="w",pady=(6,3))
        self._label(recommendation,suggested.summary,10,MUTED,wraplength=630).pack(anchor="w",pady=(0,9))
        self._button(recommendation,"Começar com o guia passo a passo",
                     lambda:self.show("Guia"),accent=True).pack(anchor="w")
        panels = tk.Frame(self.content, bg=BG)''',
    "homepage recommended action")

guide_method = '''    def _guide(self):
        """A guided, read-only start path; remote connectivity is never guessed."""
        self._heading("Vamos pôr tudo a funcionar",
                      "Segue os passos por ordem. Explico o que falta e levo-te ao sítio certo.")
        steps = build_steps(check_dependencies(), local_agent_available())
        state = self._card()
        state.pack(fill="x",pady=(0,13))
        self._label(state,"Preparação no teu computador",13,TEXT,bold=True).pack(anchor="w")
        local_done=completed_local_count(steps)
        self._label(state,f"{local_done} de 2 verificações locais concluídas automaticamente.",
                    11,GREEN if local_done==2 else MUTED,wraplength=625).pack(anchor="w",pady=(7,7))
        self._label(state,"A ligação remota ao ChatGPT é verificada separadamente. "
                    "Não damos acesso sem tua autorização.",
                    10,MUTED,wraplength=625).pack(anchor="w")
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

'''
ui=patch(ui,'    def _connections(self):',guide_method+'    def _connections(self):',"new guide UI")
ui=patch(ui,
    '        self._label(box, "ChatGPT  •  Túnel privado", 14, TEXT, bold=True).pack(anchor="w")',
    '''        self._label(box, "ChatGPT  •  Túnel privado", 14, TEXT, bold=True).pack(anchor="w")
        self._label(box,"Para ligar: 1. Abre a área de ligações da tua conta ChatGPT. "
                    "2. Escolhe o Universal Remote, se estiver disponível. "
                    "3. Confirma o pedido apenas se o reconheces. "
                    "4. Pede ao ChatGPT para verificar a ligação. "
                    "A configuração automática desta associação ainda não está concluída.",
                    10,TEXT,wraplength=630).pack(anchor="w",pady=(9,6))
        self._button(box,"Voltar ao guia",lambda:self.show("Guia")).pack(anchor="w",pady=(0,10))''',
    "ChatGPT explanatory instructions")

entry=patch(entry,
    '        self.prepare_powershell=tk.BooleanVar(value=True)',
    '        self.prepare_powershell=tk.BooleanVar(value=False)',
    "avoid automatic optional downloads")
entry=patch(entry,
    '        self.completed=False\n        self.bind',
    '        self.completed=False\n        self.show_advanced=tk.BooleanVar(value=False)\n        self.bind',
    "collapsed optional permissions")
entry=patch(entry,
    '            self._text(body,"O que acontece nesta configuração:",12,ACCENT,"bold")',
    '''            self._text(body,"Só precisas de escolher uma pasta. As opções avançadas "
                       "são opcionais e vêm desligadas.",12,ACCENT,"bold")''',
    "intro reassure")

entry=patch(entry,
    '            self._text(body,"Se a pasta ainda não existir, será criada depois da confirmação final.",10,MUTED)',
    '''            self._text(body,"A pasta sugerida já está selecionada. Não precisas de alterar nada "
                       "se quiseres utilizar essa pasta.",10,ACCENT)
            self._text(body,"Se ainda não existir, será criada depois da confirmação final.",10,MUTED)''',
    "suggested folder")

start='''            for name in PRIVILEGED:
                title,detail=DESCRIPTION[name]
                line=tk.Frame(body,bg=PANEL);line.pack(anchor="w",fill="x",pady=(5,4))
                tk.Checkbutton(line,text=title,variable=self.options[name],font=("Segoe UI",11,"bold"),
                               bg=PANEL,fg=FG,selectcolor="#17314A",activebackground=PANEL,
                               activeforeground=FG,takefocus=True).pack(anchor="w")
                self._text(line,detail,9,MUTED)'''
replacement='''            self._text(body,"Recomendado: continuar com o acesso mínimo. "
                       "Podes autorizar outras ações quando precisares.",11,ACCENT)
            tk.Checkbutton(body,text="Quero escolher permissões avançadas",
                           variable=self.show_advanced,command=self._render,
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
                    self._text(line,detail,9,MUTED)'''
entry=patch(entry,start,replacement,"progressive permissions")
entry=patch(entry,
    '            self._text(body,"O motor MCP é local. Depois de concluíres, abre a secção Conexões "\n'
    '                       "para copiar a configuração do agente autónomo para um cliente MCP compatível.",11,MUTED)',
    '            self._text(body,"Depois de começares, o guia mostra como ligar o Universal Remote "\n'
    '                       "ao ChatGPT ou a outra IA. Não precisas de configurar essa ligação já.",11,MUTED)',
    "defer pairing")
entry=patch(entry,
    '            self._text(body,"PowerShell mais recente: "+("verificação automática opcional selecionada"',
    '            self._text(body,"Ferramenta avançada opcional: "+("preparação selecionada"',
    "summary option")
entry=patch(entry,
    '    prepare_powershell=False\n    if not policy.exists():',
    '    prepare_powershell=False\n    first_run=False\n    if not policy.exists():',
    "first-run variable")
entry=patch(entry,
    '        if not wizard.completed:return 1\n        prepare_powershell=wizard.prepare_powershell.get()',
    '        if not wizard.completed:return 1\n        first_run=True\n        prepare_powershell=wizard.prepare_powershell.get()',
    "first run page")
entry=patch(entry,
    '    app=ui.UniversalRemoteApp()\n    if prepare_powershell:',
    '    app=ui.UniversalRemoteApp(start_page="Guia" if first_run else "Início")\n    if prepare_powershell:',
    "start guided after installation")
entry=patch(entry,
    'for page in ("Início","Conexões","Acesso","Tarefas","Janelas","Atividade"):',
    'for page in ("Início","Guia","Conexões","Acesso","Tarefas","Janelas","Atividade","Ajuda"):',
    "self test guide")
# Source modifications are only committed after all anchors match.
ui_file.write_text(ui, encoding="utf-8")
entry_file.write_text(entry, encoding="utf-8")
print("GUIDED_EXPERIENCE_PATCH_APPLIED",len(ui.splitlines()),len(entry.splitlines()))
