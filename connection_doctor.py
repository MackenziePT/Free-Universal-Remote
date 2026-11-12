"""Safe local engine verification. Never tests or asserts ChatGPT remote auth."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys

@dataclass(frozen=True)
class EngineResult:
    code: str
    title: str
    detail: str

def check_local_engine(*, agent: Path, python_exe: Path | None = None,
                       configured: bool = True, timeout: int = 18) -> EngineResult:
    """Probe a known, on-disk agent only; no shell, elevation, writes or network."""
    if not configured:
        return EngineResult("SETUP", "Falta concluir a primeira configuração",
                            "Escolhe uma pasta de trabalho para ativar o motor local.")
    agent=Path(agent)
    if not agent.is_file():
        return EngineResult("MISSING", "O motor de ligação não foi encontrado",
                            "Abre a Ajuda para reparar a instalação.")
    command=[str(python_exe), str(agent)] if python_exe else [str(agent)]
    flags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # A health probe validates packaged imports and the executable. A version
        # probe separately confirms the app's local policy can be loaded.
        health=subprocess.run(command+["--health-probe"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              creationflags=flags, timeout=timeout, check=False)
        if health.returncode or b"UNIVERSAL_REMOTE_AGENT_HEALTH_OK" not in health.stdout:
            return EngineResult("ERROR", "O motor não conseguiu iniciar",
                                "A aplicação está instalada, mas precisa de reparação.")
        version=subprocess.run(command+["--version"],stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                               creationflags=flags,timeout=timeout,check=False)
        if version.returncode or b"Universal Remote MCP" not in version.stdout:
            return EngineResult("ERROR", "A configuração local não foi validada",
                                "Abre a Ajuda, verifica a configuração e volta a tentar.")
        return EngineResult("READY", "O motor local está a funcionar",
                            "O teste local passou. Ainda falta confirmar a ligação à tua IA.")
    except subprocess.TimeoutExpired:
        return EngineResult("TIMEOUT", "A verificação demorou demasiado",
                            "Podes tentar novamente. Se continuar, abre a Ajuda.")
    except (OSError, ValueError):
        return EngineResult("BLOCKED", "O Windows impediu a verificação",
                            "Consulta a Ajuda; não desatives o antivírus nem a firewall.")

def check_current_local_engine() -> EngineResult:
    from public_paths import config_path
    configured=config_path().is_file()
    if getattr(sys,"frozen",False):
        agent=Path(sys.executable).resolve().parent.parent/"Agent"/"UniversalRemoteAgent-Preview.exe"
        return check_local_engine(agent=agent,configured=configured)
    return check_local_engine(agent=Path(__file__).resolve().parent/"public_agent.py",
                              python_exe=Path(sys.executable),configured=configured)
