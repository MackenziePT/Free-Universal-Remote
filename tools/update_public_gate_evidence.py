"""Update public release gate classification using actual signed/unsigned binary evidence."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/"tools"/"public_certification_audit.py"
s=p.read_text(encoding="utf-8")
old='''text=source("scripts/Install.ps1")
add("distribution","Self-contained installer without Python","FAIL" if "Get-Command py" in text else "PASS",
    "Installer still requires external Python on a clean PC")
items=['''
new='''# The legacy PowerShell+Python installer is for the development line only.
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
items=['''
assert old in s
s=s.replace(old,new)
s=s.replace('''("Fresh install with no Python","Not yet tested and current installer still needs Python"),''',
'''("Fresh install on an independently clean Windows PC","No independent clean x64/ARM64 machine tested; source/path-restricted E2E passed only on ASUS"),''')
s=s.replace('''("First-run setup wizard","Current UI lacks full public setup workflow"),''',
'''("Independent usability/accessibility evaluation of onboarding","Five-step wizard exists; requires keyboard, screen-reader, localization and external-user testing"),''')
s=s.replace('''("Uninstall, rollback and interrupted upgrade E2E","Requires isolated disposable Windows environment"),''',
'''("Upgrade interruption, rollback and Windows recovery E2E","Repair/uninstall passed locally; interruption and rollback still require an isolated Windows test system"),''')
p.write_text(s,encoding="utf-8",newline="\n")
print("PUBLIC_CERTIFICATION_GATES_NOW_REFER_TO_ACTUAL_INSTALLER")
