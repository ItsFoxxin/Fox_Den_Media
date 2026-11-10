"""Offline synthetic R4 v2 byte-preservation and flat signed-file-map tests.

These synthetic proof bytes are NOT valid cryptographic security dispositions;
the complete Ed25519 verification is owned by PR #93 and required at runtime.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts import r4_release_ready as r4


def raw(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_review(tmp_path: Path):
    base = tmp_path / "review-evidence"
    output = tmp_path / "release-bundle"
    (base / "security").mkdir(parents=True)
    (base / "review/proofs").mkdir(parents=True)
    proof = base / "review/proofs/finding-1.json"
    proof.write_text('{"schema_version":1,"kind":"FIXED"}\n')
    document = {"records": [{
        "proof_path": "proofs/finding-1.json", "proof_sha256": raw(proof),
    }]}
    (base / "review/dispositions.json").write_text(json.dumps(document))
    (base / "review/signatures.json").write_text('{"synthetic":true}')
    result = {"disposition_document_sha256": "sha256:" + "b" * 64}
    (base / "security/disposition-verification.json").write_text(json.dumps(result))
    binding = {
        "verification_sha256": raw(base / "security/disposition-verification.json"),
        "dispositions_sha256": result["disposition_document_sha256"],
        "review_run_id": 23, "verified_at": "2026-11-10T08:00:00Z",
    }
    return base, output, document, result, binding


def pack(base, output, document, result, binding, run=23):
    return r4.stage_independent_dispositions(
        review_dir=base, output=output, dispositions=document,
        signed_result=result, binding=binding, review_id=run)


def test_flat_disposition_files_fit_signed_envelope_allowlist(tmp_path):
    base, output, document, result, binding = fixture_review(tmp_path)
    extension = pack(base, output, document, result, binding)
    expected = {
        "integration/disposition-verification.json",
        "integration/security-dispositions.json",
        "integration/security-disposition-signatures.json",
        "integration/disposition-proof-finding-1.json",
    }
    actual = {str(p.relative_to(output)) for p in output.rglob("*.json")}
    assert actual == expected
    assert extension == {
        "schema_version": 1, "artifact_name": "security-disposition-review-v1",
        "verification_file": "integration/disposition-verification.json",
        "verification_sha256": binding["verification_sha256"],
        "dispositions_sha256": binding["dispositions_sha256"],
        "review_workflow": ".github/workflows/security-disposition-review.yml",
        "review_run_id": 23, "verified_at": binding["verified_at"],
    }
    # The caller's existing recursive R4 hash collector seals all four files.
    assert all(r4.sha_file(output / name) for name in expected)


@pytest.mark.parametrize("mutation", [
    "missing-proof", "altered-proof", "unreferenced-proof",
    "duplicate-proof", "wrong-hash", "wrong-run", "modified-result",
])
def test_disposition_flattening_fails_closed(mutation, tmp_path):
    base, output, document, result, binding = fixture_review(tmp_path)
    proof = base / "review/proofs/finding-1.json"
    if mutation == "missing-proof":
        proof.unlink()
    elif mutation == "altered-proof":
        proof.write_text('{"kind":"NOT_AFFECTED"}')
    elif mutation == "unreferenced-proof":
        (base / "review/proofs/extra.json").write_text("{}")
    elif mutation == "duplicate-proof":
        document["records"].append(copy.deepcopy(document["records"][0]))
    elif mutation == "wrong-hash":
        binding["dispositions_sha256"] = "sha256:" + "f" * 64
    elif mutation == "wrong-run":
        binding["review_run_id"] = 99
    elif mutation == "modified-result":
        (base / "security/disposition-verification.json").write_text("{}")
    with pytest.raises(r4.ReleaseEvidenceError):
        pack(base, output, document, result, binding)


def fixture_scan(tmp_path):
    policy = tmp_path / "source-policy.json"
    policy.write_text('{"schema_version":1,"exceptions":[]}')
    original = tmp_path / "scan-inputs"
    final = tmp_path / "security"
    components = ("portal", "music", "media", "nginx")
    for root in (original, final):
        (root / "reports").mkdir(parents=True)
        (root / "release-lock.json").write_text('{"lock":"synthetic"}')
        (root / "scanner.json").write_text('{"Version":"0.76.2"}')
        for component in components:
            for suffix in (".vuln.json", ".sbom.spdx.json"):
                (root / "reports" / (component + suffix)).write_text(
                    '{"raw":"'+component+suffix+'"}')
    (original / "vulnerability-exceptions.json").write_bytes(policy.read_bytes())
    return {"images": {key: {} for key in components}}, original, final, policy


def test_final_c_keeps_every_original_a_report_spdx_lock_and_scanner(tmp_path):
    lock, original, final, policy = fixture_scan(tmp_path)
    r4.require_unmodified_scan_collection(
        lock=lock, scan_dir=original, security_dir=final, policy_path=policy)


@pytest.mark.parametrize("mutation", [
    "altered-trivy", "altered-spdx", "altered-lock",
    "altered-scanner", "altered-policy", "missing-upstream",
])
def test_modified_scan_evidence_or_omitted_upstream_rejected(mutation, tmp_path):
    lock, original, final, policy = fixture_scan(tmp_path)
    if mutation == "altered-trivy":
        (final / "reports/nginx.vuln.json").write_text("{}")
    elif mutation == "altered-spdx":
        (original / "reports/music.sbom.spdx.json").write_text("{}")
    elif mutation == "altered-lock":
        (final / "release-lock.json").write_text("{}")
    elif mutation == "altered-scanner":
        (final / "scanner.json").write_text("{}")
    elif mutation == "altered-policy":
        policy.write_text('{"exceptions":[{"unauthorized":true}]}')
    elif mutation == "missing-upstream":
        (original / "reports/nginx.vuln.json").unlink()
    with pytest.raises(r4.ReleaseEvidenceError):
        r4.require_unmodified_scan_collection(
            lock=lock, scan_dir=original, security_dir=final, policy_path=policy)


def test_workflow_requires_source_bound_signed_a_b_c_and_owner_trust():
    root = Path(__file__).resolve().parents[2]
    wf = yaml.safe_load((root / ".github/workflows/ghcr-verify.yml").read_text())
    job = wf["jobs"]["verify"]
    steps = {step["name"]: step for step in job["steps"] if "name" in step}
    assert job["environment"] == "security-disposition-review"
    preflight = steps["Prove exact main and source producer runs"]["run"]
    assert "for kind in publisher scan review security" in preflight
    assert 'test "$scan_actor" != "$review_actor"' in preflight
    assert "required_reviewers" in preflight
    downloads = steps["Authenticate exact A B C signed artifact subjects"]["run"]
    assert "--source-digest \"$SOURCE_SHA\"" in downloads
    assert "invocationId" in downloads
    assert "security-disposition-review.yml" in downloads
    trust = steps["Load owner-managed signed disposition lifecycle and reviewer trust"]["run"]
    assert "SECURITY_DISPOSITION" not in downloads
    assert "base64 --decode" in trust
    stage = steps["Stage canonical R4 v1 release-ready bundle only after all gates pass"]
    for flag in ("--scan-run-id", "--review-run-id", "--trust-path",
                 "--lifecycle-path", "--lifecycle-signature-path"):
        assert flag in stage["run"]
    assert "--policy-path source-policy/vulnerability-exceptions.json" in stage["run"]


def test_signed_file_map_cannot_omit_or_tamper_with_disposition_proof(tmp_path):
    base, output, document, result, binding = fixture_review(tmp_path)
    extension = pack(base, output, document, result, binding)
    hashes = {str(p.relative_to(output)): r4.sha_file(p)
              for p in output.rglob("*.json")}
    r4.validate_disposition_file_map(
        files=hashes, output=output, dispositions=document, binding=extension)
    for broken in ("missing-proof", "altered-proof-hash",
                   "missing-verification", "extra-proof"):
        modified = dict(hashes)
        if broken == "missing-proof":
            modified.pop("integration/disposition-proof-finding-1.json")
        elif broken == "altered-proof-hash":
            modified["integration/disposition-proof-finding-1.json"] = "a" * 64
        elif broken == "missing-verification":
            modified.pop("integration/disposition-verification.json")
        elif broken == "extra-proof":
            modified["integration/disposition-proof-unknown.json"] = "a" * 64
        with pytest.raises(r4.ReleaseEvidenceError):
            r4.validate_disposition_file_map(
                files=modified, output=output, dispositions=document,
                binding=extension)
