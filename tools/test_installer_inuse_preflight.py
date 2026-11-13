"""Windows integration gate: an active Universal Remote process must block setup
BEFORE any file is installed. Uses only disposable dummy executables and paths.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "evidence" / "qa" / "installer-build" / (
    "UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
)

def run_case(installer: Path, process_name: str, work: Path) -> None:
    folder = work / process_name.replace(".exe", "")
    folder.mkdir(parents=True)
    exe = folder / process_name
    shutil.copy2(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe", exe)
    proc = subprocess.Popen(
        [str(exe), "/D", "/C", "ping -n 60 127.0.0.1 >NUL"],
        cwd=folder,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        time.sleep(0.6)
        if proc.poll() is not None:
            raise AssertionError(f"Disposable process exited unexpectedly: {process_name}")
        target = work / ("install-" + folder.name)
        log = work / ("setup-" + folder.name + ".log")
        result = subprocess.run(
            [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
             "/LANG=english", "/DIR=" + str(target), "/LOG=" + str(log)],
            cwd=work,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=50,
            check=False,
        )
        if result.returncode != 7:
            raise AssertionError(f"Expected safe preinstall refusal (7), got "
                                 f"{result.returncode} for {process_name}. "
                                 f"Log: {log.read_text(encoding='utf-8-sig', errors='replace')[-1200:] if log.exists() else 'missing'}")
        if (target / "GUI" / "UniversalRemote-Preview.exe").exists():
            raise AssertionError("Setup modified a target before the in-use gate")
        print("INNO_RUNNING_PROCESS_PREINSTALL_REFUSAL_PASS", process_name, flush=True)
    finally:
        # Only our intentionally spawned fixture and its descendant ping.exe.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=20, check=False)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Windows-only installer process test")
    installer = Path(sys.argv[1]) if len(sys.argv) > 1 else INSTALLER
    if not installer.is_file():
        raise SystemExit(f"Installer missing: {installer}")
    with tempfile.TemporaryDirectory(prefix="urm-inno-running-process-") as temp:
        root = Path(temp)
        for name in ("UniversalRemote-Preview.exe",
                     "UniversalRemoteBridge-Preview.exe"):
            run_case(installer, name, root)
    print("INNO_UPGRADE_PREINSTALL_GUARD_PASS", flush=True)


if __name__ == "__main__":
    main()
