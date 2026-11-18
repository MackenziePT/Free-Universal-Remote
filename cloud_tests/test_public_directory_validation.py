"""Current directory metadata limits; never claim upload is publication."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"distribution"/"chatgpt_public"


def test_public_metadata_fits_directory_limits():
    m=json.loads((ROOT/"plugin.json").read_text(encoding="utf-8"))
    ui=m["extensions"]["com.openai"]["interface"]
    assert 1 <= len(ui["displayName"]) <= 30
    assert 1 <= len(ui["shortDescription"]) <= 30
    assert 1 <= len(ui["longDescription"]) <= 4000
    assert 1 <= len(ui["developerName"]) <= 80
    assert 1 <= len(ui["defaultPrompt"]) <= 3
    assert all(len(v)<=128 for v in ui["defaultPrompt"])
    for key in ("websiteURL","supportURL","privacyPolicyURL","termsOfServiceURL"):
        assert ui[key].startswith("https://")


def test_review_dossier_has_exact_positive_and_negative_cases():
    dossier=json.loads((ROOT/"review_dossier.json").read_text(encoding="utf-8"))
    assert len(dossier["positive_cases"])==5
    assert len(dossier["negative_cases"])==3
    for item in dossier["positive_cases"]:
        assert all(item.get(k) for k in ("prompt","expected_tool","expected_result","fixture","status"))
    for item in dossier["negative_cases"]:
        assert all(item.get(k) for k in ("scenario","expected_safe_behavior","why_refused"))
    assert dossier["release_notes"]
    assert dossier["reviewer_demo_credentials_ready"] is False
    assert dossier["official_review_approved"] is False
