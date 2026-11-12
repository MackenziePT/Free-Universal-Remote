"""Fail-closed, local, at-most-once dispatch of privileged MCP operations.

This is NOT exactly-once execution. After a process crash an operation may have
run and the result is unknown: the operation must NOT be retried automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar('T')


def _journal_file(config, operation_id: str) -> Path:
    from remote_core import PolicyError, _is_link_or_junction
    if not isinstance(operation_id, str):
        raise PolicyError('A canonical UUIDv4 operation_id is required')
    try:
        value = uuid.UUID(operation_id)
        if value.version != 4 or str(value) != operation_id:
            raise ValueError('Not canonical UUIDv4')
    except (ValueError, AttributeError) as exc:
        raise PolicyError('operation_id must be a canonical random UUIDv4') from exc
    root = config.grants_path.parent / 'operation-journal'
    if any(root.is_relative_to(r) for r in config.allowed_roots):
        raise PolicyError('Operation journal must be outside allowed_roots')
    if _is_link_or_junction(root) or _is_link_or_junction(root.parent):
        raise PolicyError('Operation journal aliases are denied')
    return root / (operation_id + '.json')


def operation_status(config, operation_id: str) -> dict:
    from remote_core import PolicyError, _is_link_or_junction
    record = _journal_file(config, operation_id)
    if _is_link_or_junction(record):
        raise PolicyError('Operation journal entry aliases are denied')
    if not record.exists():
        return {'operation_id': operation_id, 'state': 'not_found'}
    marker = record.with_suffix('.done')
    return {'operation_id': operation_id,
            'state': 'completed' if marker.is_file() and not _is_link_or_junction(marker) else 'uncertain'}


def execute_once(config, operation_id: str, capability: str, fingerprint: str,
                 perform: Callable[[], T]) -> T:
    """A unique exclusive claim is persisted before executing side effects."""
    from remote_core import PolicyError, _is_link_or_junction
    record = _journal_file(config, operation_id)
    record.parent.mkdir(parents=True, exist_ok=True)
    if _is_link_or_junction(record.parent):
        raise PolicyError('Operation journal directory replaced by alias')
    metadata = {'operation_id': operation_id, 'capability': capability,
                'sha256': hashlib.sha256(fingerprint.encode('utf-8')).hexdigest(),
                'claimed_utc': datetime.now(timezone.utc).isoformat()}
    try:
        with record.open('x', encoding='utf-8') as stream:
            json.dump(metadata, stream, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise PolicyError('Duplicate operation_id: action may already have run; do not retry') from exc
    result = perform()
    # Marker is separate so crash between execution and completion is uncertain.
    with record.with_suffix('.done').open('x', encoding='ascii') as stream:
        stream.write('completed\n')
        stream.flush()
        os.fsync(stream.fileno())
    return result
