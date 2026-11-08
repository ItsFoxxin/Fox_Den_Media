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


def test_r4_authenticates_all_four_security_subjects_with_explicit_source():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = {step["name"]: step for step in workflow["jobs"]["verify"]["steps"]
             if "name" in step}
    security = steps["Download signed shared digest scan and complete release lock"]
    assert security["env"]["SOURCE_SHA"] == "${{ inputs.source_sha }}"
    assert security["env"]["SECURITY_RUN"] == "${{ inputs.security_run_id }}"
    script = security["run"]
    assert "set -euo pipefail" in script
    assert script.count("gh attestation verify") == 1
    for filename in (
        "security/security-contract.json",
        "security/release-lock.json",
        "security/rendered-release-compose.json",
        "security/scanner.json",
    ):
        assert filename in script
    assert '--source-ref "refs/heads/main"' in script
    assert '--source-digest "$SOURCE_SHA"' in script
    assert ('--signer-workflow '
            '"$GITHUB_REPOSITORY/.github/workflows/trivy-digest-security.yml"'
            ) in script
    signed = steps["Cryptographically attest exact R4 release-ready root manifest"]
    assert signed["with"]["subject-path"] == "release-bundle/release-ready.json"
    # File subjects use GitHub's attestation API, not OCI storage options.
    assert "create-storage-record" not in signed["with"]
    assert "push-to-registry" not in signed["with"]


def test_r3_publisher_requires_owner_go_rechecked_under_protected_environment():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/ghcr-candidates.yml").read_text(encoding="utf-8")
    )
    authorize, publish = workflow["jobs"]["authorize"], workflow["jobs"]["publish"]
    assert authorize["permissions"].get("packages") is None
    assert publish["permissions"]["packages"] == "write"
    assert publish["environment"] == "ghcr-candidates"
    assert publish["needs"] == "authorize"
    for job in (authorize, publish):
        scripts = "\n".join(step.get("run", "") for step in job["steps"])
        assert "scripts/verify_candidate_approval.py" in scripts
        assert "scripts/verify_publisher_checks.py" in scripts
        assert "GHCR-CANDIDATES" not in scripts  # no unauthenticated inline GO
        assert "gh api" in scripts
        assert "GITHUB_SHA" in scripts
        assert "GHCR" in str(job["steps"])
    assert workflow["jobs"]["publish"]["strategy"]["matrix"]["include"]
    assert "push" not in workflow.get("on", {})  # workflow_dispatch only


def test_independent_acceptance_run_rejects_wrong_identity_or_status():
    valid = {
        "id": 234,
        "repository": {"full_name": r4.REPO},
        "path": r4.ACCEPTANCE_WORKFLOW,
        "event": "workflow_dispatch",
        "head_sha": "a" * 40,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
    }
    r4.require_successful_acceptance(valid, "a" * 40, 234)
    for key, value in (
        ("id", 235),
        ("repository", {"full_name": "someone/other-repo"}),
        ("path", ".github/workflows/untrusted.yml"),
        ("event", "pull_request"),
        ("head_sha", "b" * 40),
        ("head_branch", "dev"),
        ("status", "queued"),
        ("conclusion", "failure"),
    ):
        bad = dict(valid)
        bad[key] = value
        with pytest.raises(r4.ReleaseEvidenceError):
            r4.require_successful_acceptance(bad, "a" * 40, 234)
    with pytest.raises(r4.ReleaseEvidenceError):
        r4.require_successful_acceptance({}, "a" * 40, 234)


def test_r4_rejects_missing_unsigned_or_mismatched_provenance():
    image = "ghcr.io/itsfoxxin/fox-den-media-portal"
    digest = "sha256:" + "b" * 64
    valid = [{
        "verificationResult": {
            "statement": {
                "subject": [{"name": image, "digest": {"sha256": "b" * 64}}],
            },
        },
    }]
    r4.verify_attested_provenance(valid, image, digest)
    for evidence in (
        [],
        [{}],
        [{"statement": valid[0]["verificationResult"]["statement"]}],
        [{"verificationResult": {"statement": {"subject": []}}}],
        [{"verificationResult": {"statement": {
            "subject": [{"name": image, "digest": {"sha256": "c" * 64}}],
        }}}],
    ):
        with pytest.raises(r4.ReleaseEvidenceError):
            r4.verify_attested_provenance(evidence, image, digest)
