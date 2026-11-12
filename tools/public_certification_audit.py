"""Reproducible pre-publication QA gates, without claiming third-party certification."""
from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence"/"qa"
OUT.mkdir(parents=True, exist_ok=True)
checks=[]
def add(category,name,status,reason):
    assert status in ("PASS","FAIL","BLOCKED","NOTE")
    checks.append(dict(category=category,control=name,status=status,reason=reason))
def exists(category,name,relative):
    present=(ROOT/relative).is_file()
    add(category,name,"PASS" if present else "FAIL",relative)
def source(relative):
    return (ROOT/relative).read_text(encoding="utf-8-sig")

for label,path in [("MCP gateway","server.py"),("Windows UI","universal_remote_ui.py"),
                   ("Native jobs","native_jobs.py"),("Native files","native_files.py"),
                   ("Native Win32 windows","native_windows.py"),("GitHub CI",".github/workflows/windows-quality.yml"),
                   ("Security policy","SECURITY.md"),("Contributing","CONTRIBUTING.md"),
                   ("Release gates","docs/PUBLIC_RELEASE_GATES.md"),
                   ("UX specification","docs/INSTALLER_AND_UX_SPEC.md"),("Website preview","site/index.html")]:
    exists("source",label,path)

try:
    config=json.loads(source("config.example.json"))
    safe=all(config.get("enable_"+x) is False for x in ("writes","shell","screen","input"))
    add("privacy","Default-deny privileges","PASS" if safe else "FAIL","Config example must disable all privileged access")
except (OSError, ValueError) as ex:
    add("privacy","Config sample","FAIL",type(ex).__name__)
text=source("server.py")
add("version","Development version marked","PASS" if '"version": "1.0.0-rc5.1-dev"' in text else "FAIL","Version cannot impersonate RC5.0")
text=source("universal_remote_ui.py")
add("privacy","Consent duration <=60min","PASS" if "self._grant(480)" not in text else "FAIL","No eight-hour grant UI")
text=source("scripts/Resolve-PowerShell.ps1")
add("runtime","Verified pwsh selection","PASS" if "Get-AuthenticodeSignature" in text and "SHA256" in text else "FAIL",
    "Static existence only; fresh-download E2E still pending")
# The legacy PowerShell+Python installer is for the development line only.
# Public users receive the compiled and separately tested Inno Setup package.
from audit_bundled_runtime import audit_all
try:
    bundles=audit_all(OUT/"public-portable-prototype")
    report=json.loads((OUT/"installer-e2e-results.json").read_text(encoding="utf-8"))
    verified=all((
        report.get("installed_files_present"),
        report.get("unconfigured_denied"),
        report.get("gui_six_pages"),
        report.get("agent_stdio_tools")==27,
        report.get("repair_preserved_personal_config"),
        report.get("uninstaller_exit")==0,
        report.get("uninstaller_removed_exe"),
        report.get("user_private_state_preserved_on_uninstall"),
    ))
    add("distribution","Bundled Python + VC++ in public x64 binaries",
        "PASS" if len(bundles)==2 else "FAIL","Two Windows x64 portable bundles with embedded runtimes")
    add("distribution","Self-contained preview installer verified without Python on PATH",
        "PASS" if verified else "FAIL",
        "Local x64 installation/reinstallation/uninstallation E2E; does not prove clean-PC compatibility")
except (OSError,ValueError,KeyError) as exc:
    add("distribution","Public runtime and installer verification","FAIL",type(exc).__name__)
wizard=source("public_gui.py")
add("usability","Five-step first-run wizard implemented",
    "PASS" if "PASSO {self.step+1} DE 5" in wizard and "prepare_powershell" in wizard else "FAIL",
    "Function tested on local desktop; independent usability and accessibility tests still required")
items=[
("Windows signed EXE/MSIX","Needs actual final installer and trusted publisher identity"),
("Windows App Certification Kit","Requires installed/packaged candidate and Windows SDK"),
("Windows 10/11 x64+ARM64 machines","Only current ASUS x64 tested"),
("Fresh install on an independently clean Windows PC","No independent clean x64/ARM64 machine tested; source/path-restricted E2E passed only on ASUS"),
("Independent usability/accessibility evaluation of onboarding","Five-step wizard exists; requires keyboard, screen-reader, localization and external-user testing"),
("Upgrade interruption, rollback and Windows recovery E2E","Repair/uninstall passed locally; interruption and rollback still require an isolated Windows test system"),
("Independent adversarial/pentest review","Cannot self-certify independent third-party findings"),
("Publisher Authenticode signing","Requires verified publisher credentials and signed artefacts"),
("Microsoft Store certification","Requires Store submission and Microsoft approval"),
("Accessible UI with assistive technology","Needs actual screen-reader, DPI and keyboard tests"),
("Published GitHub Release","No public release yet; do not publish secrets"),
("Live website, HTTPS, privacy notice","Current website is local preview only")
]
for name,detail in items:
    add("external-or-release",name,"BLOCKED",detail)
exclusions={"evidence","previous-release","__pycache__",".git",".venv","tools-venv"}
files=[]
for path in ROOT.rglob("*"):
    if not path.is_file() or set(path.relative_to(ROOT).parts)&exclusions:
        continue
    if path.suffix.lower() in {".py",".ps1",".cmd",".md",".json",".yml",".yaml",".html",".txt"}:
        files.append(path)
patterns={
    "OpenAI API key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{25,}"),
    "Tunnel ID": re.compile(r"\btunnel_[0-9a-f]{32}\b"),
    "Developer user directory": re.compile(r"[A-Za-z]:\\Users\\"+re.escape(Path.home().name)+r"\\", re.IGNORECASE),
}
sensitive={}
for name,patt in patterns.items():
    matches=[]
    for path in files:
        try: data=path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError): continue
        if patt.search(data):
            matches.append(path.relative_to(ROOT).as_posix())
    sensitive[name]=matches
    add("secrets",name,"PASS" if not matches else "FAIL",
        str(len(matches))+" matching source files; no credential values in report")
checksums={}
for relative in ("server.py","remote_core.py","native_jobs.py","native_files.py","universal_remote_ui.py",
                 "scripts/Resolve-PowerShell.ps1","scripts/Public-Bootstrap.ps1","INICIAR.cmd","requirements.txt"):
    p=ROOT/relative
    if p.is_file(): checksums[relative]=hashlib.sha256(p.read_bytes()).hexdigest()
audit=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
           status="INTERNAL ENGINEERING QA ONLY, NOT INDEPENDENT CERTIFICATION",
           checks=checks,secret_match_paths=sensitive,source_sha256=checksums)
(OUT/"certification-gates.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
counts={k:sum(c["status"]==k for c in checks) for k in ("PASS","FAIL","BLOCKED","NOTE")}
lines=["# Universal Remote RC5.1: auditoria interna de publicação",
       "","Não equivale a uma certificação independente nem a aprovação para publicação.",
       "","Resultados: "+", ".join(k+"="+str(v) for k,v in counts.items()),
       "","| Área | Controlo | Estado | Evidência/limite |","|---|---|---|---|"]
for c in checks:
    lines.append("| "+c["category"]+" | "+c["control"]+" | "+c["status"]+" | "+c["reason"].replace("|","/")+" |")
lines.append("")
lines.append("Com FAIL/BLOCKED, não anunciar como versão pública certificada.")
(OUT/"certification-gates.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("GATE_COUNTS",json.dumps(counts))
for c in checks:
    if c["status"]=="FAIL": print("FAIL",c["control"],c["reason"])
print("CREATED",OUT/"certification-gates.md")
