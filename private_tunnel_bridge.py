"""Private tunnel MCP bridge: authenticated transport -> signed RC5.1 device identity.

Never open a listening port. This is an owner-enrolled local gateway for the
existing authenticated OpenAI Secure MCP Tunnel only. Remote requests get a
fresh Ed25519 signature that the normal secure_gateway verifies. Windows grants
remain mandatory for privileged actions.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from device_pairing import (
    PairingError, PairingRegistry, TOOL_SCOPES,
    client_signature_message, pairing_signature_message,
)
from public_paths import product_home, config_path
from tunnel_manager import _protect_windows, verify_tunnel_client

BRIDGE_NAME = "Universal Remote: private owner tunnel"
KEY_FILENAME = "private-tunnel-identity.dpapi"
INFO_FILENAME = "private-tunnel-identity.json"


def _atomic_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmpname = tempfile.mkstemp(prefix=".bridge-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if path.exists():
            raise FileExistsError("A bridge identity already exists; no overwrite")
        os.replace(tmpname, path)
    finally:
        Path(tmpname).unlink(missing_ok=True)


def _paths() -> tuple[Path, Path, Path]:
    state = product_home() / "security"
    return state, state / KEY_FILENAME, state / INFO_FILENAME


def _load_identity() -> tuple[Ed25519PrivateKey, str]:
    state, keypath, infopath = _paths()
    if not keypath.is_file() or not infopath.is_file():
        raise PairingError("Private tunnel bridge needs local owner enrollment")
    seed = _protect_windows(keypath.read_bytes(), decrypt=True)
    if len(seed) != 32:
        raise PairingError("Invalid local bridge private key")
    identity = Ed25519PrivateKey.from_private_bytes(seed)
    record = json.loads(infopath.read_text(encoding="utf-8"))
    if set(record) != {"format", "client_id", "public_fingerprint"} or record["format"] != 1:
        raise PairingError("Unrecognized private tunnel identity record")
    public = identity.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    fp = hashlib.sha256(public).hexdigest()[:16]
    if fp != record["public_fingerprint"]:
        raise PairingError("Private tunnel device identity mismatch")
    registry = PairingRegistry(state)
    records = registry.list_devices_local()
    approved = next((r for r in records if r["client_id"] == record["client_id"]), None)
    if not approved or approved["revoked"] is not None or approved["fingerprint"] != fp:
        raise PairingError("Tunnel device is not locally approved or was revoked")
    return identity, record["client_id"]


def enroll_with_local_confirmation() -> int:
    if os.name != "nt":
        return 4
    state, keypath, infopath = _paths()
    if keypath.exists() or infopath.exists():
        _load_identity()
        print("PRIVATE_TUNNEL_BRIDGE_ALREADY_ENROLLED")
        return 0
    import ctypes
    caption = "Universal Remote - ligar o ChatGPT"
    message = (
        "Autorizar o canal privado do ChatGPT a comunicar com o Universal Remote RC5.1?\n\n"
        "Este computador será associado a um dispositivo local com assinatura Ed25519.\n"
        "O acesso a ficheiros fica limitado às pastas configuradas.\n"
        "Alterações, PowerShell, ecrã e teclado continuam sujeitos a autorizações\n"
        "temporárias locais e podem ser revogados na aplicação.\n\n"
        "Escolhe SIM para emparelhar, ou NAO para manter a configuração atual.")
    answer = ctypes.windll.user32.MessageBoxW(None, message, caption, 0x00000004 | 0x00000020 | 0x00000100 | 0x00040000)
    if answer != 6:
        print("PRIVATE_TUNNEL_BRIDGE_NOT_APPROVED")
        return 3
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    registry = PairingRegistry(state)
    pending = registry.begin(base64.b64encode(public).decode("ascii"), BRIDGE_NAME)
    signature = private.sign(pairing_signature_message(
        pending["request_id"], pending["challenge"]))
    registry.finish(pending["request_id"], base64.b64encode(signature).decode("ascii"))
    granted = registry.approve_local(pending["request_id"],
                                     {"read", "writes", "shell", "screen", "input"},
                                     presence_confirmed=True)
    seed = private.private_bytes(serialization.Encoding.Raw,
                                 serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption())
    try:
        _atomic_private(keypath, _protect_windows(seed))
        info = {"format": 1, "client_id": granted["client_id"],
                "public_fingerprint": hashlib.sha256(public).hexdigest()[:16]}
        _atomic_private(infopath, json.dumps(info, sort_keys=True).encode("utf-8"))
    except Exception:
        registry.revoke_local(granted["client_id"])
        raise
    _load_identity()
    print("PRIVATE_TUNNEL_BRIDGE_LOCAL_APPROVAL_COMPLETE")
    return 0


def _transport_verified() -> bool:
    # This process must be spawned by the pinned official client with a
    # private control-plane credential in its environment. Local shell callers
    # and unrelated processes are rejected. No secret is ever logged.
    if not os.environ.get("CONTROL_PLANE_API_KEY", "").startswith("sk-"):
        return False
    try:
        import psutil
        parent = psutil.Process(os.getpid()).parent()
        for _ in range(7):
            if parent is None:
                break
            if parent.name().casefold() == "tunnel-client.exe":
                verify_tunnel_client(Path(parent.exe()))
                return True
            parent = parent.parent()
    except Exception:
        return False
    return False


def configure_signed_private_tunnel(mcp, identity: Ed25519PrivateKey, client_id: str) -> None:
    from secure_gateway import attach_secure_gateway
    state, _, _ = _paths()
    attach_secure_gateway(mcp, state)
    manager = mcp._tool_manager
    checked_call = manager.call_tool
    all_tools = manager.list_tools

    async def bridge_checked_call(name, arguments, context=None, convert_result=False):
        if name not in TOOL_SCOPES or name in ("pairing_begin", "pairing_finish"):
            raise PairingError("Tool is unavailable through the private tunnel")
        if not isinstance(arguments, dict):
            raise PairingError("Invalid MCP tool arguments")
        clean = dict(arguments)
        # A remote caller may not substitute its own identity or replay proof.
        if "device_proof" in clean:
            raise PairingError("Bridge prohibits caller-supplied device proof")
        if TOOL_SCOPES[name] is not None:
            nonce = str(uuid.uuid4())
            timestamp = int(time.time())
            message = client_signature_message(client_id, name, clean, nonce, timestamp)
            clean["device_proof"] = {
                "client_id": client_id, "nonce": nonce, "timestamp": timestamp,
                "signature": base64.b64encode(identity.sign(message)).decode("ascii"),
            }
        return await checked_call(name, clean, context=context,
                                  convert_result=convert_result)

    def bridge_list_tools():
        result = []
        for source in all_tools():
            if source.name in ("pairing_begin", "pairing_finish"):
                continue
            view = copy.deepcopy(source)
            view.parameters.get("properties", {}).pop("device_proof", None)
            result.append(view)
        return result

    manager.call_tool = bridge_checked_call
    manager.list_tools = bridge_list_tools


def main() -> int:
    if sys.argv[1:] == ["--health-probe"]:
        import mcp, psutil
        from cryptography.hazmat.primitives.asymmetric import ed25519
        print("UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK")
        return 0
    if sys.argv[1:] == ["--enroll"]:
        return enroll_with_local_confirmation()
    if sys.argv[1:]:
        return 2
    if not _transport_verified():
        print("Trusted private tunnel transport not verified", file=sys.stderr)
        return 14
    identity, client_id = _load_identity()
    policy = config_path()
    if not policy.is_file():
        print("Universal Remote local configuration is missing", file=sys.stderr)
        return 12
    os.environ["HARMONY_MCP_CONFIG"] = str(policy)
    os.environ["UNIVERSAL_REMOTE_DATA_HOME"] = str(product_home())
    os.environ.pop("CONTROL_PLANE_API_KEY", None)
    from server import mcp
    configure_signed_private_tunnel(mcp, identity, client_id)
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PairingError, ValueError, OSError) as exc:
        print("Universal Remote bridge cannot start: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(14)
