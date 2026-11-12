"""Audit installed runtime dependency closure against OSV.dev, without credentials.

Queries public PyPI names and versions only. Writes a bounded local JSON report.
No pip upgrades or application changes.
"""
from __future__ import annotations
import importlib.metadata as md
import json,os,sys,urllib.request
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"evidence"/"qa"/"dependency-osv-runtime.json"
DIRECT=("mcp","psutil","mss","Pillow","pyautogui","Send2Trash")
queue=deque(DIRECT)
found={}
unresolved=[]
while queue:
    name=queue.popleft()
    name=canonicalize_name(name)
    if name in found:continue
    try:dist=md.distribution(name)
    except md.PackageNotFoundError:
        unresolved.append(name)
        continue
    metadata=dist.metadata
    found[name]={"version":dist.version,
                 "license":metadata.get("License-Expression") or metadata.get("License") or "UNKNOWN"}
    for line in dist.requires or []:
        try:
            req=Requirement(line)
            if req.marker and not req.marker.evaluate({"extra":""}):
                continue
            dependent=canonicalize_name(req.name)
            if dependent not in found:queue.append(dependent)
        except Exception:
            unresolved.append("unparsed_requirement")
queries=[{"package":{"name":name,"ecosystem":"PyPI"},"version":info["version"]}
         for name,info in sorted(found.items())]
output={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
        "source":"OSV.dev public vulnerability query batch",
        "direct":DIRECT,
        "packages":found,
        "unresolved":unresolved,
        "queried":len(queries),
        "status":"not_checked",
        "vulnerabilities":[]}
try:
    body=json.dumps({"queries":queries}).encode("utf-8")
    request=urllib.request.Request("https://api.osv.dev/v1/querybatch",data=body,
            headers={"Content-Type":"application/json","User-Agent":"UniversalRemote-PrivateQA/1.0"},
            method="POST")
    with urllib.request.urlopen(request,timeout=30) as response:
        result=json.load(response)
    rows=result.get("results",[])
    if len(rows)!=len(queries):raise ValueError("OSV result count mismatch")
    for package,row in zip(sorted(found),rows):
        for vuln in row.get("vulns",[]):
            output["vulnerabilities"].append({
                "package":package,"installed_version":found[package]["version"],
                "osv_id":vuln.get("id"),"modified":vuln.get("modified")})
    output["status"]="queried"
except Exception as exc:
    output["status"]="error"
    output["error_type"]=type(exc).__name__
REPORT.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
print("RUNTIME_SUPPLY_CHAIN_OSV",json.dumps({
    "status":output["status"],
    "runtime_packages":len(found),
    "unknown_licenses":sum(1 for x in found.values() if x["license"]=="UNKNOWN"),
    "unresolved":len(unresolved),
    "advisory_matches":len(output["vulnerabilities"]),
    "advisories":output["vulnerabilities"][:15],
},ensure_ascii=False))
