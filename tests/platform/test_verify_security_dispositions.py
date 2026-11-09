"""Isolated synthetic tests: no images, real CVEs, release workflows or secrets."""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts import verify_security_dispositions as v

NOW = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
SOURCE = "a" * 40
IMG = "sha256:" + "b" * 64
PLATFORM = "sha256:" + "c" * 64


def utc(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")


def signed(key, domain, obj):
    digest = bytes.fromhex(v.canonical_digest(obj)[7:])
    return base64.b64encode(key.sign(domain + digest)).decode("ascii")


def refresh(case, *, resign=True):
    p = case["root"]
    put(p / "security/reports/portal.vuln.json", case["report"])
    put(p / "security/reports/portal.sbom.spdx.json", case["sbom"])
    put(p / "security/scanner.json", case["scanner"])
    put(p / "security/release-lock.json", case["lock"])
    im = case["context"]["images"]["portal"]
    im["trivy_report_sha256"] = v.raw_digest(p / "security/reports/portal.vuln.json")
    im["spdx_sbom_sha256"] = v.raw_digest(p / "security/reports/portal.sbom.spdx.json")
    case["context"]["scanner_metadata_sha256"] = v.raw_digest(p / "security/scanner.json")
    case["context"]["release_lock_sha256"] = v.raw_digest(p / "security/release-lock.json")
    case["doc"]["source_sha"] = case["context"]["source_sha"]
    case["doc"]["producer_actor"] = case["context"]["producer_actor"]
    case["doc"]["release_lock_sha256"] = case["context"]["release_lock_sha256"]
    case["doc"]["r3_run_id"] = case["context"]["r3_run_id"]
    case["doc"]["scan_run_id"] = case["context"]["scan_run_id"]
    if case["doc"]["records"]:
        record = case["doc"]["records"][0]
        item = case["report"]["Results"][0]["Vulnerabilities"][0]
        record["subject"] = v.finding_subject("portal", 0, 0, case["report"]["Results"][0],
                                              item, im)
        proof = case["proof"]
        for field in ("source_sha", "release_lock_sha256", "r3_run_id", "scan_run_id"):
            proof[field] = case["context"][field]
        for field in ("image_repository", "manifest_digest", "platform_digest",
                      "finding_sha256", "installed_version"):
            proof[field] = record["subject"][field]
        put(p / "review/proofs/proof.json", proof)
        record["proof_sha256"] = v.raw_digest(p / "review/proofs/proof.json")
    if resign:
        resign_document(case)


def resign_document(case):
    h = v.canonical_digest(case["doc"])
    sigs = []
    if case["doc"]["records"]:
        sigs.append({"role": "reviewer", "identity": "github:independent-reviewer",
                     "key_id": "reviewer-key-v1",
                     "signature_base64": signed(case["reviewer"],
                                                b"foxden.dispositions.v1\n", case["doc"])})
        if case["doc"]["records"][0]["status"] == "NOT_AFFECTED" and \
                case["report"]["Results"][0]["Vulnerabilities"][0]["Severity"] == "CRITICAL":
            sigs.append({"role": "owner", "identity": "github:ItsFoxxin",
                         "key_id": "owner-key-v1",
                         "signature_base64": signed(case["owner"],
                                                    b"foxden.dispositions.v1\n", case["doc"])})
    case["signatures"] = {"schema_version": 1, "document_sha256": h, "signatures": sigs}


def case_factory(tmp_path, status="FIXED", severity="HIGH"):
    p = tmp_path
    reviewer = Ed25519PrivateKey.generate()
    owner = Ed25519PrivateKey.generate()
    vuln = {"VulnerabilityID": "CVE-2099-1000", "PkgName": "libsynthetic",
            "InstalledVersion": "1.0", "Severity": severity, "FixedVersion": "1.1"}
    report = {"ArtifactType": "container_image",
              "ArtifactName": "ghcr.io/example/portal@" + IMG,
              "Results": [{"Target": "debian:12", "Type": "debian",
                           "Vulnerabilities": [] if severity == "CLEAN" else [vuln]}]}
    case = {
        "root": p, "reviewer": reviewer, "owner": owner, "report": report,
        "sbom": {"spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT",
                 "packages": [{"SPDXID": "SPDXRef-Package-a"}]},
        "scanner": {"Version": "0.76.2",
                    "VulnerabilityDB": {"Version": 2, "UpdatedAt": utc(NOW)}},
        "lock": {"schema_version": 1, "source_sha": SOURCE, "images": {}},
        "context": {"schema_version": 1, "repository": v.REPOSITORY,
                    "source_sha": SOURCE, "producer_actor": "github:security-producer", "release_lock_sha256": "",
                    "r3_run_id": 101, "scan_run_id": 202,
                    "scanner_metadata_sha256": "",
                    "images": {"portal": {"image_repository": "ghcr.io/example/portal",
                                          "manifest_digest": IMG, "platform_digest": PLATFORM,
                                          "trivy_report_sha256": "", "spdx_sbom_sha256": ""}}},
        "doc": {"schema_version": 1, "repository": v.REPOSITORY,
                "source_sha": SOURCE, "producer_actor": "github:security-producer", "release_lock_sha256": "", "r3_run_id": 101,
                "scan_run_id": 202, "created_at": utc(NOW - timedelta(hours=2)),
                "reviewed_at": utc(NOW - timedelta(hours=1)),
                "expires_at": utc(NOW + timedelta(days=20)), "records": []},
        "proof": {"schema_version": 1, "kind": status, "source_sha": SOURCE,
                  "release_lock_sha256": "", "r3_run_id": 101, "scan_run_id": 202,
                  "image_repository": "ghcr.io/example/portal", "manifest_digest": IMG,
                  "platform_digest": PLATFORM, "finding_sha256": "",
                  "reference_url": "https://security.example.org/advisory/2099-1000",
                  "reference_sha256": "sha256:" + "d" * 64,
                  "verification_method": "Inspect exact signed image package and binary",
                  "binary_sha256": "sha256:" + "e" * 64,
                  "installed_version": "1.0",
                  "technical_basis": "authoritative-remediation-and-installed-image" if
                  status == "FIXED" else "vulnerable-implementation-absent"},
        "trust": {"schema_version": 1, "repository": v.REPOSITORY,
                  "review_workflow": v.REVIEW_WORKFLOW,
                  "producer_workflow": v.PRODUCER_WORKFLOW,
                  "reviewers": {"github:independent-reviewer": {
                      "key_id": "reviewer-key-v1", "public_key_pem": public(reviewer)}},
                  "owner": {"identity": "github:ItsFoxxin", "key_id": "owner-key-v1",
                            "public_key_pem": public(owner)}},
        "exceptions": {"schema_version": 1, "exceptions": []},
        "lifecycle": {"schema_version": 1, "issued_at": utc(NOW - timedelta(minutes=30)),
                      "expires_at": utc(NOW + timedelta(hours=12)),
                      "revoked_document_sha256": [], "superseded_document_sha256": []},
    }
    if severity != "CLEAN":
        case["doc"]["records"].append(
            {"status": status, "subject": {}, "proof_path": "proofs/proof.json",
             "proof_sha256": "", "reviewer_id": "github:independent-reviewer"})
    refresh(case)
    case["lifecycle_signature"] = signed(owner, b"foxden.lifecycle.v1\n",
                                          case["lifecycle"])
    return case


def check(c, *, now=NOW):
    p = c["root"]
    return v.verify(
        context=c["context"], dispositions=c["doc"], signatures=c["signatures"],
        lifecycle=c["lifecycle"], lifecycle_signature=c["lifecycle_signature"],
        trust=c["trust"], evidence_dir=p / "security", proofs_dir=p / "review",
        lock_path=p / "security/release-lock.json",
        scanner=c["scanner"], scanner_path=p / "security/scanner.json",
        exceptions=c["exceptions"], expected_source_sha=SOURCE,
        expected_r3_run_id=101, expected_scan_run_id=202,
        expected_producer_actor=c["context"]["producer_actor"], now=now)


@pytest.mark.parametrize("status,severity", [
    ("FIXED", "HIGH"), ("FIXED", "CRITICAL"),
    ("NOT_AFFECTED", "HIGH"), ("NOT_AFFECTED", "CRITICAL")])
def test_complete_authenticated_review(tmp_path, status, severity):
    c = case_factory(tmp_path, status, severity)
    result = check(c)
    assert result["decision"] == "pass"
    assert result["cleared_finding_count"] == 1
    assert result["disposition_document_sha256"] == v.canonical_digest(c["doc"])


def test_clean_image_is_not_a_fabricated_disposition(tmp_path):
    c = case_factory(tmp_path, severity="CLEAN")
    assert check(c)["cleared_finding_count"] == 0


@pytest.mark.parametrize("status,severity", [
    ("FIXED", "HIGH"), ("NOT_AFFECTED", "CRITICAL")])
def test_unresolved_severe(tmp_path, status, severity):
    c = case_factory(tmp_path, status, severity)
    c["doc"]["records"] = []
    resign_document(c)
    with pytest.raises(v.DispositionError):
        check(c)


def test_unknown_always_blocks(tmp_path):
    c = case_factory(tmp_path, severity="UNKNOWN")
    with pytest.raises(v.DispositionError, match="UNKNOWN"):
        check(c)


@pytest.mark.parametrize("name,mutator", [
    ("wrong_source", lambda c: c["context"].update(source_sha="f" * 40)),
    ("wrong_lock", lambda c: c["doc"].update(release_lock_sha256="sha256:" + "f" * 64)),
    ("wrong_r3", lambda c: c["doc"].update(r3_run_id=999)),
    ("wrong_scan", lambda c: c["doc"].update(scan_run_id=999)),
    ("wrong_cve", lambda c: c["doc"]["records"][0]["subject"].update(cve_id="CVE-2099-9999")),
    ("wrong_target", lambda c: c["doc"]["records"][0]["subject"].update(target="alpine")),
    ("wrong_ecosystem", lambda c: c["doc"]["records"][0]["subject"].update(ecosystem="alpine")),
    ("wrong_version", lambda c: c["doc"]["records"][0]["subject"].update(installed_version="999")),
    ("wrong_component", lambda c: c["doc"]["records"][0]["subject"].update(component="music")),
    ("wrong_manifest", lambda c: c["doc"]["records"][0]["subject"].update(manifest_digest="sha256:" + "f" * 64)),
    ("wrong_platform", lambda c: c["doc"]["records"][0]["subject"].update(platform_digest="sha256:" + "f" * 64)),
    ("wrong_finding", lambda c: c["doc"]["records"][0]["subject"].update(finding_sha256="sha256:" + "f" * 64)),
    ("bad_digest", lambda c: c["doc"]["records"][0].update(proof_sha256="*")),
    ("extra_record_key", lambda c: c["doc"]["records"][0].update(approved=True)),
    ("wrong_schema", lambda c: c["doc"].update(schema_version=2)),
    ("wrong_repo", lambda c: c["doc"].update(repository="example/other")),
])
def test_rejects_wrong_binding_even_with_new_signature(tmp_path, name, mutator):
    c = case_factory(tmp_path)
    mutator(c)
    resign_document(c)
    with pytest.raises(v.DispositionError):
        check(c)


def test_original_report_changed(tmp_path):
    c = case_factory(tmp_path)
    c["report"]["Results"][0]["Vulnerabilities"][0]["PkgName"] = "changed"
    put(tmp_path / "security/reports/portal.vuln.json", c["report"])
    with pytest.raises(v.DispositionError, match="Modified original"):
        check(c)


def test_original_sbom_changed(tmp_path):
    c = case_factory(tmp_path)
    (tmp_path / "security/reports/portal.sbom.spdx.json").write_text("{}")
    with pytest.raises(v.DispositionError, match="Modified original"):
        check(c)


def test_mutated_proof_file(tmp_path):
    c = case_factory(tmp_path)
    (tmp_path / "review/proofs/proof.json").write_text("{}")
    with pytest.raises(v.DispositionError, match="Modified or missing proof"):
        check(c)


def test_modified_signed_document(tmp_path):
    c = case_factory(tmp_path)
    c["doc"]["expires_at"] = utc(NOW + timedelta(days=21))
    with pytest.raises(v.DispositionError, match="Modified disposition"):
        check(c)


def test_duplicate_ambiguous_finding(tmp_path):
    c = case_factory(tmp_path)
    c["report"]["Results"][0]["Vulnerabilities"].append(
        copy.deepcopy(c["report"]["Results"][0]["Vulnerabilities"][0]))
    refresh(c)
    with pytest.raises(v.DispositionError, match="Ambiguous duplicate"):
        check(c)


def test_duplicate_review_record(tmp_path):
    c = case_factory(tmp_path)
    c["doc"]["records"].append(copy.deepcopy(c["doc"]["records"][0]))
    resign_document(c)
    with pytest.raises(v.DispositionError, match="Duplicate"):
        check(c)


def test_duplicate_json_keys(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(v.DispositionError, match="Duplicate JSON key"):
        v.load_json(f)


@pytest.mark.parametrize("raw", ['{"a":NaN}', '{"a":1.5}', '{"a":Infinity}'])
def test_invalid_json_numeric_encoding(tmp_path, raw):
    f = tmp_path / "bad.json"
    f.write_text(raw)
    with pytest.raises(v.DispositionError):
        v.load_json(f)


def test_missing_or_bad_reviewer_signature(tmp_path):
    c = case_factory(tmp_path)
    c["signatures"]["signatures"] = []
    with pytest.raises(v.DispositionError):
        check(c)
    resign_document(c)
    c["signatures"]["signatures"][0]["signature_base64"] = "A" * 88
    with pytest.raises(v.DispositionError):
        check(c)


def test_unapproved_signer_workflow(tmp_path):
    c = case_factory(tmp_path)
    c["trust"]["review_workflow"] = ".github/workflows/trivy-digest-security.yml"
    with pytest.raises(v.DispositionError, match="Unauthorized repository"):
        check(c)


def test_self_approval_and_shared_owner_key(tmp_path):
    c = case_factory(tmp_path, status="NOT_AFFECTED", severity="CRITICAL")
    c["trust"]["reviewers"]["github:independent-reviewer"]["public_key_pem"] = public(c["owner"])
    with pytest.raises(v.DispositionError, match="shares owner key"):
        check(c)


def test_critical_na_without_owner_concurrence(tmp_path):
    c = case_factory(tmp_path, status="NOT_AFFECTED", severity="CRITICAL")
    c["signatures"]["signatures"] = c["signatures"]["signatures"][:1]
    with pytest.raises(v.DispositionError, match="owner concurrence"):
        check(c)


@pytest.mark.parametrize("which", ["created_at", "reviewed_at", "expires_at"])
def test_future_or_expired_dates(tmp_path, which):
    c = case_factory(tmp_path)
    if which == "expires_at":
        c["doc"][which] = utc(NOW - timedelta(seconds=1))
    else:
        c["doc"][which] = utc(NOW + timedelta(days=1))
    resign_document(c)
    with pytest.raises(v.DispositionError, match="expired, future"):
        check(c)


def test_over_30_day_review(tmp_path):
    c = case_factory(tmp_path)
    c["doc"]["expires_at"] = utc(NOW + timedelta(days=31))
    resign_document(c)
    with pytest.raises(v.DispositionError):
        check(c)


@pytest.mark.parametrize("field", ["revoked_document_sha256", "superseded_document_sha256"])
def test_revoked_or_superseded(tmp_path, field):
    c = case_factory(tmp_path)
    c["lifecycle"][field].append(v.canonical_digest(c["doc"]))
    c["lifecycle_signature"] = signed(c["owner"], b"foxden.lifecycle.v1\n",
                                       c["lifecycle"])
    with pytest.raises(v.DispositionError, match="Revoked or superseded"):
        check(c)


def test_lifecycle_forgery_and_replay(tmp_path):
    c = case_factory(tmp_path)
    c["lifecycle"]["issued_at"] = utc(NOW - timedelta(days=2))
    with pytest.raises(v.DispositionError):
        check(c)
    c = case_factory(tmp_path)
    c["lifecycle"]["revoked_document_sha256"].append("sha256:" + "f" * 64)
    with pytest.raises(v.DispositionError, match="Invalid or unauthorized"):
        check(c)


def test_fixed_from_other_image_or_unmerged_source(tmp_path):
    c = case_factory(tmp_path)
    c["proof"]["manifest_digest"] = "sha256:" + "f" * 64
    put(tmp_path / "review/proofs/proof.json", c["proof"])
    c["doc"]["records"][0]["proof_sha256"] = v.raw_digest(tmp_path / "review/proofs/proof.json")
    resign_document(c)
    with pytest.raises(v.DispositionError, match="Proof not bound"):
        check(c)
    c = case_factory(tmp_path)
    c["proof"]["source_sha"] = "e" * 40
    put(tmp_path / "review/proofs/proof.json", c["proof"])
    c["doc"]["records"][0]["proof_sha256"] = v.raw_digest(tmp_path / "review/proofs/proof.json")
    resign_document(c)
    with pytest.raises(v.DispositionError, match="Proof for wrong"):
        check(c)


def test_nonreproduction_is_not_proof(tmp_path):
    c = case_factory(tmp_path, status="NOT_AFFECTED")
    c["proof"]["technical_basis"] = "failed-exploit-reproduction"
    c["proof"]["verification_method"] = "Failed exploit reproduction with synthetic input"
    put(tmp_path / "review/proofs/proof.json", c["proof"])
    c["doc"]["records"][0]["proof_sha256"] = v.raw_digest(tmp_path / "review/proofs/proof.json")
    resign_document(c)
    with pytest.raises(v.DispositionError):
        check(c)


def test_nonempty_exception_and_stale_db(tmp_path):
    c = case_factory(tmp_path)
    c["exceptions"]["exceptions"].append({"CVE": "CVE-2099-1000"})
    with pytest.raises(v.DispositionError, match="security exceptions"):
        check(c)
    c["exceptions"]["exceptions"] = []
    c["scanner"]["VulnerabilityDB"]["UpdatedAt"] = utc(NOW - timedelta(days=15))
    put(tmp_path / "security/scanner.json", c["scanner"])
    c["context"]["scanner_metadata_sha256"] = v.raw_digest(tmp_path / "security/scanner.json")
    with pytest.raises(v.DispositionError, match="scanner database"):
        check(c)


def test_expiration_between_r4_and_r5(tmp_path):
    c = case_factory(tmp_path)
    c["doc"]["expires_at"] = utc(NOW + timedelta(hours=1))
    resign_document(c)
    assert check(c)["decision"] == "pass"
    c["lifecycle"]["expires_at"] = utc(NOW + timedelta(hours=6))
    c["lifecycle_signature"] = signed(c["owner"], b"foxden.lifecycle.v1\n",
                                       c["lifecycle"])
    with pytest.raises(v.DispositionError):
        check(c, now=NOW + timedelta(hours=2))


def test_security_producer_cannot_sign_own_disposition(tmp_path):
    c = case_factory(tmp_path)
    c["context"]["producer_actor"] = "github:independent-reviewer"
    c["doc"]["producer_actor"] = "github:independent-reviewer"
    resign_document(c)
    with pytest.raises(v.DispositionError, match="cannot approve own"):
        check(c)
