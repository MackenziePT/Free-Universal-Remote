"""Validate workflow YAML structure before it is pushed. Not a hosted CI execution."""
from pathlib import Path
import yaml
root=Path(__file__).resolve().parents[1]
paths=sorted((root/".github"/"workflows").glob("*.yml"))
assert paths, "No GitHub Actions workflows"
for path in paths:
    workflow=yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(workflow,dict)
    triggers=workflow.get("on",workflow.get(True))
    assert triggers, "Missing triggers in "+path.name
    assert workflow.get("permissions",{}).get("contents")=="read", "Missing least-privilege permissions"
    jobs=workflow.get("jobs")
    assert isinstance(jobs,dict) and jobs
    for name,job in jobs.items():
        assert job.get("runs-on"), (path.name,name,"runs-on missing")
        steps=job.get("steps",[])
        assert steps and all(("run" in s or "uses" in s) for s in steps)
        for step in steps:
            if "uses" in step:
                assert "@" in step["uses"], (path.name, "Unversioned action")
    print("WORKFLOW_PASS",path.name,len(jobs))
print("WORKFLOWS_VALIDATED",len(paths))
