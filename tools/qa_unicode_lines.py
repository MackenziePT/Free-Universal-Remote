"""ASCII-safe inspection of suspect Unicode sequences."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
items=[
 r.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"/"LEIA-PRIMEIRO.md",
 r/"README.md",
 r/"public_gui.py",
 r/"docs"/"PUBLIC_RELEASE_GATES.md",
 r/"tools"/"promote_latest_preview.ps1",
]
for p in items:
    for i,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
        if "\u00c3" in line or "\ufffd" in line:
            print(p.name,i,ascii(line[:240]))
