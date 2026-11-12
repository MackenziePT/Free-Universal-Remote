"""Fix UTF-8 decoding for Windows PowerShell 5.1 and Inno Setup source files.

PowerShell 5.1 assumes ANSI for BOM-less .ps1, so localized strings require a BOM.
Also repairs the preview README previously interpreted as cp1252 during execution.
"""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
qa=root/"evidence"/"qa"
bom=b"\xef\xbb\xbf"
for relative in ("scripts/Resolve-PowerShell.ps1","scripts/Prepare-PowerShell.ps1",
                 "packaging/UniversalRemote-Preview.iss","tools/promote_latest_preview.ps1"):
    p=root/relative
    data=p.read_bytes()
    data.decode("utf-8-sig")
    if not data.startswith(bom):
        p.write_bytes(bom+data)
    assert p.read_bytes().startswith(bom)
    print("UTF8_BOM_PASS",relative)
doc=root.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"/"LEIA-PRIMEIRO.md"
original=doc.read_text(encoding="utf-8")
assert "\u00c3\u00a9" in original, "README does not contain expected mojibake; do not modify"
shutil.copy2(doc,qa/"DELIVERY_README_BEFORE_ENCODING_REPAIR.md")
repaired=original.encode("cp1252").decode("utf-8")
assert "pr\u00e9-visualiza\u00e7\u00e3o" in repaired
assert "N\u00c3O" in repaired
assert "\u00c3\u00a9" not in repaired
assert "\u00e2\u20ac" not in repaired
doc.write_text(repaired,encoding="utf-8")
print("DELIVERY_README_PTPT_UTF8_PASS",len(repaired))
