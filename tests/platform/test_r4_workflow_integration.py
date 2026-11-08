"""R4 release-ready workflow entrypoint and fail-closed synthetic regressions.

No registry access, workflow dispatch, release publication or NAS operation.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts import r4_release_ready as r4
from scripts.verify_image_security import SecurityContractError

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ghcr-verify.yml"


def test_r4_job_keeps_minimal_attestation_signing_and_module_entrypoints():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["verify"]
    assert job["permissions"]["attestations"] == "write"
    assert job["permissions"]["id-token"] == "write"
    assert job["permissions"]["packages"] == "read"
    steps = {step["name"]: step for step in job["steps"] if "name" in step}
    integration = steps["Run disposable integration using pulled digests only"]["run"]
    producer = steps["Stage canonical R4 v1 release-ready bundle only after all gates pass"]["run"]
    assert "python -m scripts.no_rebuild_integration --lock" in integration
    assert "python -m scripts.r4_release_ready " in producer
    assert "actions/attest@" in steps[
        "Cryptographically attest exact R4 release-ready root manifest"]["uses"]
    assert steps["Upload signed canonical release-ready artifact for R5"]["with"]["name"] == (
        "foxden-r4-release-ready-v1.0.0"
    )
    for module in ("scripts.no_rebuild_integration", "scripts.r4_release_ready"):
        result = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, (module, result.stderr)


def test_r4_assembler_rejects_signed_scanner_failure_before_staging(
    tmp_path, monkeypatch
):
    security = tmp_path / "security"
    candidates = tmp_path / "candidates"
    security.mkdir()
    candidates.mkdir()
    for name, data in (
        ("security-contract.json", {}),
        ("release-lock.json", {"version": "1.0.0", "publisher": {"run_id": 7}}),
        ("scanner.json", {}),
        ("rendered-release-compose.json", {}),
    ):
        (security / name).write_text(json.dumps(data), encoding="utf-8")
    for name in ("portal", "music", "media"):
        (candidates / (name + ".json")).write_text("{}", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text("{}", encoding="utf-8")
    compose = tmp_path / "compose.yaml"
    compose.write_text("services: {}", encoding="utf-8")

    # Isolate the assembler's scanner gate; the complete R2 and v1 contract
    # validation have their own positive/negative test suites.
    monkeypatch.setattr(r4, "validate_lock", lambda *args, **kwargs: None)
    monkeypatch.setattr(r4, "validate_contract", lambda *args, **kwargs: None)

    def reject_bad_scanner(contract, metadata, ledger):
        raise SecurityContractError("synthetic stale signed scanner evidence")

    monkeypatch.setattr(r4, "validate_scanner_policy", reject_bad_scanner)
    output = tmp_path / "release-bundle"
    with pytest.raises(SecurityContractError, match="stale signed scanner"):
        r4.assemble_bundle(
            source="a" * 40, r3_id=7, r4_id=8, acceptance_id=9,
            approval_issue=18, security_dir=security, candidates_dir=candidates,
            provenance_dir=tmp_path / "provenance",
            integration_path=tmp_path / "integration.json",
            acceptance_dir=tmp_path / "acceptance",
            issue_path=tmp_path / "issue.json",
            comments_path=tmp_path / "comments.json",
            alerts_dir=tmp_path / "alerts", compose_path=compose,
            policy_path=policy, output=output,
        )
    assert not output.exists()


def test_r4_assembler_rejects_duplicate_json_evidence_keys(tmp_path):
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"source_sha": "a", "source_sha": "b"}', encoding="utf-8")
    with pytest.raises(r4.ReleaseEvidenceError, match="Duplicate evidence JSON field"):
        r4.read_json(malformed)
