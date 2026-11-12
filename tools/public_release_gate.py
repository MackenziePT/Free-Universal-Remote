"""Fail-closed public release readiness inspector (never publishes/signs)."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
unsigned=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
signed=QA/"ca-signed-candidate"/"UniversalRemote-1.0.0-rc5.1-x64-SIGNED-CANDIDATE.exe"
binary=QA/"public-portable-prototype"/"UniversalRemoteUpdater-Preview"/"UniversalRemoteUpdater-Preview.exe"
prod=QA/"publisher-ready-bundle"/"UniversalRemoteUpdater-Preview"/"UniversalRemoteUpdater-Preview.exe"
def inspect_profile(exe):
    if not exe.is_file():
        return {"channel":"MISSING","embedded_keys":0}
    try:
        cp=subprocess.run([str(exe),"trust-profile"],capture_output=True,text=True,
                          timeout=35,check=False)
        if cp.returncode:
            return {"channel":"INVALID","embedded_keys":0}
        profile=json.loads(cp.stdout)
        if set(profile)!={"channel","embedded_keys"}:
            return {"channel":"INVALID","embedded_keys":0}
        return profile
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {"channel":"INVALID","embedded_keys":0}

def main():
    qa_profile=inspect_profile(binary)
    prod_profile=inspect_profile(prod)
    gates={
        "qa_installer_exists":unsigned.is_file(),
        "qa_updater_private_only":qa_profile=={"channel":"PRIVATE_QA","embedded_keys":0},
        "production_updater_embeds_public_keys":(
            prod_profile.get("channel")=="PRODUCTION" and
            isinstance(prod_profile.get("embedded_keys"),int) and
            prod_profile["embedded_keys"]>=1),
        "signed_candidate_present":signed.is_file(),
        "signed_candidate_identity_validated":False,
        "independent_windows_x64_and_arm64_evidence":False,
        "clean_vm_wack_report_reviewed":False,
        "external_security_audit_reviewed":False,
    }
    # The final four gates require trusted external evidence and an authorised
    # publisher identity; this offline code never guesses success.
    audit={
       "product":"Universal Remote","version":"RC5.1",
       "releasable":False,
       "scope":"internal-qa-only",
       "gates":gates,
       "blockers":[name for name,value in gates.items() if not value],
       "qa_installer_sha256":(hashlib.sha256(unsigned.read_bytes()).hexdigest()
                              if unsigned.is_file() else None)
    }
    destination=QA/"PUBLIC-RELEASE-GATE-LATEST.json"
    destination.write_text(json.dumps(audit,ensure_ascii=False,sort_keys=True,
                                       indent=2),encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))
    if not all(gates.values()):
        print("PUBLIC_RELEASE_NO_GO: REQUIREMENTS_NOT_YET_VERIFIED",file=sys.stderr)
        return 3
    return 0

if __name__=="__main__":
    raise SystemExit(main())
