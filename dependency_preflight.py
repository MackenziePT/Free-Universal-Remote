"""Dependency readiness for the Windows public application.

The user-facing binaries are self-contained: never request system Python/pip.
Optional PowerShell 7 can be provisioned into the private app directory only
after a visible user action. This module never downloads or changes the machine.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


BUNDLED_PYTHON_FILES = (
    "python314.dll",
    "python3.dll",
    "base_library.zip",
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
    "ucrtbase.dll",
)


@dataclass(frozen=True)
class Readiness:
    key: str
    title: str
    ok: bool
    required: bool
    detail: str


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent / "_internal"))
    return Path(sys.executable).parent


def bundled_runtime_check() -> Readiness:
    """Enforce frozen-runtime completeness; it is NOT an Authenticode check."""
    if not getattr(sys, "frozen", False):
        return Readiness("runtime", "Motor da aplicação", True, True,
                         "Ambiente de desenvolvimento; Python incluído no futuro executável.")
    base = runtime_dir()
    missing = [name for name in BUNDLED_PYTHON_FILES if not (base / name).is_file()]
    if missing:
        return Readiness("runtime", "Motor da aplicação", False, True,
                         "Faltam ficheiros do programa: " + ", ".join(missing)
                         + ". Usa a opção Reparar no instalador.")
    return Readiness("runtime", "Motor da aplicação", True, True,
                     "Python e componentes Windows já incluídos. Não é necessária instalação separada.")


def local_agent_check() -> Readiness:
    if getattr(sys, "frozen", False):
        candidate = (Path(sys.executable).resolve().parent.parent /
                     "Agent" / "UniversalRemoteAgent-Preview.exe")
    else:
        candidate = Path(__file__).resolve().parent / "public_agent.py"
    if candidate.is_file():
        return Readiness("agent", "Ligação local a assistentes", True, True,
                         "Motor local instalado. Podes associar um assistente compatível.")
    return Readiness("agent", "Ligação local a assistentes", False, True,
                     "Falta o motor de ligação. Repara a instalação do Universal Remote.")


def configuration_check() -> Readiness:
    from public_paths import config_path
    if config_path().is_file():
        return Readiness("config", "Primeira configuração", True, True,
                         "A aplicação já tem uma pasta de trabalho configurada.")
    return Readiness("config", "Primeira configuração", False, False,
                     "Ainda não concluída; o assistente de configuração ajuda-te.")


def powershell_check() -> Readiness:
    """Optional: no system-wide updates, no shell execution or credentials."""
    private_base = Path(os.environ.get("LOCALAPPDATA",str(Path.home() / "AppData" / "Local"))) / (
        "UniversalRemote/runtime/powershell")
    candidates = []
    if private_base.is_dir():
        candidates.extend(folder / "pwsh.exe" for folder in private_base.iterdir() if folder.is_dir())
    env_program_files = os.environ.get("ProgramFiles")
    if env_program_files:
        install_root = Path(env_program_files) / "PowerShell"
        if install_root.is_dir():
            candidates.extend(
                folder / "pwsh.exe" for folder in install_root.iterdir()
                if folder.is_dir() and folder.name.isdecimal() and int(folder.name) >= 7
            )
    candidates.extend(Path(entry) / "pwsh.exe" for entry in os.environ.get("PATH", "").split(os.pathsep)
                      if entry)
    if any(path.is_file() for path in candidates):
        return Readiness("powershell", "Ferramentas PowerShell", True, False,
                         "PowerShell moderno encontrado. A assinatura será verificada antes de o utilizar.")
    return Readiness("powershell", "Ferramentas PowerShell", False, False,
                     "Opcional: pode ser preparado automaticamente pela aplicação quando precisares.")


def check_dependencies() -> list[Readiness]:
    return [
        bundled_runtime_check(),
        local_agent_check(),
        configuration_check(),
        powershell_check(),
    ]


def has_missing_required_dependencies(results: list[Readiness] | None = None) -> bool:
    rows = check_dependencies() if results is None else results
    return any(row.required and not row.ok for row in rows)
