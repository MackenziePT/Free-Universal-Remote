"""Build ONE private portable Windows ZIP in the same layout as the installer.

Does not touch the active installation or download anything.
Fails closed on missing resources, incorrect tunnel-client digest or failed startup.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "evidence" / "qa"
BUILT = QA / "public-portable-prototype"
OUTPUT = QA / "UniversalRemote-RC5.1-20261113-HARDENED-PRIVATE-UNSIGNED.zip"
TOP = "UniversalRemote-RC5.1-HARDENED-PRIVATE"
APPS = {
    "GUI": ("UniversalRemote-Preview", "UniversalRemote-Preview.exe"),
    "Agent": ("UniversalRemoteAgent-Preview", "UniversalRemoteAgent-Preview.exe"),
    "Bridge": ("UniversalRemoteBridge-Preview", "UniversalRemoteBridge-Preview.exe"),
    "Tunnel": ("UniversalRemoteTunnel-Preview", "UniversalRemoteTunnel-Preview.exe"),
    "Updater": ("UniversalRemoteUpdater-Preview", "UniversalRemoteUpdater-Preview.exe"),
}
BIN = (
    "tunnel-client.exe", "tunnel-client-origin.json", "LICENSE", "NOTICE",
    "tunnel-client-v0.0.16-windows-amd64-licenses.txt",
    "tunnel-client-v0.0.16-windows-amd64.spdx.json",
    "cloudflared.exe", "cloudflared-manifest.json",
)
SCRIPTS = ("Resolve-PowerShell.ps1", "Prepare-PowerShell.ps1",
           "Test-Independent-PC.ps1")
DOCS = ("README.md", "PUBLIC_SECURITY_MODEL.md",
        "INSTALLER_AND_UX_SPEC.md", "PUBLIC_RELEASE_GATES.md")
TUNNEL_SHA256 = "4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571"
TUNNEL_SIZE = 22591488
STANDALONE_PROBES = (
    ("GUI", "--self-test", None),
    ("Agent", "--health-probe", "UNIVERSAL_REMOTE_AGENT_HEALTH_OK"),
    ("Bridge", "--health-probe", "UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK"),
    ("Tunnel", "--self-test", "UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK"),
    ("Updater", "trust-profile", '"channel": "PRIVATE_QA"'),
)


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Missing or linked file: {path.name}")
    if os.name == "nt" and path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise RuntimeError("Windows reparse point is forbidden")


def copy_checked(src: Path, dst: Path) -> None:
    regular_file(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if digest(src) != digest(dst):
        raise RuntimeError(f"Copy checksum mismatch: {src.name}")


def stage(stage_dir: Path) -> list[dict]:
    # Fail before copying any untrusted executable if the pinned client differs.
    client = ROOT / "bin" / "tunnel-client.exe"
    regular_file(client)
    if client.stat().st_size != TUNNEL_SIZE or digest(client) != TUNNEL_SHA256:
        raise RuntimeError("Official tunnel-client v0.0.16 verification failed")
    origin = json.loads((ROOT / "bin" / "tunnel-client-origin.json").read_text("utf-8"))
    if origin.get("executable_sha256") != TUNNEL_SHA256 or origin.get("release") != "v0.0.16":
        raise RuntimeError("Provenance metadata is inconsistent")
    components = []
    for folder, (src_folder, exe) in APPS.items():
        source = BUILT / src_folder
        if not source.is_dir() or source.is_symlink():
            raise RuntimeError("Bundled component is absent")
        dest = stage_dir / folder
        for file in sorted(source.rglob("*")):
            if file.is_symlink() or (os.name == "nt" and
                file.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise RuntimeError("Unsafe reparse point in component")
            if file.is_file():
                copy_checked(file, dest / file.relative_to(source))
        target = dest / exe
        regular_file(target)
        components.append({"name": folder, "executable": f"{folder}/{exe}",
                           "bytes": target.stat().st_size, "sha256": digest(target)})
    for name in BIN:
        copy_checked(ROOT / "bin" / name, stage_dir / "bin" / name)
    for name in SCRIPTS:
        copy_checked(ROOT / "scripts" / name, stage_dir / "scripts" / name)
    for name in DOCS:
        source = ROOT / "README.md" if name == "README.md" else ROOT / "docs" / name
        copy_checked(source, stage_dir / "docs" / name)
    copy_checked(BUILT / "UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt",
                 stage_dir / "UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt")
    (stage_dir / "PRIVATE-RELEASE-NOTES.txt").write_text(
        "PRIVATE, UNSIGNED QA PREVIEW. Not approved for public distribution.\n"
        "Bridge is owner-only code, included for authenticated private pairing.\n"
        "The Agent also embeds private_tunnel_bridge for owner-only entry points.\n"
        "This archive MUST NOT be shipped as a public artifact.\n"
        "A ZIP layout test is not an authenticated tunnel-pairing test.\n",
        encoding="utf-8")
    return components


def validate_runtime(stage_dir: Path) -> dict:
    # Native Windows-only smoke tests with no Python in PATH and no personal data.
    if os.name != "nt":
        raise RuntimeError("Acceptance requires a real Windows host")
    env = {name: value for name, value in os.environ.items()
           if not name.upper().startswith("_PYI_") and
           name.upper() not in {"PYINSTALLER_RESET_ENVIRONMENT",
                                "PYINSTALLER_SUPPRESS_SPLASH_SCREEN"}}
    for name in ("HARMONY_MCP_CONFIG", "UNIVERSAL_REMOTE_DATA_HOME",
                 "CONTROL_PLANE_API_KEY", "PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    env["PATH"] = os.pathsep.join((str(Path(os.environ["SystemRoot"]) / "System32"),
                                  os.environ["SystemRoot"]))
    passed = {}
    with tempfile.TemporaryDirectory(prefix="urm-portable-qa-") as state:
        env["LOCALAPPDATA"] = state
        for folder, flag, marker in STANDALONE_PROBES:
            exe = stage_dir / folder / APPS[folder][1]
            result = subprocess.run([str(exe), flag], cwd=exe.parent,
                                    env=env, capture_output=True,
                                    text=True, timeout=90)
            if result.returncode or (marker and marker not in result.stdout):
                # Never include potentially sensitive stdout/stderr in release metadata.
                raise RuntimeError(f"{folder} executable startup failed: {result.returncode}")
            passed[folder] = True
        if (Path(state) / "UniversalRemote" / "grants.json").exists():
            raise RuntimeError("Unexpected elevated permissions created in QA profile")
    return passed


def generate_manifest(stage_dir: Path, components: list[dict],
                      probes: dict) -> dict:
    entries = []
    for file in sorted(stage_dir.rglob("*")):
        if not file.is_file():
            continue
        regular_file(file)
        entries.append({
            "path": file.relative_to(stage_dir).as_posix(),
            "bytes": file.stat().st_size,
            "sha256": digest(file),
        })
    manifest = {
        "format": 2,
        "kind": "private-unsigned-windows-x64-portable",
        "version": "1.0.0-rc5.1-dev",
        "layout": "installer-compatible",
        "publishable": False,
        "private_bridge_embedded_in_agent": True,
        "components": components,
        "tunnel_client": {"path": "bin/tunnel-client.exe",
                          "version": "v0.0.16", "bytes": TUNNEL_SIZE,
                          "sha256": TUNNEL_SHA256},
        "standalone_probes": probes,
        "files": entries,
    }
    (stage_dir / "BUILD-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def create_zip(stage_dir: Path, manifest: dict) -> None:
    tmp = OUTPUT.with_name(OUTPUT.name + ".partial")
    tmp.unlink(missing_ok=True)
    if OUTPUT.exists():
        raise RuntimeError("Refusing to overwrite an existing final private ZIP")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for file in sorted(stage_dir.rglob("*")):
                if file.is_file():
                    archive.write(file, arcname=TOP + "/" +
                                  file.relative_to(stage_dir).as_posix())
        with zipfile.ZipFile(tmp, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP CRC verification failed")
            actual = set(archive.namelist())
            expected = {TOP + "/" + row["path"] for row in manifest["files"]}
            expected.add(TOP + "/BUILD-MANIFEST.json")
            if actual != expected:
                raise RuntimeError("ZIP file inventory mismatch")
            for row in manifest["files"]:
                with archive.open(TOP + "/" + row["path"]) as stream:
                    sha = hashlib.sha256()
                    while chunk := stream.read(1024 * 1024):
                        sha.update(chunk)
                    if sha.hexdigest() != row["sha256"]:
                        raise RuntimeError("ZIP member digest mismatch")
        os.replace(tmp, OUTPUT)
        print("PRIVATE_LAYOUT_ZIP_PASS",
              json.dumps({"path": str(OUTPUT), "bytes": OUTPUT.stat().st_size,
                          "sha256": digest(OUTPUT), "files": len(manifest["files"]),
                          "probes": manifest["standalone_probes"]}), flush=True)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    QA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="urm-private-", dir=Path(os.environ["TEMP"])) as tmp:
        where = Path(tmp) / TOP
        where.mkdir()
        components = stage(where)
        probes = validate_runtime(where)
        manifest = generate_manifest(where, components, probes)
        create_zip(where, manifest)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print("PRIVATE_PORTABLE_REJECTED:", str(exc), file=sys.stderr)
        raise SystemExit(1)
