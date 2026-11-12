"""ASCII-only source encoding audit for user-facing files."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"
SKIP={"evidence","previous-release","__pycache__",".git","tools-venv",".venv"}
PATTERNS={
    "mojibake_lead_C3": "\u00c3",
    "mojibake_lead_C2": "\u00c2",
    "replacement_char": "\ufffd",
    "windows_1252_blob": "\u00e2\u20ac",
}
paths=[]
for p in ROOT.rglob("*"):
    if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP) and p.suffix.lower() in {
        ".py",".ps1",".cmd",".md",".iss",".html",".json",".yml",".yaml",".txt"
    }:
        paths.append(p)
paths.extend(p for p in DEST.glob("*") if p.is_file() and p.suffix.lower() in {".md",".txt"})
for p in sorted(paths):
    try:text=p.read_text(encoding="utf-8")
    except (UnicodeError,OSError):
        continue
    hits={k:text.count(v) for k,v in PATTERNS.items() if v in text}
    if hits:
        print("ENCODING_SUSPECT",str(p.relative_to(ROOT.parent)),hits)
print("AUDITED_FILES",len(paths))
