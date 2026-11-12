"""Isolated developer-controlled static and dependency QA. No application installs."""
from __future__ import annotations
import json, os, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
TOOL=QA/"tools-venv"/"Scripts"
APP=Path(os.environ["LOCALAPPDATA"])/"HarmonyRemoteMCP"/"app"/".venv"/"Scripts"/"python.exe"
assert APP.exists()
QA.mkdir(parents=True,exist_ok=True)
results={}
def run(key,command,timeout):
    start=time.perf_counter()
    try:
        p=subprocess.run([str(x) for x in command],cwd=str(ROOT),capture_output=True,
                         text=True,errors="replace",timeout=timeout,check=False)
        result=dict(exit_code=p.returncode,seconds=round(time.perf_counter()-start,2),
                    error_tail=p.stderr[-2000:],output_tail=p.stdout[-800:])
    except subprocess.TimeoutExpired:
        result=dict(exit_code=None,seconds=round(time.perf_counter()-start,2),
                    error_tail="Timeout; audit incomplete",output_tail="")
    results[key]=result
    (QA/(key+".run.json")).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("AUDIT",key,"EXIT",result["exit_code"],"SECONDS",result["seconds"],flush=True)

ruff=list(ROOT.glob("*.py"))+list((ROOT/"tests").glob("*.py"))+list((ROOT/"tools").glob("*.py"))
run("ruff",[TOOL/"ruff.exe","check","--no-cache","--output-format","json",
            "--output-file",QA/"ruff-findings.json",*ruff],90)
run("bandit",[TOOL/"bandit.exe","-r",ROOT,"-x",
             ",".join(str(ROOT/x) for x in ("evidence","tests","tools","previous-release",".git")),
             "-f","json","-o",QA/"bandit-findings.json"],90)
run("cyclonedx",[TOOL/"cyclonedx-py.exe","environment",APP,
                 "--output-reproducible","--of","JSON","-o",QA/"sbom-cyclonedx.json"],90)
run("pip_audit",[TOOL/"pip-audit.exe","--path",APP.parent.parent/"Lib"/"site-packages",
                 "--format","json","--output",QA/"pip-vulnerabilities.json"],240)
summary={}
for name,r in results.items():
    summary[name]=dict(exit_code=r["exit_code"],seconds=r["seconds"])
    if name=="ruff" and (QA/"ruff-findings.json").exists():
        try:
            issues=json.loads((QA/"ruff-findings.json").read_text(encoding="utf-8"))
            summary[name]["issues"]=len(issues)
            summary[name]["codes"]={}
            for issue in issues:
                code=issue.get("code","?")
                summary[name]["codes"][code]=summary[name]["codes"].get(code,0)+1
        except Exception: pass
    elif name=="bandit" and (QA/"bandit-findings.json").exists():
        try:
            issues=json.loads((QA/"bandit-findings.json").read_text(encoding="utf-8"))
            summary[name]["issues"]=len(issues.get("results",[]))
            summary[name]["severities"]={}
            for issue in issues.get("results",[]):
                k=issue.get("issue_severity","UNKNOWN")
                summary[name]["severities"][k]=summary[name]["severities"].get(k,0)+1
        except Exception:pass
    elif name=="cyclonedx" and (QA/"sbom-cyclonedx.json").exists():
        try:
            bom=json.loads((QA/"sbom-cyclonedx.json").read_text(encoding="utf-8"))
            summary[name]["components"]=len(bom.get("components",[]))
        except Exception:pass
    elif name=="pip_audit" and (QA/"pip-vulnerabilities.json").exists():
        try:
            obj=json.loads((QA/"pip-vulnerabilities.json").read_text(encoding="utf-8"))
            vulns=[{"package":x.get("name"),"version":x.get("version"),"ids":[v["id"] for v in x.get("vulns",[])]}
                   for x in obj.get("dependencies",[]) if x.get("vulns")]
            summary[name]["vulnerable_packages"]=vulns
            summary[name]["total_dependencies"]=len(obj.get("dependencies",[]))
        except Exception: pass
(QA/"security-audit-summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print("SUMMARY_BEGIN")
print(json.dumps(summary,ensure_ascii=False))
print("SUMMARY_END")
