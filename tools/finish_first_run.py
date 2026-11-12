"""RC5.1 one-time simplification; verify anchors, then save both files together."""
from pathlib import Path

base=Path(__file__).resolve().parents[1]
entry=base/"public_gui.py"
gui=base/"universal_remote_ui.py"
a=entry.read_text(encoding="utf-8")
b=gui.read_text(encoding="utf-8")
def one(s, old, new, label):
    if s.count(old)!=1:
        raise RuntimeError(f"{label}: expected one anchor, got {s.count(old)}")
    return s.replace(old,new,1)

start=a.index("        if self.step==0:\n")
end=a.index("        else:\n            self._text(body,\"Confirmar e começar\"",start)
reduced='''        if self.step==0:
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
            self._text(body,"Permissões — recomendado: acesso mínimo",20,FG,"bold")
            self._text(body,"A aplicação começa com permissões avançadas desligadas. "
                       "Nenhuma sessão privilegiada é concedida automaticamente.",11,MUTED)
            self._text(body,"Só altera estas opções se souberes que precisas delas.",
                       11,ACCENT)
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
'''
a=a[:start]+reduced+a[end:]
a=one(a,'CONFIGURAÇÃO INICIAL · PASSO {self.step+1} DE 5',
      'CONFIGURAÇÃO INICIAL · PASSO {self.step+1} DE 3',"step heading")
a=one(a,'text=("Concluir e abrir" if self.step==4 else "Continuar")',
      'text=("Concluir e abrir" if self.step==2 else "Continuar")',"finish button")
a=one(a,'        if self.step==1:\n            try:config_for_root(self.selection.get())',
      '        if self.step==0:\n            try:config_for_root(self.selection.get())',"folder safety")
a=one(a,'        if self.step<4:\n            self.step+=1;self._render()',
      '        if self.step<2:\n            self.step+=1;self._render()',"navigation")
a=one(a,'                    "Não selecionas o disco inteiro, pastas de rede ou pastas protegidas da aplicação. "',
      '                    "Não seleciones o disco inteiro, pastas de rede ou pastas protegidas da aplicação. "',"typo")

b=one(b,'from guided_steps import build_steps, next_action, completed_local_count',
      'from guided_steps import build_steps, next_action, completed_local_count\n'
      'from connection_doctor import check_current_local_engine',"doctor import")
b=one(b,'        self._pwsh_results = queue.Queue()\n        self._pwsh_worker = None',
      '''        self._pwsh_results = queue.Queue()
        self._pwsh_worker = None
        self._engine_results = queue.Queue()
        self._engine_worker = None
        self._engine_status = "A verificação local vai começar automaticamente."''',
      "worker state")
b=one(b,'        self.after(2800, self._heartbeat)',
      '        self.after(1100, self._test_engine_local)\n        self.after(2800, self._heartbeat)',"auto test schedule")
b=one(b,'''        self._label(state,"A ligação remota ao ChatGPT é verificada separadamente. "
                    "Não damos acesso sem tua autorização.",
                    10,MUTED,wraplength=625).pack(anchor="w")''',
'''        self._label(state,"A ligação remota ao ChatGPT é verificada separadamente. "
                    "Não damos acesso sem tua autorização.",
                    10,MUTED,wraplength=625).pack(anchor="w")
        self._engine_label=self._label(state,self._engine_status,10,ACCENT,wraplength=625)
        self._engine_label.pack(anchor="w",pady=(8,7))
        self._button(state,"Testar o motor local agora",self._test_engine_local).pack(anchor="w")''',
"guide local test")
b=one(b,'''        self._button(box,"Voltar ao guia",lambda:self.show("Guia")).pack(anchor="w",pady=(0,10))''',
'''        self._button(box,"Abrir ChatGPT (site oficial)",self._open_chatgpt).pack(anchor="w",pady=(0,9))
        self._button(box,"Testar o motor local",self._test_engine_local).pack(anchor="w",pady=(0,9))
        self._label(box,self._engine_status,10,MUTED,wraplength=630).pack(anchor="w",pady=(0,6))
        self._button(box,"Voltar ao guia",lambda:self.show("Guia")).pack(anchor="w",pady=(0,10))''',
"connect self check")
methods='''    def _open_chatgpt(self):
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
        self._update_engine_label()
        if self.page=="Conexões":
            self.show("Conexões")
        elif result.code not in {"READY"} and self.page=="Guia":
            self._last_issue=guidance("AGENT_MISSING" if result.code=="MISSING"
                                     else "UNKNOWN_ERROR")
        # An authenticated remote ChatGPT session is never inferred here.

'''
b=one(b,'    def _prepare_powershell(self, approved=False):',
      methods+'    def _prepare_powershell(self, approved=False):',"doctor UI handlers")
# Correct conceptual status: UI observes local engine, not trusted remote connection.
b=one(b,' + " · ligação remota por configurar" + suffix,',
      ' + " · ligação remota por confirmar" + suffix,',"local status accuracy")
# Only commit once all anchors have passed.
entry.write_text(a,encoding="utf-8")
gui.write_text(b,encoding="utf-8")
print("SIMPLIFIED_FIRST_RUN_AND_LOCAL_DOCTOR_PATCH_OK")
