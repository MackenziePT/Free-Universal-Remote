"""Verify Windows same-volume atomic hard-link capability in a disposable directory."""
import os,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory(prefix="urm-link-test-") as temp:
    source=Path(temp)/"source"
    target=Path(temp)/"target"
    source.write_text("probe")
    os.link(source,target)
    assert target.read_text()=="probe"
    assert source.stat().st_ino==target.stat().st_ino
    print("ATOMIC_HARD_LINK_CREATION_PASS",source.stat().st_nlink)
    try:
        os.link(source,target)
    except FileExistsError:
        print("NO_CLOBBER_EXISTING_TARGET_PASS")
    else:
        raise RuntimeError("os.link unexpectedly replaced an existing target")
