import json
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
qa=root/"evidence"/"qa"
r=json.loads((qa/"ruff-findings.json").read_text(encoding="utf-8"))
print("RUFF_COUNT",len(r))
for item in r:
    if item["code"] in {"F821","F822","F823","F841","F401","PLW1510"}:
        print("RUFF",item["code"],Path(item["filename"]).relative_to(root).as_posix(),
              item["location"]["row"],item["message"][:115])
bandit=json.loads((qa/"bandit-findings.json").read_text(encoding="utf-8"))
print("BANDIT_COUNT",len(bandit.get("results",[])))
for item in bandit.get("results",[]):
    print("BANDIT",item["issue_severity"],item["test_id"],
          Path(item["filename"]).relative_to(root).as_posix(),item["line_number"],
          item["issue_text"][:130])
pipa=json.loads((qa/"pip-vulnerabilities.json").read_text(encoding="utf-8"))
print("AUDIT_PACKAGES",len(pipa.get("dependencies",[])))
for pkg in pipa.get("dependencies",[]):
    v=pkg.get("vulns",[])
    if v:
        counts=Counter(f for issue in v for f in issue.get("fix_versions",[]))
        print("PACKAGE",pkg["name"],pkg["version"],"FINDINGS",len(v),"FIX_VERSION_COUNTS",dict(counts))
