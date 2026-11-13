"""Unsigned Windows x64 standalone prototype only. Do NOT publish these binaries."""
from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from audit_bundled_runtime import audit_all
from rc51_windows_version import generate_version_file

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
DIST=QA/"public-portable-prototype"
WORK=QA/"pyinstaller-work"
SPEC=QA/"pyinstaller-spec"
DIST.mkdir(parents=True,exist_ok=True)
WORK.mkdir(parents=True,exist_ok=True)
SPEC.mkdir(parents=True,exist_ok=True)

targets=[
    ("UniversalRemote-Preview","public_gui.py","windowed",
     ["--hidden-import","pairing_management_ui",
      "--hidden-import","device_pairing",
      "--hidden-import","help_center",
      "--hidden-import","guided_steps",
      "--hidden-import","connection_doctor",
      "--hidden-import","tunnel_setup_ui",
      "--hidden-import","tunnel_manager",
      "--hidden-import","cryptography.hazmat.primitives.asymmetric.ed25519"]),
    ("UniversalRemoteAgent-Preview","public_agent.py","console",
     ["--collect-submodules","mcp.server","--collect-submodules","mcp.shared",
      "--exclude-module","mcp.cli","--collect-all","anyio",
      "--hidden-import","mss","--hidden-import","PIL",
      "--hidden-import","pyautogui","--hidden-import","send2trash",
      "--hidden-import","secure_gateway","--hidden-import","device_pairing",
      "--hidden-import","private_tunnel_bridge",
      "--hidden-import","cryptography.hazmat.primitives.asymmetric.ed25519"]),
    ("UniversalRemoteBridge-Preview","private_tunnel_bridge.py","console",
     ["--collect-submodules","mcp.server","--collect-submodules","mcp.shared",
      "--exclude-module","mcp.cli","--collect-all","anyio",
      "--hidden-import","server","--hidden-import","secure_gateway",
      "--hidden-import","device_pairing","--hidden-import","tunnel_manager",
      "--hidden-import","mss","--hidden-import","PIL",
      "--hidden-import","pyautogui","--hidden-import","send2trash",
      "--hidden-import","psutil",
      "--hidden-import","cryptography.hazmat.primitives.asymmetric.ed25519"]),
    ("UniversalRemoteUpdater-Preview","public_update_cli.py","console",
     ["--hidden-import","release_security",
      "--hidden-import","release_trust_anchor",
      "--hidden-import","cryptography.hazmat.primitives.asymmetric.ed25519"]),
    ("UniversalRemoteTunnel-Preview","public_tunnel.py","console",
     [])
]
outputs=[]
for name,script,window,extras in targets:
    if "--finalize-existing" in sys.argv[1:]:
        binary=DIST/name/(name+".exe")
        if not binary.is_file():
            raise RuntimeError("Cannot finalize missing previously built binary: "+str(binary))
        outputs.append({"binary":str(binary.relative_to(DIST)),
                        "sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
                        "bytes":binary.stat().st_size,
                        "bundle_bytes":sum(f.stat().st_size for f in (DIST/name).rglob("*") if f.is_file())})
        continue
    command=[
        sys.executable,"-m","PyInstaller",
        "--noconfirm","--clean","--noupx","--onedir",
        "--"+window,"--name",name,
        "--version-file",str(generate_version_file(name, QA/(name+".version.txt"))),
        "--distpath",str(DIST),"--workpath",str(WORK),
        "--specpath",str(SPEC),"--paths",str(ROOT),
        *extras,str(ROOT/script)
    ]
    print("BUILD_START",name,flush=True)
    start=time.monotonic()
    log=QA/(name+".build.log")
    flags=getattr(subprocess,"BELOW_NORMAL_PRIORITY_CLASS",0) if os.name=="nt" else 0
    try:
        with log.open("wb") as f:
            proc=subprocess.run(command,cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT,
                                timeout=900,check=False,creationflags=flags)
    except subprocess.TimeoutExpired:
        print("BUILD_TIMEOUT",name,flush=True)
        raise
    print("BUILD_EXIT",name,proc.returncode,"SECONDS",round(time.monotonic()-start,1),flush=True)
    if proc.returncode:
        lines=log.read_text(encoding="utf-8",errors="replace").splitlines()
        print("LOG_LAST_LINES",name,"\n".join(lines[-14:]),flush=True)
        raise SystemExit(proc.returncode)
    binary=DIST/name/(name+".exe")
    if not binary.is_file():raise RuntimeError("Missing expected standalone binary: "+str(binary))
    with binary.open("rb") as handle:
        sha=hashlib.file_digest(handle,"sha256").hexdigest()
    outputs.append({"binary":str(binary.relative_to(DIST)),"sha256":sha,
                    "bytes":binary.stat().st_size,
                    "bundle_bytes":sum(f.stat().st_size for f in (DIST/name).rglob("*") if f.is_file())})
