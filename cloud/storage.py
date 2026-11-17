"""Encrypted, single-replica SQLite job queue with strict ownership and expirations.

A production deployment must mount durable storage, protect UR_QUEUE_KEY in a sealed
secret, and use a single process/replica or migrate these transactions to PostgreSQL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from contextlib import contextmanager
import secrets
import sqlite3
import time
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Denied(PermissionError):
    pass


def encode_json(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True,
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


class Store:
    def __init__(self, db: Path, key: bytes, *, clock=time.time):
        if len(key) != 32:
            raise ValueError("UR_QUEUE_KEY requires 32 random bytes")
        self.db = Path(db)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.crypt = AESGCM(key)
        self.clock = clock
        self._init()

    @contextmanager
    def _connect(self):
        c = sqlite3.connect(self.db, timeout=8, isolation_level=None)
        c.execute("PRAGMA busy_timeout=8000")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def _init(self):
        with self._connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, label TEXT NOT NULL,
                    public_key BLOB NOT NULL UNIQUE, created INTEGER NOT NULL,
                    revoked INTEGER, last_seen INTEGER);
                CREATE INDEX IF NOT EXISTS devices_owner ON devices(owner,revoked);
                CREATE TABLE IF NOT EXISTS enrollment (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, challenge BLOB NOT NULL,
                    expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, device TEXT NOT NULL,
                    op TEXT NOT NULL, args BLOB NOT NULL, result BLOB,
                    status TEXT NOT NULL, created INTEGER NOT NULL,
                    expires INTEGER NOT NULL, lease INTEGER,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(device) REFERENCES devices(id));
                CREATE INDEX IF NOT EXISTS jobs_poll ON jobs(device,status,created);
                CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner,id);
                CREATE TABLE IF NOT EXISTS device_nonces (
                    device TEXT NOT NULL, nonce TEXT NOT NULL, seen INTEGER NOT NULL,
                    PRIMARY KEY(device,nonce), FOREIGN KEY(device) REFERENCES devices(id));
            """)

    def _seal(self, obj, aad: str):
        blob = encode_json(obj)
        limit = 2_000_000 if aad.startswith("result:") else 65536
        if len(blob) > limit:
            raise Denied("Payload too large")
        nonce = os.urandom(12)
        return nonce + self.crypt.encrypt(nonce, blob, aad.encode())

    def _open(self, blob, aad: str):
        if blob is None or len(blob) < 29:
            raise Denied("Corrupt encrypted payload")
        return json.loads(self.crypt.decrypt(blob[:12], blob[12:], aad.encode()))

    def begin_enrollment(self, owner):
        now = int(self.clock())
        ident = str(uuid.uuid4())
        challenge = secrets.token_bytes(32)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM enrollment WHERE expires < ?", (now,))
            if c.execute("SELECT COUNT(*) FROM enrollment WHERE owner=?", (owner,)).fetchone()[0] >= 5:
                raise Denied("Too many pending enrollment requests")
            c.execute("INSERT INTO enrollment VALUES(?,?,?,?)", (ident, owner, challenge, now + 120))
        return ident, challenge, now + 120

    def enroll(self, owner, enrollment_id, public_key, signature, label):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        if not isinstance(label, str) or not (1 <= len(label) <= 48) or any(ord(x) < 32 for x in label):
            raise Denied("Invalid label")
        if len(public_key) != 32 or len(signature) != 64:
            raise Denied("Invalid device key")
        now = int(self.clock())
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT challenge, expires FROM enrollment WHERE id=? AND owner=?",
                            (enrollment_id, owner)).fetchone()
            if not row or row[1] < now:
                raise Denied("Unknown or expired enrollment")
            import base64
            message = encode_json({"domain":"universal-remote-enroll/v1", "owner":owner,
                                   "id":enrollment_id,
                                   "challenge":base64.b64encode(row[0]).decode(),
                                   "public_key":base64.b64encode(public_key).decode()})
            try:
                Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            except InvalidSignature as exc:
                raise Denied("Device proof invalid") from exc
            ident = str(uuid.uuid4())
            try:
                c.execute("INSERT INTO devices(id,owner,label,public_key,created) VALUES(?,?,?,?,?)",
                          (ident,owner,label,public_key,now))
            except sqlite3.IntegrityError as exc:
                raise Denied("Device key already enrolled") from exc
            c.execute("DELETE FROM enrollment WHERE id=?", (enrollment_id,))
        return ident

    def find_device(self, owner, device):
        with self._connect() as c:
            row=c.execute("SELECT id,label,last_seen,revoked FROM devices WHERE owner=? AND id=?",
                          (owner, device)).fetchone()
        if not row or row[3] is not None:
            raise Denied("Device unavailable")
        return {"device_id":row[0],"label":row[1],"online":bool(row[2] and
                (int(self.clock())-row[2] < 70))}

    def list_devices(self, owner):
        with self._connect() as c:
            rows=c.execute("SELECT id,label,last_seen FROM devices WHERE owner=? AND revoked IS NULL ORDER BY created",
                           (owner,)).fetchall()
        now=int(self.clock())
        return [{"device_id":r[0],"label":r[1],"online":bool(r[2] and now-r[2]<70)} for r in rows]

    def revoke(self, owner, device):
        now=int(self.clock())
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            changed=c.execute("UPDATE devices SET revoked=? WHERE owner=? AND id=? AND revoked IS NULL",
                              (now,owner,device)).rowcount
            if not changed:
                raise Denied("Device unavailable")
            c.execute("UPDATE jobs SET status='revoked', args=X'', result=NULL WHERE device=? AND status IN ('queued','leased')",(device,))

    def submit(self, owner, device, operation, args):
        now=int(self.clock())
        ident=str(uuid.uuid4())
        encrypted=self._seal(args,"args:"+ident)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM devices WHERE id=? AND owner=? AND revoked IS NULL",
                             (device,owner)).fetchone():
                raise Denied("Device unavailable")
            count=c.execute("SELECT COUNT(*) FROM jobs WHERE owner=? AND status IN ('queued','leased') AND expires>=?",(owner,now)).fetchone()[0]
            if count>=25:
                raise Denied("Queue full")
            c.execute("INSERT INTO jobs(id,owner,device,op,args,status,created,expires) VALUES(?,?,?,?,?,?,?,?)",
                      (ident,owner,device,operation,encrypted,'queued',now,now+300))
        return ident

    def operation(self, owner, ident):
        with self._connect() as c:
            r=c.execute("SELECT status,result,expires FROM jobs WHERE id=? AND owner=?",(ident,owner)).fetchone()
        if not r:
            raise Denied("Operation unavailable")
        if r[2] < int(self.clock()) and r[0] not in ('done','failed','revoked'):
            return {"operation_id":ident,"status":"expired"}
        ans={"operation_id":ident,"status":r[0]}
        if r[1] is not None:
            ans["result"]=self._open(r[1],"result:"+ident)
        return ans

    def get_public_key(self, device):
        with self._connect() as c:
            r=c.execute("SELECT public_key FROM devices WHERE id=? AND revoked IS NULL",(device,)).fetchone()
        if not r:
            raise Denied("Device unavailable")
        return r[0]

    def accept_nonce(self, device, nonce, now):
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM device_nonces WHERE seen < ?",(now-180,))
            try:
                c.execute("INSERT INTO device_nonces VALUES(?,?,?)",(device,nonce,now))
            except sqlite3.IntegrityError as exc:
                raise Denied("Replay rejected") from exc
            changed=c.execute("UPDATE devices SET last_seen=? WHERE id=? AND revoked IS NULL",(now,device)).rowcount
            if changed!=1:
                raise Denied("Revoked device")

    def poll(self, device):
        now=int(self.clock())
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM devices WHERE id=? AND revoked IS NULL",(device,)).fetchone():
                raise Denied("Device unavailable")
            c.execute("UPDATE jobs SET status='expired' WHERE device=? AND expires<? AND status IN ('queued','leased')",(device,now))
            # A job is delivered once only. A lost response becomes an explicit timeout,
            # never a blind retry that might execute destructive Windows commands twice.
            r=c.execute("SELECT id,op,args FROM jobs WHERE device=? AND status='queued' ORDER BY created,id LIMIT 1",(device,)).fetchone()
            if not r:
                return None
            changed=c.execute("UPDATE jobs SET status='leased',lease=?, attempts=attempts+1 WHERE id=? AND status='queued'",(now+90,r[0])).rowcount
            if not changed:
                return None
            return {"operation_id":r[0],"tool":r[1],"arguments":self._open(r[2],"args:"+r[0]), "deadline":now+90}

    def complete(self, device, jobid, result, ok):
        now=int(self.clock())
        data=self._seal(result,"result:"+jobid)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM devices WHERE id=? AND revoked IS NULL",(device,)).fetchone():
                raise Denied("Device unavailable")
            r=c.execute("SELECT status,lease,expires FROM jobs WHERE id=? AND device=?",(jobid,device)).fetchone()
            if not r or r[0]!='leased' or not r[1] or r[1]<now or r[2]<now:
                raise Denied("Operation unavailable or lease expired")
            c.execute("UPDATE jobs SET status=?,result=? WHERE id=? AND device=? AND status='leased'",
                      ('done' if ok else 'failed',data,jobid,device))
