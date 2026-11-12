"""User-initiated, verified portable PowerShell runtime setup for standalone Windows GUI."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys

def get_private_powershell_setup_path() -> Path:
    if getattr(sys,"frozen",False):
        base=Path(sys.executable).resolve().parent.parent / "scripts"
    else:
        base=Path(__file__).resolve().parent / "scripts"
    script=base / "Prepare-PowerShell.ps1"
    if not script.is_file():
        raise FileNotFoundError("O componente de preparação do PowerShell não está incluído. Repara a instalação.")
    return script

def install_private_powershell() -> Path:
    """Downloads and verifies the latest stable Microsoft runtime without modifying global PATH.

    Must be called only from an explicit user action, never during import or agent startup.
    """
    if os.name!="nt":
        raise OSError("Funcionalidade disponível apenas para Windows")
    script=get_private_powershell_setup_path()
    host=Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32"/"WindowsPowerShell"/"v1.0"/"powershell.exe"
    if not host.is_file():
        raise FileNotFoundError("Windows PowerShell de sistema não encontrado")
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    result=subprocess.run([str(host),"-NoProfile","-NonInteractive",
                           "-ExecutionPolicy","Bypass","-File",str(script)],
                          capture_output=True,text=True,errors="replace",
                          timeout=600,creationflags=flags,check=False)
    if result.returncode:
        # Error output can include local paths; only expose a bounded status summary.
        raise RuntimeError(f"Preparação do PowerShell falhou (código {result.returncode}). "
                           "Verifica ligação à Internet, assinatura Microsoft e antivirus.")
    match=re.search(r"(?m)^UNIVERSAL_REMOTE_PWSH_READY=(.+?)\s*$",result.stdout)
    if not match:
        raise RuntimeError("O instalador não confirmou o caminho final do PowerShell.")
    candidate=Path(match.group(1).strip())
    if not candidate.is_file() or candidate.name.lower()!="pwsh.exe":
        raise RuntimeError("O executável PowerShell final não foi verificado.")
    return candidate