# CPython 3.14 on Windows has a frozen ZIP startup consistency regression:
# two independently generated, semantically identical base_library.zip archives
# are not always equally bootable. Use the ALREADY-VERIFIED main agent archive as
# the canonical CPython stdlib ZIP for all five bundled executables.
# Verify every member byte-for-byte before sharing it. Fail closed if variants
# contain different standard-library code; do not mask a packaging mismatch.
canonical=DIST/"UniversalRemoteAgent-Preview"/"_internal"/"base_library.zip"
with zipfile.ZipFile(canonical) as package:
    canonical_names=package.namelist()
    canonical_hashes={name:hashlib.sha256(package.read(name)).digest()
                      for name in canonical_names}
for item in outputs:
    folder=DIST/Path(item["binary"]).parts[0]
    target=folder/"_internal"/"base_library.zip"
    with zipfile.ZipFile(target) as archive:
        if (len(archive.namelist())!=len(canonical_names) or set(archive.namelist())!=set(canonical_names)) or any(
                hashlib.sha256(archive.read(name)).digest()!=expected
                for name,expected in canonical_hashes.items()):
            raise RuntimeError("Mismatched embedded Python standard library: "+folder.name)
    if target!=canonical:
        shutil.copy2(canonical,target)
    if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(canonical.read_bytes()).digest():
        raise RuntimeError("Failed to normalize frozen Python ZIP: "+folder.name)
print("CANONICAL_PYTHON314_ZIP_VERIFIED_AND_SHARED",flush=True)

# CPython 3.14's frozen ZIP loader needs zlib1.dll BEFORE Python initializes.
# PyInstaller's dependency graph can omit it from a minimal updater, which
# otherwise crashes with "Failed to import encodings module". Reuse the trusted,
# locally bundled Python runtime DLL; never download a random binary.
runtime_zlib = DIST/"UniversalRemoteAgent-Preview"/"_internal"/"zlib1.dll"
if not runtime_zlib.is_file():
    raise RuntimeError("Required Python runtime zlib1.dll missing from agent build")
runtime_hash=hashlib.sha256(runtime_zlib.read_bytes()).digest()
for item in outputs:
    component=DIST/Path(item["binary"]).parts[0]
    expected=component/"_internal"/"zlib1.dll"
    if not expected.is_file():
        shutil.copy2(runtime_zlib,expected)
    if hashlib.sha256(expected.read_bytes()).digest()!=runtime_hash:
        raise RuntimeError("Inconsistent zlib1.dll across components: "+component.name)
    item["bundle_bytes"]=sum(f.stat().st_size for f in component.rglob("*") if f.is_file())
gate_result=audit_all(DIST)
print("RUNTIME_PREREQUISITES_AUDIT_PASS",json.dumps(gate_result),flush=True)

# Real startup probes for every frozen binary. File-presence and SHA audits
# cannot prove that Python's ZIP importer is actually bootable.
for component, arguments, expected in (
        ("UniversalRemote-Preview", ["--self-test"], None),
        ("UniversalRemoteAgent-Preview", ["--health-probe"], "UNIVERSAL_REMOTE_AGENT_HEALTH_OK"),
        ("UniversalRemoteBridge-Preview", ["--health-probe"], "UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK"),
        ("UniversalRemoteUpdater-Preview", ["trust-profile"], '"channel": "PRIVATE_QA"'),
        ("UniversalRemoteTunnel-Preview", ["--self-test"], "UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK")):
    executable = DIST / component / (component + ".exe")
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("_PYI_")
                   and key.upper() not in {"PYINSTALLER_RESET_ENVIRONMENT",
                                           "PYINSTALLER_SUPPRESS_SPLASH_SCREEN"}}
    environment.pop("HARMONY_MCP_CONFIG", None)
    environment.pop("CONTROL_PLANE_API_KEY", None)
    result = subprocess.run([str(executable), *arguments],
                            cwd=executable.parent, env=environment,
                            capture_output=True, text=True, timeout=75)
    if result.returncode != 0 or (expected and expected not in result.stdout):
        print("FROZEN_STARTUP_PROBE_FAILED", component, "exit", result.returncode, flush=True)
        raise SystemExit(7)
    print("FROZEN_STARTUP_PROBE_PASS", component, flush=True)
(DIST/"UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt").write_text(
    "UNSIGNED TEST ARTIFACT. NOT A CERTIFIED RELEASE.\n"
    "Use only for isolated local acceptance, never as an official download.\n"
    "No publisher identity, installer, MSIX, formal WACK or clean Windows E2E.\n",encoding="utf-8")
(DIST/"BUILD-MANIFEST.json").write_text(
    json.dumps({"kind":"unsigned-private-prototype","python":sys.version.split()[0],
                "architectures":["Windows x64"],"components":outputs},
               indent=2,ensure_ascii=False),encoding="utf-8")
print("PORTABLE_BUILD_COMPLETED",json.dumps(outputs,ensure_ascii=False),flush=True)
