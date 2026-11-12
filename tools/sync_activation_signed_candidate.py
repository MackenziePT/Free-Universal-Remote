"""Keep the signed candidate's URI registration in parity with private QA.
This changes only source; never bypasses CA signing or release gating.
"""
from pathlib import Path
base=Path(__file__).resolve().parents[1]
p=base/"packaging"/"UniversalRemote-Preview.iss"
signed=base/"packaging"/"UniversalRemote-SIGNED-CANDIDATE.iss"
src=p.read_text(encoding="utf-8-sig")
dst=signed.read_text(encoding="utf-8-sig")
marker="[Code]\n"
if src.count(marker)!=1 or dst.count(marker)!=1:
    raise RuntimeError("Expected exactly one [Code] block each")
same_start=src.index(marker)
other_start=dst.index(marker)
code=src[same_start:]
if "InstallURProtocol" not in code or "CurUninstallStepChanged" not in code:
    raise RuntimeError("Required safe URL protocol registration missing")
# The signed candidate retains its own header, signing and bundled files.
signed.write_text(dst[:other_start]+code,encoding="utf-8-sig")
print("SIGNED_CANDIDATE_LINK_HANDLER_PARITY_OK")
