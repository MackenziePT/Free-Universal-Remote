"""Offline release integrity and basic structure audit; never executes shipped binaries."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys
import zipfile


def verify_directory(root: Path) -> list[str]:
    problems: list[str] = []
    manifest = root / 'SHA256SUMS.txt'
    if not manifest.is_file():
        return ['missing SHA256SUMS.txt']
    entries: set[str] = set()
    for lineno, line in enumerate(manifest.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            digest, relative = line.split('  ', 1)
        except ValueError:
            problems.append(f'bad manifest line {lineno}')
            continue
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            problems.append(f'invalid digest on line {lineno}')
            continue
        relative = relative.replace('\\', '/')
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or not rel.parts:
            problems.append(f'unsafe manifest path on line {lineno}')
            continue
        if relative in entries:
            problems.append(f'duplicate manifest path on line {lineno}')
            continue
        entries.add(relative)
        file = root / rel
        if not file.is_file() or file.is_symlink():
            problems.append(f'missing or linked file: {relative}')
            continue
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest != actual:
            problems.append(f'SHA mismatch: {relative}')
    disk = {x.relative_to(root).as_posix() for x in root.rglob('*')
            if x.is_file() and '__pycache__' not in x.parts and '.pytest_cache' not in x.parts}
    allowed_unmanifested = {'SHA256SUMS.txt'}
    for extra in sorted(disk - entries - allowed_unmanifested):
        problems.append(f'unmanifested file: {extra}')
    print(f'Manifest entries: {len(entries)}; actual files: {len(disk)}')
    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = verify_directory(root)
    if problems:
        for item in problems: print('FAIL:', item, file=sys.stderr)
        return 1
    print('OK: all manifest files match, no unexpected files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
