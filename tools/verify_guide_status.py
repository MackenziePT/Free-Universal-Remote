"""Make the guide reflect verified local execution rather than file existence."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
m=r/"guided_steps.py"
g=r/"universal_remote_ui.py"
t=r/"tests"/"test_guided_steps.py"
s=m.read_text(encoding="utf-8")
u=g.read_text(encoding="utf-8")
v=t.read_text(encoding="utf-8")
def patch(source, old, new, label):
    if source.count(old)!=1:
        raise RuntimeError(f"Not a unique expected {label} anchor: {source.count(old)}")
    return source.replace(old,new,1)
s=patch(s, 'def build_steps(checks: Iterable[object], local_agent: bool) -> tuple[GuideStep, ...]:',
        'def build_steps(checks: Iterable[object], local_agent: bool, engine_health: str | None = None) -> tuple[GuideStep, ...]:',
        "signature")
s=patch(s,'''    engine = by_key.get("runtime", False) and by_key.get("agent", False) and local_agent
    configured = by_key.get("config", False)''',
'''    files_ok = by_key.get("runtime", False) and by_key.get("agent", False) and local_agent
    engine = files_ok and engine_health == "READY"
    verifying = files_ok and engine_health is None
    configured = by_key.get("config", False)''', "health states")
s=patch(s,
'''                  "Os componentes principais foram encontrados." if engine else
                  "Precisamos de reparar um componente da instalação.",
                  "O motor local está disponível. A ligação ao ChatGPT ainda não foi confirmada."
                  if engine else "Abre a Ajuda e segue os passos de reparação indicados.",
                  "done" if engine else "action",
                  "Verificar os componentes" if engine else "Resolver instalação",
                  "Ajuda"),''',
'''                  ("O motor respondeu corretamente." if engine else
                   "A verificar o motor local..." if verifying else
                   "O motor local precisa de atenção."),
                  ("Os testes locais passaram. Falta confirmar a ligação ao ChatGPT."
                   if engine else
                   "A verificação automática está a decorrer. Podes continuar a explorar."
                   if verifying else
                   "Abre Ajuda ou volta a testar o motor para obter o próximo passo."),
                  "done" if engine else ("pending" if verifying else "action"),
                  "Verificar novamente" if engine or verifying else "Resolver instalação",
                  "Ajuda"),''', "first step")
s=patch(s,
'''    for step in steps:
        if step.state == "action":
            return step
    return steps[2]''',
'''    for step in steps:
        if step.state == "action":
            return step
    if steps[0].state == "pending":
        return steps[0]
    return steps[2]''',"next step")
u=patch(u,
'''        self._engine_status = "A verificação local vai começar automaticamente."
        self.page = ""''',
'''        self._engine_status = "A verificação local vai começar automaticamente."
        self._engine_result_code = None
        self.page = ""''',"state")
old_steps='        steps = build_steps(check_dependencies(), local_agent_available())'
new_steps='''        steps = build_steps(check_dependencies(), local_agent_available(),
                            engine_health=self._engine_result_code)'''
if u.count(old_steps)!=2:
    raise RuntimeError("Expected exactly two guide/home step calls")
u=u.replace(old_steps,new_steps)
u=patch(u,
'''        self._engine_status=result.title+". "+result.detail
        self._update_engine_label()
        if self.page=="Conexões":
            self.show("Conexões")
        elif result.code not in {"READY"} and self.page=="Guia":
            self._last_issue=guidance("AGENT_MISSING" if result.code=="MISSING"
                                     else "UNKNOWN_ERROR")''',
'''        self._engine_status=result.title+". "+result.detail
        self._engine_result_code=result.code
        self._update_engine_label()
        if result.code != "READY":
            codes={"SETUP":"SETUP_INCOMPLETE","MISSING":"AGENT_MISSING",
                   "BLOCKED":"SECURITY_BLOCKED","TIMEOUT":"UNKNOWN_ERROR",
                   "ERROR":"UNKNOWN_ERROR"}
            self._last_issue=guidance(codes.get(result.code,"UNKNOWN_ERROR"))
        if self.page in {"Conexões","Guia","Início"}:
            self.show(self.page)''',"status and page refresh")
# Tests now require real evidence for the local engine ready state.
v=v.replace('build_steps(self.checks(),True)', 'build_steps(self.checks(),True,engine_health="READY")')
v=v.replace('build_steps(self.checks(runtime=False),True)',
            'build_steps(self.checks(runtime=False),True,engine_health="READY")')
v=v.replace('build_steps(self.checks(config=False),True)',
            'build_steps(self.checks(config=False),True,engine_health="READY")')
v=v.replace('build_steps(self.checks(),False)',
            'build_steps(self.checks(),False,engine_health="READY")')
before='    def test_no_optional_power_shell_dependency(self):'
extra='''    def test_no_unverified_local_health_is_ever_marked_ready(self):
        stages=build_steps(self.checks(),True)
        self.assertEqual(stages[0].state,"pending")
        self.assertEqual(completed_local_count(stages),1)
        self.assertEqual(next_action(stages).number,1)

    def test_runtime_failure_comes_before_remote_connection(self):
        stages=build_steps(self.checks(),True,engine_health="BLOCKED")
        self.assertEqual(stages[0].state,"action")
        self.assertEqual(next_action(stages).number,1)

'''
v=patch(v,before,extra+before,"additional tests")
m.write_text(s,encoding="utf-8")
g.write_text(u,encoding="utf-8")
t.write_text(v,encoding="utf-8")
print("VERIFIED_GUIDE_STATUS_FIX_COMPLETE")
