"""Local-approved Ed25519 device registry and per-call anti-replay verification.

The server never receives a client private key. Local approval MUST be invoked
through a trusted local UI with user presence, never exposed as an MCP action.
Remote control of an already unlocked desktop can undermine UI-only approvals:
Windows Hello / independent presence is an additional PUBLIC security gate.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class PairingError(PermissionError):
    pass


SCOPES = frozenset({"read", "writes", "shell", "screen", "input"})
TOOL_SCOPES = {
    "ping": None,
    "product_capabilities": None,
    "pairing_begin": None,
    "pairing_finish": None,
    "agent_policy": "read",
    "get_system_metrics": "read",
    "list_processes": "read",
    "windows_diagnostic": "read",
    "browse_directory": "read",
    "search_files": "read",
    "read_text_file": "read",
    "read_binary_chunk": "read",
    "inspect_file": "read",
    "check_operation": "read",
    "list_tasks": "shell",
    "task_status": "shell",
    "task_output": "shell",
    "list_windows": "screen",
    "desktop_screenshot": "screen",
    "write_text_file": "writes",
    "create_folder": "writes",
    "copy_file": "writes",
    "move_file": "writes",
    "recycle_file": "writes",
    "run_powershell": "shell",
    "start_task": "shell",
    "stop_task": "shell",
    "focus_window": "input",
    "desktop_action": "input",
}


def _canonical(data: dict) -> bytes:
    try:
        return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PairingError("Invalid proof content") from exc


def _decode(value: str, n: int) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise PairingError("Invalid base64") from exc
    if len(raw) != n:
        raise PairingError("Invalid public key or signature size")
    return raw


def _uuid4(value: str) -> str:
    try:
        identifier = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise PairingError("Invalid request identifier") from exc
    if identifier.version != 4 or str(identifier) != value:
        raise PairingError("Identifier must be canonical UUIDv4")
    return value


def _check_label(label: str) -> str:
    if not isinstance(label, str) or not 1 <= len(label) <= 48 or any(ord(x) < 32 for x in label):
        raise PairingError("Invalid device label")
    return label


def client_signature_message(client_id: str, method: str,
                             arguments: dict, nonce: str, timestamp: int) -> bytes:
    """Canonical domain-separated message; callers sign these exact bytes."""
    if not isinstance(arguments, dict) or not isinstance(method, str):
        raise PairingError("Invalid signed arguments")
    return _canonical({
        "domain": "universal-remote-call/v1",
        "client_id": client_id,
        "method": method,
        "params_sha256": hashlib.sha256(_canonical(arguments)).hexdigest(),
        "nonce": nonce,
        "timestamp": timestamp,
    })


def pairing_signature_message(request_id: str, challenge_b64: str) -> bytes:
    return _canonical({"domain": "universal-remote-pair/v1",
                       "request_id": request_id, "challenge": challenge_b64})


class PairingRegistry:
    def __init__(self, folder: Path, *, clock=time.time):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db = self.folder / "devices.sqlite3"
        self.clock = clock
        self._initialize()

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(str(self.db), timeout=8, isolation_level=None)
        try:
            con.execute("PRAGMA busy_timeout=8000")
            con.execute("PRAGMA foreign_keys=ON")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def _initialize(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS pending (
                request_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                public_key TEXT NOT NULL,
                challenge TEXT NOT NULL,
                created INTEGER NOT NULL,
                expires INTEGER NOT NULL,
                proved INTEGER NOT NULL DEFAULT 0
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS devices (
                client_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                public_key TEXT NOT NULL UNIQUE,
                scopes TEXT NOT NULL,
                approved INTEGER NOT NULL,
                revoked INTEGER
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS used_nonces (
                client_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                seen INTEGER NOT NULL,
                PRIMARY KEY (client_id, nonce),
                FOREIGN KEY (client_id) REFERENCES devices(client_id)
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS ix_used_nonces_seen ON used_nonces(seen)")

    def begin(self, public_key: str, label: str) -> dict:
        _decode(public_key, 32)
        _check_label(label)
        now = int(self.clock())
        request_id = str(uuid.uuid4())
        challenge = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM pending WHERE expires < ?", (now,))
            if con.execute("SELECT COUNT(*) FROM pending").fetchone()[0] >= 5:
                raise PairingError("Too many pending pairing requests")
            if con.execute("SELECT 1 FROM devices WHERE public_key=?", (public_key,)).fetchone():
                raise PairingError("Device key already known; rotate through local management")
            con.execute("INSERT INTO pending(request_id,label,public_key,challenge,created,expires) "
                        "VALUES(?,?,?,?,?,?)", (request_id,label,public_key,challenge,now,now+120))
        return {"request_id": request_id, "challenge": challenge,
                "expires_at": now + 120, "fingerprint": hashlib.sha256(_decode(public_key,32)).hexdigest()[:16]}

    def finish(self, request_id: str, signature: str) -> dict:
        _uuid4(request_id)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            record = con.execute("SELECT public_key,challenge,expires,proved FROM pending "
                                 "WHERE request_id=?", (request_id,)).fetchone()
            if record is None or record[2] < int(self.clock()):
                raise PairingError("Pairing request missing or expired")
            if record[3]:
                raise PairingError("Pairing proof already submitted")
            try:
                Ed25519PublicKey.from_public_bytes(_decode(record[0],32)).verify(
                    _decode(signature,64), pairing_signature_message(request_id,record[1]))
            except (InvalidSignature, ValueError) as exc:
                raise PairingError("Device possession proof invalid") from exc
            con.execute("UPDATE pending SET proved=1 WHERE request_id=?", (request_id,))
        return {"status": "pending_local_approval", "request_id": request_id}

    def list_pending_local(self) -> list[dict]:
        now = int(self.clock())
        with self._connect() as con:
            rows=con.execute("SELECT request_id,label,public_key,expires,proved FROM pending "
                             "WHERE expires >= ? ORDER BY created", (now,)).fetchall()
        return [{"request_id":row[0],"label":row[1],
                 "fingerprint":hashlib.sha256(_decode(row[2],32)).hexdigest()[:16],
                 "expires_at":row[3],"proved":bool(row[4])} for row in rows]

    def approve_local(self, request_id: str, scopes: set[str], *,
                      presence_confirmed: bool = False) -> dict:
        """Never expose this method via MCP; caller MUST verify local user presence."""
        _uuid4(request_id)
        if presence_confirmed is not True:
            raise PairingError("Local user presence required")
        if not scopes or not scopes.issubset(SCOPES):
            raise PairingError("Invalid approval scopes")
        now = int(self.clock())
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT label,public_key,expires,proved FROM pending "
                              "WHERE request_id=?", (request_id,)).fetchone()
            if not row or row[2] < now or not row[3]:
                raise PairingError("Unproved, missing or expired request")
            if con.execute("SELECT 1 FROM devices WHERE public_key=?", (row[1],)).fetchone():
                raise PairingError("Device key was already enrolled")
            client_id = str(uuid.uuid4())
            con.execute("INSERT INTO devices(client_id,label,public_key,scopes,approved,revoked) "
                        "VALUES (?,?,?,?,?,NULL)",
                        (client_id,row[0],row[1],json.dumps(sorted(scopes)),now))
            con.execute("DELETE FROM pending WHERE request_id=?", (request_id,))
        return {"client_id": client_id, "scopes": sorted(scopes)}

    def list_devices_local(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("SELECT client_id,label,public_key,scopes,approved,revoked "
                               "FROM devices ORDER BY approved").fetchall()
        return [{"client_id":r[0], "label":r[1], "fingerprint":
                 hashlib.sha256(_decode(r[2],32)).hexdigest()[:16],
                 "scopes":json.loads(r[3]),"approved":r[4],"revoked":r[5]} for r in rows]

    def revoke_local(self, client_id: str) -> None:
        _uuid4(client_id)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("UPDATE devices SET revoked=coalesce(revoked,?) "
                           "WHERE client_id=?", (int(self.clock()),client_id)).rowcount != 1:
                raise PairingError("Unknown client")

    def verify_call(self, method: str, arguments: dict, proof: dict) -> None:
        if method not in TOOL_SCOPES:
            raise PairingError("Unknown tool denied")
        scope = TOOL_SCOPES[method]
        if scope is None:
            return
        if not isinstance(proof, dict) or set(proof) != {
                "client_id","nonce","timestamp","signature"}:
            raise PairingError("Signed device proof required")
        client_id = _uuid4(proof["client_id"])
        nonce = _uuid4(proof["nonce"])
        timestamp = proof["timestamp"]
        now = int(self.clock())
        if type(timestamp) is not int or abs(now - timestamp) > 60:
            raise PairingError("Expired or future-dated signed call")
        message = client_signature_message(client_id,method,arguments,nonce,timestamp)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT public_key,scopes,revoked FROM devices "
                              "WHERE client_id=?", (client_id,)).fetchone()
            if row is None or row[2] is not None:
                raise PairingError("Device not authorized or revoked")
            if scope not in json.loads(row[1]):
                raise PairingError("Device lacks required capability")
            try:
                Ed25519PublicKey.from_public_bytes(_decode(row[0],32)).verify(
                    _decode(proof["signature"],64),message)
            except (InvalidSignature, ValueError) as exc:
                raise PairingError("Invalid signed request") from exc
            if con.execute("SELECT 1 FROM used_nonces WHERE client_id=? AND nonce=?",
                           (client_id,nonce)).fetchone():
                raise PairingError("Replay rejected")
            con.execute("INSERT INTO used_nonces(client_id,nonce,seen) VALUES(?,?,?)",
                        (client_id,nonce,now))
            con.execute("DELETE FROM used_nonces WHERE seen < ?",(now-3600,))
