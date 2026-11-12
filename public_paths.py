"""Windows per-user state and first-run policy for a public Universal Remote install."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import tempfile

PRIVILEGED=("writes","shell","screen","input")

def product_home() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home()/"AppData"/"Local")
    return Path(base).resolve()/"UniversalRemote"

def config_path() -> Path:
    return product_home()/"config.json"

def default_workspace() -> Path:
    documents=Path.home()/"Documents"
    if documents.is_dir():
        return documents/"Universal Remote Workspace"
    return product_home()/"workspace"

def config_for_root(folder: str | Path, permissions: dict[str,bool] | None = None) -> dict:
    from remote_core import PolicyError, _is_link_or_junction, validate_windows_path
    if not isinstance(folder,(str,Path)):
        raise ValueError("Choose a Windows folder")
    original=Path(folder).expanduser()
    if not original.is_absolute():
        raise ValueError("A pasta tem de ter um caminho absoluto.")
    if str(original).startswith(("\\\\","//")):
        raise ValueError("Esta versão não permite partilhar pastas de rede.")
    if os.name == "nt":
        # Validate the original lexical path BEFORE resolve() can hide a reparse
        # point or strip an invalid Windows suffix/reserved DOS name.
        validate_windows_path(str(original))
    current=original
    while True:
        if current.exists() and _is_link_or_junction(current):
            raise PolicyError("Não é permitido selecionar pastas com atalhos NTFS ou junctions.")
        if current==current.parent:
            break
        current=current.parent
    directory=original.resolve()
    if str(directory)==directory.anchor:
        raise ValueError("Não é permitido partilhar o disco inteiro.")
    home=product_home()
    if home == directory or home.is_relative_to(directory):
        raise ValueError("A pasta de trabalho não pode conter os dados privados da aplicação.")
    if directory.exists() and not directory.is_dir():
        raise ValueError("The selected path is not a directory")
    policy={key:False for key in PRIVILEGED}
    if permissions is not None:
        if set(permissions)-set(PRIVILEGED) or any(type(v) is not bool for v in permissions.values()):
            raise ValueError("Unsupported capability selection")
        policy.update(permissions)
    return {
        "allowed_roots":[str(directory)],
        "backup_root":str(home/"backups"),
        "grants_path":str(home/"grants.json"),
        "max_command_seconds":30,
        "max_read_bytes":65536,
        "max_write_bytes":1048576,
        **{"enable_"+key:value for key,value in policy.items()},
    }

def write_initial_config(folder: str | Path, permissions: dict[str,bool] | None = None) -> Path:
    """Exclusive, atomic first-run configuration. No consent grant is ever created."""
    from remote_core import load_config
    record=config_for_root(folder,permissions)
    target=config_path()
    if target.exists():
        raise FileExistsError("Configuration already exists; explicit repair required")
    workspace=Path(record["allowed_roots"][0])
    workspace.mkdir(parents=True,exist_ok=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(record,ensure_ascii=False,indent=2)+"\n"
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=target.parent,
                                     prefix=".init-",suffix=".tmp",delete=False) as f:
        candidate=Path(f.name)
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    try:
        # Validate the staging file BEFORE making anything visible. The same-
        # volume NTFS hardlink is an atomic no-clobber publish; open("x") would
        # expose a partially written config to a competing application.
        load_config(candidate)
        os.link(candidate,target)
    finally:
        candidate.unlink(missing_ok=True)
    return target
