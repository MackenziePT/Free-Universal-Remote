"""Private, per-user Secure MCP Tunnel setup and supervised reconnection.

The Windows owner's explicit consent is required to configure/start this tunnel.
Tokens are protected with Windows DPAPI for CurrentUser. The external tunnel
client is pinned by SHA-256. No public inbound port is opened here.

Only local process status is reported; NEVER claim a ChatGPT login/connection.
The official ChatGPT plugin authorization is a separate required user action.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time


CLIENT_SHA256="4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571"
PROFILE_NAME="universal-remote-preview"
MAX_ATTEMPTS=8

class TunnelConfigError(ValueError):
    pass

class _Blob(ctypes.Structure):
    _fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]

def _protect_windows(value: bytes, *, decrypt: bool=False) -> bytes:
    if os.name!="nt":
        raise TunnelConfigError("Credenciais protegidas apenas no Windows")
    crypt=ctypes.windll.crypt32
    kernel=ctypes.windll.kernel32
    input_buffer=ctypes.create_string_buffer(value,len(value))
    incoming=_Blob(len(value),ctypes.cast(input_buffer,ctypes.POINTER(ctypes.c_ubyte)))
    outgoing=_Blob()
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=([ctypes.POINTER(_Blob),ctypes.c_void_p,
                  ctypes.POINTER(_Blob),ctypes.c_void_p,ctypes.c_void_p,
                  wintypes.DWORD,ctypes.POINTER(_Blob)] if not decrypt else
                  [ctypes.POINTER(_Blob),ctypes.c_void_p,
                   ctypes.POINTER(_Blob),ctypes.c_void_p,ctypes.c_void_p,
                   wintypes.DWORD,ctypes.POINTER(_Blob)])
    fn.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    if not fn(ctypes.byref(incoming),None,None,None,None,0,ctypes.byref(outgoing)):
        raise TunnelConfigError("O Windows não conseguiu proteger a chave da ligação")
    try:
        return ctypes.string_at(outgoing.data,outgoing.size)
    finally:
        kernel.LocalFree(ctypes.cast(outgoing.data,ctypes.c_void_p))

def _atomic_bytes(file: Path, payload: bytes) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb",dir=file.parent,prefix=".ur-tunnel-",
                                     suffix=".tmp",delete=False) as handle:
        temp=Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp,file)
    finally:
        temp.unlink(missing_ok=True)

def store_private_key(state: Path, secret: str) -> None:
    if not isinstance(secret,str) or not 20 <= len(secret) <= 4096 or not re.fullmatch(r"sk-[A-Za-z0-9_-]+",secret):
        raise TunnelConfigError("A chave inserida não tem um formato válido")
    _atomic_bytes(Path(state)/"tunnel-key.dpapi",_protect_windows(secret.encode()))

def load_private_key(state: Path) -> str:
    candidate=Path(state)/"tunnel-key.dpapi"
    if not candidate.is_file() or candidate.stat().st_size > 8192:
        raise TunnelConfigError("A chave de ligação não está configurada")
    try:
        return _protect_windows(candidate.read_bytes(),decrypt=True).decode()
    except (UnicodeError, OSError, ValueError) as exc:
        raise TunnelConfigError("A chave guardada não está disponível nesta conta Windows") from exc

def verify_tunnel_client(file: Path) -> None:
    file=Path(file)
    if not file.is_file() or file.is_symlink() or file.stat().st_size!=22591488:
        raise TunnelConfigError("O cliente de túnel verificado não foi encontrado")
    with file.open("rb") as handle:
        if hashlib.file_digest(handle,"sha256").hexdigest()!=CLIENT_SHA256:
            raise TunnelConfigError("O cliente de túnel falhou a verificação de integridade")

def profile_path() -> Path:
    return Path.home()/".config"/"tunnel-client"/(PROFILE_NAME+".yaml")

def provision_profile(tunnel_id: str, secret: str, state: Path,
                      agent: Path, client: Path) -> Path:
    """Explicit owner action only. Keeps secret out of arguments, YAML and logs."""
    if not isinstance(tunnel_id,str) or not re.fullmatch(r"tunnel_[0-9a-f]{32}",tunnel_id):
        raise TunnelConfigError("Identificador do túnel inválido")
    if not isinstance(secret,str) or not re.fullmatch(r"sk-[A-Za-z0-9_-]{17,4093}",secret):
        raise TunnelConfigError("A chave inserida não tem um formato válido")
    agent=Path(agent)
    if not agent.is_file() or agent.is_symlink() or agent.name.lower()!="universalremoteagent-preview.exe":
        raise TunnelConfigError("O motor instalado não foi encontrado")
    verify_tunnel_client(client)
    state=Path(state)
    profile=profile_path()
    manifest=state/"tunnel-profile.json"
    if manifest.exists() or profile.exists():
        # Never overwrite a pre-existing profile or credential by surprise.
        if not manifest.is_file() or not profile.is_file():
            raise TunnelConfigError("Já existe uma configuração diferente. Abre a Ajuda.")
        record=json.loads(manifest.read_text(encoding="utf-8"))
        if (record.get("tunnel_id")!=tunnel_id or
            record.get("profile_sha256")!=hashlib.sha256(profile.read_bytes()).hexdigest()):
            raise TunnelConfigError("A ligação existente difere do pedido. Não foi alterada.")
        store_private_key(state,secret)
        return profile
    # Windows CreateProcess/Go CLI needs double-quoted paths, not POSIX shlex single quotes.
    command=subprocess.list2cmdline([str(agent)])
    args=[str(client),"init","--sample","sample_mcp_stdio_local",
          "--profile",PROFILE_NAME,"--tunnel-id",tunnel_id,
          "--mcp-command",command]
    try:
        result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,check=False,timeout=45,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise TunnelConfigError("Não foi possível preparar o túnel verificado") from exc
    # Fresh setup must be transactional: a generated, invalid profile cannot
    # permanently block the user from retrying the first-run wizard.
    try:
        if result.returncode or not profile.is_file():
            raise TunnelConfigError("O serviço não conseguiu criar a ligação privada")
        raw=profile.read_bytes()
        if len(raw)>16384 or tunnel_id.encode() not in raw or b"CONTROL_PLANE_API_KEY" not in raw or agent.name.encode() not in raw:
            raise TunnelConfigError("O perfil criado não passou na verificação de segurança")
        store_private_key(state,secret)
        _atomic_bytes(manifest,json.dumps({
            "format":1,"tunnel_id":tunnel_id,
            "profile_sha256":hashlib.sha256(raw).hexdigest(),
            "agent_name":agent.name
        },sort_keys=True).encode())
        return profile
    except Exception:
        if not manifest.is_file():
            profile.unlink(missing_ok=True)
        raise

def next_retry_seconds(failures: int, *,stable_seconds:float=0,
                       jitter=lambda: random.random()) -> int:
    if stable_seconds>=120:
        failures=1
    failures=max(1,int(failures))
    base=min(300,5*(2**min(failures-1,8)))
    # 0-20% jitter avoids synchronized reconnect storms.
    return min(360,base+int(base*0.2*max(0,min(1,float(jitter())))))

def write_status(state: Path, status: str, *, attempt: int=0,
                 retry_in:int=0) -> None:
    allowed={"STARTING","RUNNING_LOCAL","RETRYING","NEEDS_ATTENTION","STOPPED"}
    if status not in allowed:
        raise ValueError("Invalid tunnel state")
    _atomic_bytes(Path(state)/"tunnel-status.json",json.dumps({
        "state":status,"updated_at":int(time.time()),
        "attempt":max(0,int(attempt)),"retry_in":max(0,int(retry_in))
    },sort_keys=True).encode())

def summarize_transport(raw: dict) -> dict:
    if not isinstance(raw,dict):
        raw={}
    state=raw.get("state","")
    if not isinstance(raw.get("updated_at"),int) or abs(int(time.time())-raw["updated_at"])>30:
        state="UNKNOWN"
    meta={
      "RUNNING_LOCAL":("LOCAL_READY","O túnel está em execução neste PC; a ligação ao ChatGPT ainda não foi confirmada."),
      "RETRYING":("RECONNECTING","A tentar restabelecer a ligação privada, sem intervenção. A autenticação ChatGPT continua por confirmar."),
      "STARTING":("STARTING","A iniciar a ligação privada. A conta ChatGPT ainda não foi associada."),
      "NEEDS_ATTENTION":("ATTENTION","Falha persistente. A recuperação automática tenta novamente a intervalos longos; verifica a Internet e as credenciais."),
      "STOPPED":("STOPPED","Ligação privada parada. Podes iniciá-la quando quiseres."),
      "UNKNOWN":("UNKNOWN","Não há informação atual da ligação privada.")
    }
    code,detail=meta.get(state,meta["UNKNOWN"])
    return {"code":code,"detail":detail,"chatgpt_confirmed":False,
            "retry_in":raw.get("retry_in",0) if state in ("RETRYING","NEEDS_ATTENTION") else 0}

def read_status(state: Path) -> dict:
    status=Path(state)/"tunnel-status.json"
    if not status.is_file() or status.stat().st_size>2048:
        return summarize_transport({})
    try:
        return summarize_transport(json.loads(status.read_bytes()))
    except (ValueError,UnicodeError,OSError):
        return summarize_transport({})

def _acquire_lock(state: Path):
    """One user-owned persistent supervisor per local installation."""
    import msvcrt
    f=Path(state)/"tunnel.lock"
    f.parent.mkdir(parents=True,exist_ok=True)
    handle=f.open("a+b")
    handle.seek(0)
    handle.write(b"0")
    handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except OSError as exc:
        handle.close()
        raise TunnelConfigError("A ligação já está a ser supervisionada") from exc
    return handle

def _validate_provisioned(state: Path,client: Path,agent: Path)->Path:
    verify_tunnel_client(client)
    profile=profile_path()
    receipt=state/"tunnel-profile.json"
    if not profile.is_file() or not receipt.is_file() or not (state/"tunnel-key.dpapi").is_file():
        raise TunnelConfigError("Ligação ainda não configurada")
    record=json.loads(receipt.read_text(encoding="utf-8"))
    if (record.get("format")!=1 or record.get("agent_name")!=agent.name or
        record.get("profile_sha256")!=hashlib.sha256(profile.read_bytes()).hexdigest()):
        raise TunnelConfigError("Configuração do túnel foi alterada; inicia novamente a associação")
    return profile

def run_supervisor(state:Path,client:Path,agent:Path) -> int:
    """Blocking sidecar: bounded retry rate, owner stop, no unowned process access."""
    import msvcrt
    state=Path(state)
    handle=_acquire_lock(state)
    stop=state/"stop.request"
    stop.unlink(missing_ok=True)
    try:
        profile=_validate_provisioned(state,client,agent)
        secret=load_private_key(state)
        failures=0
        while not stop.is_file():
            write_status(state,"STARTING",attempt=failures)
            started=time.monotonic()
            env=dict(os.environ)
            env["CONTROL_PLANE_API_KEY"]=secret
            try:
                child=subprocess.Popen([str(client),"run","--profile-file",str(profile)],
                         cwd=str(client.parent),env=env,
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            except OSError:
                child=None
            finally:
                env.pop("CONTROL_PLANE_API_KEY",None)
            if child is not None:
                while child.poll() is None and not stop.is_file():
                    write_status(state,"RUNNING_LOCAL",attempt=failures)
                    time.sleep(2)
                if stop.is_file():
                    child.terminate()
                    try: child.wait(timeout=8)
                    except subprocess.TimeoutExpired: child.kill()
                stable=time.monotonic()-started
            else:
                stable=0
            if stop.is_file():
                break
            failures=1 if stable>=120 else min(MAX_ATTEMPTS,failures+1)
            if failures>=MAX_ATTEMPTS:
                # Low-frequency, owner-controlled self-healing after repeated
                # failures. Never spin or spawn multiple copies of the client.
                delay=900
                write_status(state,"NEEDS_ATTENTION",attempt=failures,retry_in=delay)
            else:
                delay=next_retry_seconds(failures,stable_seconds=stable)
                write_status(state,"RETRYING",attempt=failures,retry_in=delay)
            for remaining in range(delay,0,-1):
                if stop.is_file():break
                if remaining % 10 == 0:
                    # Keeps UI telemetry alive throughout long cooldowns.
                    state_name=("NEEDS_ATTENTION" if failures>=MAX_ATTEMPTS
                                else "RETRYING")
                    write_status(state,state_name,attempt=failures,
                                 retry_in=remaining)
                time.sleep(1)
        write_status(state,"STOPPED",attempt=failures)
        return 0
    except (TunnelConfigError,OSError,ValueError):
        write_status(state,"NEEDS_ATTENTION",attempt=0)
        return 4
    finally:
        stop.unlink(missing_ok=True)
        handle.seek(0)
        msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        handle.close()

def request_stop(state: Path)->None:
    _atomic_bytes(Path(state)/"stop.request",b"stop")

def is_provisioned(state: Path)->bool:
    return all((Path(state)/name).is_file()
               for name in ("tunnel-key.dpapi","tunnel-profile.json"))

def spawn_supervisor(executable: Path)->None:
    executable=Path(executable)
    if not executable.is_file():
        raise TunnelConfigError("O serviço de ligação não está instalado")
    flags=(getattr(subprocess,"CREATE_NO_WINDOW",0) |
           getattr(subprocess,"DETACHED_PROCESS",0) |
           getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
    try:
        subprocess.Popen([str(executable),"run"],cwd=str(executable.parent),
             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
             creationflags=flags,close_fds=True)
    except OSError as exc:
        raise TunnelConfigError("O Windows não conseguiu iniciar a ligação") from exc

RUN_ENTRY="UniversalRemoteTunnelPreview"

def set_autostart(executable: Path, enabled: bool) -> None:
    """Explicit HKCU startup preference only; never touch other entries."""
    if os.name!="nt":
        raise TunnelConfigError("Arranque automático disponível apenas no Windows")
    import winreg
    exe=Path(executable).resolve()
    if exe.name.lower()!="universalremotetunnel-preview.exe" or not exe.is_file():
        raise TunnelConfigError("O serviço instalado não está disponível")
    command=f'"{exe}" run'
    location=r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,location,0,
                            winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE) as key:
        try:
            previous,_=winreg.QueryValueEx(key,RUN_ENTRY)
        except FileNotFoundError:
            previous=None
        if previous is not None and previous!=command:
            raise TunnelConfigError("Existe uma preferência de arranque diferente; não foi substituída")
        if enabled:
            winreg.SetValueEx(key,RUN_ENTRY,0,winreg.REG_SZ,command)
        elif previous==command:
            winreg.DeleteValue(key,RUN_ENTRY)

def autostart_enabled(executable: Path)->bool:
    if os.name!="nt":
        return False
    import winreg
    expected=f'"{Path(executable).resolve()}" run'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            value,_=winreg.QueryValueEx(key,RUN_ENTRY)
        return value==expected
    except OSError:
        return False
