"""Five-step user-oriented first-run flow; no implicit remote access."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/"public_gui.py"
s=p.read_text(encoding="utf-8")
s=s.replace('PASSO {self.step+1} DE 3','PASSO {self.step+1} DE 5')
start=s.index("        if self.step==0:\n",s.index("    def _render(self):"))
end=s.index("\n        nav=tk.Frame",start)
replacement='''        if self.step==0:
            self._text(body,"Bem-vindo ao Universal Remote",23,FG,"bold")
            self._text(body,"Liga assistentes de IA compatíveis ao teu Windows através de "
                       "um agente MCP autónomo. Tu escolhes as pastas, as permissões e as ligações.",12,MUTED)
            self._text(body,"O que acontece nesta configuração:",12,ACCENT,"bold")
            self._text(body,"1. Selecionas uma pasta de trabalho.\\n"
                       "2. Decides o que pode ser autorizado.\\n"
                       "3. Vês como conectar uma IA, sem ativar ligações remotas automaticamente.\\n"
                       "4. Confirmas tudo antes de começar.",11,FG)
            self._text(body,"Por defeito não existe acesso privilegiado nem qualquer ligação remota ativa.",11,MUTED)
        elif self.step==1:
            self._text(body,"Escolhe uma pasta de trabalho",22,FG,"bold")
            self._text(body,"O Universal Remote não partilha todo o disco. "
                       "Seleciona uma pasta para ficheiros e projetos que autorizas.",11,MUTED)
            entry=tk.Entry(body,textvariable=self.selection,font=("Segoe UI",11),
                           bg="#0A1222",fg=FG,insertbackground=FG,relief="flat")
            entry.pack(fill="x",ipady=12,pady=(8,14))
            tk.Button(body,text="Escolher pasta...",command=self._pick,bg="#223C5C",fg=FG,relief="flat",
                      activebackground="#315C7D",font=("Segoe UI",11),padx=16,pady=10).pack(anchor="w")
            self._text(body,"Se a pasta ainda não existir, será criada depois da confirmação final.",10,MUTED)
        elif self.step==2:
            self._text(body,"Permissões sob o teu controlo",21,FG,"bold")
            self._text(body,"Tudo começa desligado. Selecionar uma capacidade aqui não concede acesso: "
                       "cada sessão privilegiada exige nova confirmação local temporária.",11,MUTED)
            for name in PRIVILEGED:
                title,detail=DESCRIPTION[name]
                line=tk.Frame(body,bg=PANEL);line.pack(anchor="w",fill="x",pady=(5,4))
                tk.Checkbutton(line,text=title,variable=self.options[name],font=("Segoe UI",11,"bold"),
                               bg=PANEL,fg=FG,selectcolor="#17314A",activebackground=PANEL,
                               activeforeground=FG,takefocus=True).pack(anchor="w")
                self._text(line,detail,9,MUTED)
        elif self.step==3:
            self._text(body,"Ligar a tua IA",22,FG,"bold")
            self._text(body,"O motor MCP é local. Depois de concluíres, abre a secção Conexões "
                       "para copiar a configuração do agente autónomo para um cliente MCP compatível.",11,MUTED)
            self._text(body,"ChatGPT remoto e outros clientes na Internet",12,ACCENT,"bold")
            self._text(body,"Exigem um transporte privado autenticado e emparelhamento específico. "
                       "Nenhuma conta, túnel ou porta pública será configurada sem autorização.",11,FG)
            self._text(body,"PowerShell 7 (opcional): na secção Conexões podes obter automaticamente "
                       "a versão estável mais recente da Microsoft, verificada por assinatura e SHA-256.",10,MUTED)
        else:
            self._text(body,"Confirmar e começar",22,FG,"bold")
            self._text(body,"Pasta autorizada:",11,ACCENT,"bold")
            self._text(body,self.selection.get(),11,FG)
            enabled=[DESCRIPTION[k][0] for k,v in self.options.items() if v.get()]
            self._text(body,"Capacidades que poderás autorizar temporariamente:",11,ACCENT,"bold")
            self._text(body,(", ".join(enabled) if enabled else "Nenhuma — apenas leitura"),11,FG)
            self._text(body,"A aplicação não concede permissões automaticamente, não abre portas "
                       "na Internet e não ativa o arranque com o Windows.",11,MUTED)
'''
s=s[:start]+replacement+s[end:]
needle='''        if self.step==0:
            try:config_for_root(self.selection.get())'''
assert needle in s
s=s.replace(needle,'''        if self.step==1:
            try:config_for_root(self.selection.get())''')
assert "if self.step<2:" in s
s=s.replace("if self.step<2:","if self.step<4:")
p.write_text(s,encoding="utf-8",newline="\n")
print("PUBLIC_FIVE_STEP_ONBOARDING_READY")
