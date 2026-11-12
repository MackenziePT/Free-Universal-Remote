"""Guided UX decision model; factual, read-only and independent of tkinter.

Never infer remote authentication or private tunnel state from an installed
agent, loopback server, a previously viewed screen or a manually ticked box.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class GuideStep:
    number: int
    title: str
    summary: str
    detail: str
    state: str
    button: str
    destination: str


def build_steps(checks: Iterable[object], local_agent: bool, engine_health: str | None = None) -> tuple[GuideStep, ...]:
    by_key = {getattr(row, "key", ""): bool(getattr(row, "ok", False))
              for row in checks}
    files_ok = by_key.get("runtime", False) and by_key.get("agent", False) and local_agent
    engine = files_ok and engine_health == "READY"
    verifying = files_ok and engine_health is None
    configured = by_key.get("config", False)
    return (
        GuideStep(1, "A aplicação está pronta",
                  ("O motor respondeu corretamente." if engine else
                   "A verificar o motor local..." if verifying else
                   "O motor local precisa de atenção."),
                  ("Os testes locais passaram. Falta confirmar a ligação ao ChatGPT."
                   if engine else
                   "A verificação automática está a decorrer. Podes continuar a explorar."
                   if verifying else
                   "Abre Ajuda ou volta a testar o motor para obter o próximo passo."),
                  "done" if engine else ("pending" if verifying else "action"),
                  "Verificar novamente" if engine or verifying else "Resolver instalação",
                  "Ajuda"),
        GuideStep(2, "A tua pasta de trabalho",
                  "Pasta autorizada na configuração inicial." if configured else
                  "Ainda não foi escolhida uma pasta de trabalho.",
                  "A aplicação limita os ficheiros acessíveis às pastas que autorizaste."
                  if configured else
                  "Conclui a configuração inicial para escolher apenas a pasta de que precisas.",
                  "done" if configured else "action",
                  "Ver explicação" if configured else "Resolver configuração", "Ajuda"),
        GuideStep(3, "Ligar à tua IA",
                  "Ligação remota por confirmar.",
                  "Para ChatGPT, confirma o emparelhamento no serviço; para outra IA, "
                  "segue as instruções do cliente MCP. Não vamos abrir portas do router.",
                  "pending", "Mostrar como ligar", "Conexões"),
        GuideStep(4, "Experimentar e continuar",
                  "Teste de ligação no próprio assistente.",
                  "Depois de associares o Universal Remote no ChatGPT, pede-lhe para "
                  "verificar o agente. Este ecrã não consegue confirmar sozinho uma sessão remota.",
                  "pending", "Ver ligações", "Conexões"),
    )


def next_action(steps: tuple[GuideStep, ...]) -> GuideStep:
    for step in steps:
        if step.state == "action":
            return step
    if steps[0].state == "pending":
        return steps[0]
    return steps[2]


def completed_local_count(steps: tuple[GuideStep, ...]) -> int:
    return sum(step.state == "done" for step in steps[:2])
