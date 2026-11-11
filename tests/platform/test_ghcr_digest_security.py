"""Synthetic fail-closed R4 digest producer tests. No registry or live evidence."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from scripts.ghcr_digest_security import (
    EvidenceError, FIRST_PARTY, build_contract, check_manifest, check_scanner,
    check_gh_cli_version, prepare, collect_v2_context, final_v2_contract,
    severe_inventory, strict_load,
)

SOURCE = "a" * 40
UPSTREAM_SHA = "b" * 40
INDEX = "sha256:" + "c" * 64
PLATFORM = "sha256:" + "d" * 64
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def fixture():
    upstream_ref = "docker.io/library/nginx@" + INDEX
    images = {}
    candidates = {}
    for name, repository in {**FIRST_PARTY, "nginx": "docker.io/library/nginx"}.items():
        images[name] = {
            "ref": repository + "@" + INDEX, "platform": "linux/amd64",
            "platform_digest": PLATFORM.removeprefix("sha256:"),
            "source_sha": SOURCE if name in FIRST_PARTY else None,
        }
        if name in FIRST_PARTY:
            candidates[name] = {
                "component": name, "image": repository, "source_sha": SOURCE,
                "digest": INDEX, "platform": "linux/amd64",
                "platform_digest": PLATFORM, "workflow": "ghcr-candidates.yml",
                "run_id": 113,
            }
    services = {"portal": "portal", "music": "music", "music-worker": "music",
                "media": "media", "ingress": "nginx"}
    lock = {
        "version": "1.0.0", "source_sha": SOURCE, "platform": "linux/amd64",
        "publisher": {"workflow": "ghcr-candidates.yml", "run_id": 113,
                      "source_sha": SOURCE},
        "images": images, "services": services, "profiles": ["music", "media"],
    }
    rendered = {"services": {name: {"image": images[component]["ref"]}
                             for name, component in services.items()}}
    signers = {
        "schema_version": 1, "upstream": {
            "nginx": {
                "ref": upstream_ref, "source_repo": "nginxinc/docker-nginx",
                "source_sha": UPSTREAM_SHA, "source_ref": "refs/tags/1.0.0",
                "signer_workflow": "nginxinc/docker-nginx/.github/workflows/build.yml",
            }
        },
    }
    return lock, rendered, candidates, signers


def synthetic_reports(tmp_path, plan, *, severity=None):
    for name, entry in plan.items():
        (tmp_path / f"{name}.manifest.json").write_text(json.dumps({
            "schemaVersion": 2,
            "manifests": [{"platform": {"os": "linux", "architecture": "amd64"},
                           "digest": PLATFORM}],
        }))
        (tmp_path / f"{name}.image-id").write_text("sha256:" + "e" * 64)
        vulnerabilities = []
        if severity and name == "portal":
            vulnerabilities = [{
                "VulnerabilityID": "CVE-2026-12345", "PkgName": "pkg",
                "InstalledVersion": "1.2.3", "Severity": severity,
            }]
        (tmp_path / f"{name}.vuln.json").write_text(json.dumps({
            "ArtifactType": "container_image", "ArtifactName": entry["ref"],
            "Metadata": {"ImageID": "sha256:" + "e" * 64},
            "Results": [{"Target": "rootfs (debian 12)", "Type": "debian",
                         "Vulnerabilities": vulnerabilities}],
        }))
        (tmp_path / f"{name}.sbom.spdx.json").write_text(json.dumps({
            "spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT",
            "creationInfo": {"creators": ["Tool: Trivy"]},
            "packages": [{"name": "pkg", "SPDXID": "SPDXRef-Package-pkg"}],
        }))


def plan_fixture():
    lock, rendered, candidates, signers = fixture()
    return prepare(lock, rendered, candidates, signers, SOURCE, 113)


def metadata(date="2026-11-08T00:00:00Z"):
    return {"Version": "0.76.2", "VulnerabilityDB": {"Version": 2, "UpdatedAt": date}}


def test_positive_complete_contract_and_image_subjects(tmp_path):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan)
    contract = build_contract(plan, tmp_path, metadata(),
                              {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)
    assert contract["schema_version"] == 1
    assert set(contract["images"]) == set(FIRST_PARTY)
    assert set(contract["upstream"]) == {"nginx"}
    assert contract["images"]["music"]["scan_subject"] == INDEX
    assert contract["images"]["portal"]["sbom_sha256"].startswith("sha256:")
    assert contract["upstream"]["nginx"]["provenance_status"] == "verified"
    assert contract["publisher_run_id"] == 113
    assert contract["policy_version"].startswith("v1:")


@pytest.mark.parametrize("mutate", [
    lambda l, r, c, s: l.update(source_sha="f" * 40),
    lambda l, r, c, s: l["publisher"].update(run_id=114),
    lambda l, r, c, s: l["images"].pop("media"),
    lambda l, r, c, s: l["images"]["music"].update(ref="ghcr.io/evil/m@" + INDEX),
    lambda l, r, c, s: l["images"]["portal"].update(platform_digest="f" * 64),
    lambda l, r, c, s: c["portal"].update(source_sha="f" * 40),
    lambda l, r, c, s: c["music"].update(digest="sha256:" + "f" * 64),
    lambda l, r, c, s: c["music"].update(workflow="unknown.yml"),
    lambda l, r, c, s: c.pop("media"),
    lambda l, r, c, s: s["upstream"].pop("nginx"),
    lambda l, r, c, s: s["upstream"]["nginx"].update(ref="docker.io/evil/foo@" + INDEX),
    lambda l, r, c, s: s["upstream"]["nginx"].update(source_sha="bad"),
    lambda l, r, c, s: s["upstream"]["nginx"].update(signer_workflow="evil/build.yml"),
    lambda l, r, c, s: r["services"]["portal"].update(build="."),
    lambda l, r, c, s: r["services"]["portal"].update(image="registry/evil@" + INDEX),
    lambda l, r, c, s: l.update(profiles=["music"]),
])
def test_invalid_lock_candidate_upstream_provenance_or_compose_fails(mutate):
    lock, rendered, candidates, signers = fixture()
    mutate(lock, rendered, candidates, signers)
    with pytest.raises(EvidenceError):
        prepare(lock, rendered, candidates, signers, SOURCE, 113)


def test_upstream_scope_includes_enabled_optional_images():
    lock, rendered, candidates, signers = fixture()
    lock["profiles"].append("jellyfin")
    lock["images"]["jellyfin"] = {
        "ref": "docker.io/jellyfin/jellyfin@" + INDEX,
        "platform": "linux/amd64", "platform_digest": "d" * 64, "source_sha": None,
    }
    lock["services"]["jellyfin"] = "jellyfin"
    rendered["services"]["jellyfin"] = {"image": lock["images"]["jellyfin"]["ref"]}
    with pytest.raises(EvidenceError, match="upstream"):
        prepare(lock, rendered, candidates, signers, SOURCE, 113)
    signers["upstream"]["jellyfin"] = {
        "ref": lock["images"]["jellyfin"]["ref"],
        "source_repo": "jellyfin/jellyfin",
        "source_sha": UPSTREAM_SHA, "source_ref": "refs/tags/v1",
        "signer_workflow": "jellyfin/jellyfin/.github/workflows/release.yml",
    }
    assert "jellyfin" in prepare(lock, rendered, candidates, signers, SOURCE, 113)


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL", "UNKNOWN"])
def test_blocking_vulnerabilities_and_unknown_severity_fail(tmp_path, severity):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan, severity=severity)
    with pytest.raises(EvidenceError, match="finding|vulnerability"):
        build_contract(plan, tmp_path, metadata(),
                       {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)


def test_nonrequired_low_severity_not_hidden(tmp_path):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan, severity="LOW")
    assert build_contract(plan, tmp_path, metadata(),
                          {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)["images"]["portal"]["decision"] == "pass"


@pytest.mark.parametrize("ledger", [
    {"schema_version": 1, "exceptions": [{"finding_id": "CVE-2026-12345", "expires": "2026-11-01"}]},
    {"schema_version": 1, "exceptions": [{"finding_id": "CVE-2026-12345", "expires": "2027-12-01"}]},
    {"schema_version": 1, "exceptions": None},
    {"schema_version": 1},
])
def test_exception_never_laundered_to_pass(tmp_path, ledger):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan)
    with pytest.raises(EvidenceError):
        build_contract(plan, tmp_path, metadata(), ledger, SOURCE, 113, NOW)


@pytest.mark.parametrize("date", ["2026-10-01T00:00:00Z", "2026-11-10T00:00:00Z",
                                  "", "not-a-date"])
def test_stale_future_or_missing_trivy_db_fails(date):
    with pytest.raises(EvidenceError):
        check_scanner(metadata(date), NOW)


@pytest.mark.parametrize("date", [
    "2026-11-08T00:00:00+00:00",
    "2026-11-08T00:00:00.000Z",
    "2026-11-08T00:00Z",
    "2026-11-08T00:00:00-05:00",
])
def test_scanner_timestamp_requires_merged_verifier_utc_seconds(date):
    with pytest.raises(EvidenceError, match="UTC whole-second"):
        check_scanner(metadata(date), NOW)


def test_exact_scanner_version_required():
    record = metadata()
    record["Version"] = "0.77.0"
    with pytest.raises(EvidenceError):
        check_scanner(record, NOW)


def test_drifted_platform_manifest_fails():
    plan = plan_fixture()
    with pytest.raises(EvidenceError):
        check_manifest("music", plan, {
            "schemaVersion": 2, "manifests": [{
                "digest": "sha256:" + "f" * 64,
                "platform": {"os": "linux", "architecture": "amd64"},
            }],
        })


def test_absent_report_sbom_wrong_subject_or_config_id_fails(tmp_path):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan)
    report = tmp_path / "portal.vuln.json"
    data = json.loads(report.read_text())
    data["ArtifactName"] = "ghcr.io/evil/ref@" + INDEX
    report.write_text(json.dumps(data))
    with pytest.raises(EvidenceError):
        build_contract(plan, tmp_path, metadata(),
                       {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)
    synthetic_reports(tmp_path, plan)
    (tmp_path / "media.sbom.spdx.json").unlink()
    with pytest.raises(OSError):
        build_contract(plan, tmp_path, metadata(),
                       {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)
    synthetic_reports(tmp_path, plan)
    (tmp_path / "music.image-id").write_text("sha256:" + "f" * 64)
    with pytest.raises(EvidenceError):
        build_contract(plan, tmp_path, metadata(),
                       {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)


def test_consumer_exact_v1_field_schema_and_hash_canonicalization(tmp_path):
    """Frozen from PR #81 head 6e2af6b; no consumers imported across branches."""
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan)
    policy = {"schema_version": 1, "exceptions": []}
    contract = build_contract(plan, tmp_path, metadata(), policy, SOURCE, 113, NOW)
    assert set(contract) == {
        "schema_version", "producer", "source_sha", "publisher_run_id", "platform",
        "scanner", "policy_version", "images", "upstream",
    }
    assert contract["producer"] == ".github/workflows/trivy-digest-security.yml"
    assert contract["scanner"] == {
        "name": "trivy", "version": "0.76.2",
        "db_updated_at": "2026-11-08T00:00:00Z",
    }
    # Cross-check the exact independently coded R4 canonicalization and no spaces.
    expected = "v1:" + hashlib.sha256(json.dumps(
        policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert contract["policy_version"] == expected
    for component in FIRST_PARTY:
        record = contract["images"][component]
        assert set(record) == {
            "ref", "platform_digest", "source_sha", "provenance", "sbom_format",
            "sbom_sha256", "sbom_subject", "vulnerability_report_sha256",
            "scan_subject", "decision", "exceptions",
        }
    assert set(contract["upstream"]["nginx"]) == {
        "ref", "platform_digest", "scan_subject", "sbom_subject",
        "sbom_sha256", "vulnerability_report_sha256", "decision",
        "exceptions", "provenance_status",
    }
    for name, record in {**contract["images"], **contract["upstream"]}.items():
        assert record["vulnerability_report_sha256"] == (
            "sha256:" + hashlib.sha256((tmp_path / f"{name}.vuln.json").read_bytes()).hexdigest()
        )
        assert record["sbom_sha256"] == (
            "sha256:" + hashlib.sha256((tmp_path / f"{name}.sbom.spdx.json").read_bytes()).hexdigest()
        )
        assert record["ref"] == plan[name]["ref"]
        assert record["scan_subject"] == plan[name]["digest"]
        assert record["sbom_subject"] == plan[name]["digest"]


@pytest.mark.parametrize("db_version", [None, 0, -1, "2", True])
def test_scanner_database_schema_version_strict(tmp_path, db_version):
    data = metadata()
    data["VulnerabilityDB"]["Version"] = db_version
    with pytest.raises(EvidenceError, match="database|metadata"):
        check_scanner(data, NOW)


def test_scanner_db_fresh_and_exact_14_day_boundary():
    assert check_scanner(metadata("2026-11-08T00:00:00Z"), NOW)["version"] == "0.76.2"
    assert check_scanner(metadata("2026-10-25T00:00:00Z"), NOW)["db_updated_at"]
    with pytest.raises(EvidenceError, match="expired"):
        check_scanner(metadata("2026-10-24T23:59:59Z"), NOW)


@pytest.mark.parametrize("version", [
    "2.101.0", "2.101.99", "2.102", "2.102.0-rc1", "bogus", "2.102.0evil",
    "v2.103.0",
])
def test_untrusted_gh_cli_version_rejected(version):
    with pytest.raises(EvidenceError):
        check_gh_cli_version(version)


@pytest.mark.parametrize("version", ["2.102.0", "2.102.1", "2.110.0", "3.0.0"])
def test_minimum_patched_gh_cli_version_accepted(version):
    check_gh_cli_version(version)


def test_single_manifest_upstream_supported_only_on_exact_platform_digest():
    plan = plan_fixture()
    plan["nginx"]["platform_digest"] = INDEX
    manifest = {
        "schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": "sha256:" + "e" * 64},
        "layers": [{"digest": "sha256:" + "f" * 64}],
    }
    check_manifest("nginx", plan, manifest)
    plan["nginx"]["platform_digest"] = PLATFORM
    with pytest.raises(EvidenceError, match="digest"):
        check_manifest("nginx", plan, manifest)
    manifest["mediaType"] = "application/x-untrusted"
    with pytest.raises(EvidenceError):
        check_manifest("nginx", plan, manifest)


@pytest.mark.parametrize("mutation", ["empty-results", "missing-target", "malformed-findings",
                                      "unknown-severity", "missing-vulnerability-id"])
def test_trivy_incomplete_report_cannot_generate_pass(tmp_path, mutation):
    plan = plan_fixture()
    synthetic_reports(tmp_path, plan)
    report_path = tmp_path / "portal.vuln.json"
    report = json.loads(report_path.read_text())
    if mutation == "empty-results":
        report["Results"] = []
    elif mutation == "missing-target":
        report["Results"][0].pop("Target")
    elif mutation == "malformed-findings":
        report["Results"][0]["Vulnerabilities"] = {"severity": "LOW"}
    else:
        report["Results"][0]["Vulnerabilities"] = [{
            "VulnerabilityID": "CVE-2026-12345" if mutation != "missing-vulnerability-id" else "",
            "PkgName": "pkg", "InstalledVersion": "1.0",
            "Severity": "UNKNOWN" if mutation == "unknown-severity" else "LOW",
        }]
    report_path.write_text(json.dumps(report))
    with pytest.raises(EvidenceError):
        build_contract(plan, tmp_path, metadata(),
                       {"schema_version": 1, "exceptions": []}, SOURCE, 113, NOW)


def test_workflow_signer_and_four_attestation_subjects_are_explicit():
    workflow = Path(".github/workflows/trivy-digest-security.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "environment: ghcr-security" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "check-gh-version" in workflow
    assert '.github/workflows/ghcr-candidates.yml' in workflow
    assert '--signer-workflow "$workflow"' in workflow
    assert '--source-digest "$commit"' in workflow
    assert '--source-ref "$source_ref"' in workflow
    assert 'test "$(docker image inspect --format' in workflow
    assert "packages: read" in workflow and "packages: write" not in workflow
    for path in ("security/security-contract.json", "security/release-lock.json",
                 "security/rendered-release-compose.json", "security/scanner.json"):
        assert workflow.count(path) >= 2
    assert "create-storage-record:" not in workflow


# V2 B is a separate Worker: these are synthetic A/C contract tests, NOT
# a substitute for cryptographic B signatures, environment or live lifecycle.
def v2_fixture(tmp_path, severity=None):
    plan = plan_fixture()
    reports = tmp_path / "reports"
    reports.mkdir()
    synthetic_reports(reports, plan, severity=severity)
    lock, _rendered, _candidates, _signers = fixture()
    # Match the complete R2 lock expected by the independently merged verifier.
    lock.update({"schema_version": 1, "compose_sha256": "f" * 64,
                 "rollback": {"version": "0.9.6", "lock_sha256": "e" * 64}})
    lock_path = tmp_path / "release-lock.json"
    lock_path.write_text(json.dumps(lock))
    scanner_path = tmp_path / "scanner.json"
    scanner_path.write_text(json.dumps(metadata()))
    policy = {"schema_version": 1, "exceptions": []}
    context = collect_v2_context(
        plan, reports, metadata(), policy, lock_path, scanner_path,
        SOURCE, 113, 235, "github:scan-bot", NOW)
    return plan, reports, lock_path, scanner_path, policy, context


def synthetic_review(context, records):
    document = {
        "schema_version": 1, "repository": context["repository"],
        "source_sha": context["source_sha"],
        "producer_actor": context["producer_actor"],
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": context["r3_run_id"],
        "scan_run_id": context["scan_run_id"],
        "created_at": "2026-11-07T00:00:00Z",
        "reviewed_at": "2026-11-07T12:00:00Z",
        "expires_at": "2026-11-20T00:00:00Z",
        "records": records,
    }
    document_hash = "sha256:" + hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    result = {
        "schema_version": 1, "decision": "pass",
        "disposition_document_sha256": document_hash,
        "lifecycle_sha256": "sha256:" + "c" * 64,
        "source_sha": SOURCE,
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": 113, "scan_run_id": 235,
        "reviewed_at": "2026-11-07T12:00:00Z",
        "expires_at": "2026-11-20T00:00:00Z",
        "cleared_finding_count": len(records),
        "image_count": len(context["images"]),
    }
    return document, result


def synthetic_finalize(plan, reports, lock_path, scanner_path, policy, context,
                       document, result, *, now=NOW):
    return final_v2_contract(
        plan, reports, metadata(), policy, lock_path, scanner_path,
        context, result, deepcopy(result), json.dumps(result).encode(),
        document, SOURCE, 113, 235, "github:scan-bot", 236, now)


def test_v2_collection_does_not_suppress_or_block_real_high_findings(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "HIGH")
    assert set(context) == {
        "schema_version", "repository", "source_sha", "producer_actor",
        "release_lock_sha256", "r3_run_id", "scan_run_id",
        "scanner_metadata_sha256", "images",
    }
    assert set(context["images"]) == set(plan)
    assert context["images"]["portal"]["trivy_report_sha256"] == (
        "sha256:" + hashlib.sha256((reports / "portal.vuln.json").read_bytes()).hexdigest()
    )
    assert json.loads((reports / "portal.vuln.json").read_text())[
        "Results"][0]["Vulnerabilities"][0]["Severity"] == "HIGH"


def test_v2_strict_positive_reviewed_contract_uses_no_v1_fallback(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "CRITICAL")
    item = next(iter(severe_inventory(context, reports).values()))
    record = {"status": "NOT_AFFECTED", "subject": item,
              "proof_path": "proofs/review.json",
              "proof_sha256": "sha256:" + "d" * 64,
              "reviewer_id": "github:independent-reviewer"}
    document, result = synthetic_review(context, [record])
    contract = synthetic_finalize(
        plan, reports, lock, scanner, policy, context, document, result)
    assert contract["schema_version"] == 2
    assert contract["disposition_review"]["artifact_name"] == "security-disposition-review-v1"
    assert contract["disposition_review"]["review_run_id"] == 236
    assert contract["images"]["portal"]["decision"] == "pass"
    assert contract["images"]["portal"]["exceptions"] == []


@pytest.mark.parametrize("mutation", ["wrong-source", "wrong-lock", "wrong-scan",
                                       "wrong-image", "forged-decision", "stale",
                                       "altered-document", "wrong-count"])
def test_v2_rejects_misbound_forged_or_stale_independent_result(tmp_path, mutation):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "HIGH")
    subject = next(iter(severe_inventory(context, reports).values()))
    document, result = synthetic_review(context, [{
        "status": "FIXED", "subject": subject, "proof_path": "proofs/one.json",
        "proof_sha256": "sha256:" + "d" * 64,
        "reviewer_id": "github:reviewer",
    }])
    if mutation == "wrong-source":
        result["source_sha"] = "f" * 40
    elif mutation == "wrong-lock":
        result["release_lock_sha256"] = "sha256:" + "f" * 64
    elif mutation == "wrong-scan":
        result["scan_run_id"] = 344
    elif mutation == "wrong-image":
        subject["manifest_digest"] = "sha256:" + "e" * 64
    elif mutation == "forged-decision":
        result["decision"] = "approved"
    elif mutation == "stale":
        result["expires_at"] = "2026-11-07T13:00:00Z"
    elif mutation == "altered-document":
        document["records"][0]["status"] = "NOT_AFFECTED"
    elif mutation == "wrong-count":
        result["cleared_finding_count"] = 0
    with pytest.raises(EvidenceError):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, document, result)


def test_v2_missing_unreviewed_severe_inventory_fails(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "CRITICAL")
    document, result = synthetic_review(context, [])
    with pytest.raises(EvidenceError, match="HIGH/CRITICAL"):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, document, result)


def test_v2_unknown_severity_collected_but_rejected_at_final_review(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "UNKNOWN")
    document, result = synthetic_review(context, [])
    with pytest.raises(EvidenceError, match="UNKNOWN"):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, document, result)


def test_v2_missing_or_mutated_raw_evidence_is_rejected(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path)
    report_path = reports / "portal.vuln.json"
    report = strict_load(report_path)
    report["Results"][0]["Target"] = "substituted target"
    report_path.write_text(json.dumps(report))
    document, result = synthetic_review(context, [])
    with pytest.raises(EvidenceError, match="context"):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, document, result)
    report_path.unlink()
    with pytest.raises((EvidenceError, OSError)):
        collect_v2_context(plan, reports, metadata(), policy, lock,
                           scanner, SOURCE, 113, 235, "github:scan-bot", NOW)


def test_v2_strict_duplicate_json_and_missing_enabled_images(tmp_path):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path)
    bad = tmp_path / "duplicate.json"
    bad.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(EvidenceError, match="Duplicate"):
        strict_load(bad)
    plan.pop("nginx")
    with pytest.raises(EvidenceError):
        collect_v2_context(plan, reports, metadata(), policy,
                           lock, scanner, SOURCE, 113, 235, "github:scan-bot", NOW)


def test_v2_manual_a_c_workflow_and_independent_crypto_gate_are_explicit():
    workflow = Path(".github/workflows/trivy-digest-security.yml").read_text()
    assert "options: [collect, finalize]" in workflow
    assert "ghcr-security-contract-v2-inputs" in workflow
    assert "ghcr-security-contract-v2" in workflow
    assert "python -m scripts.ghcr_digest_security finalize-v2" in workflow
    assert "ghcr-security-contract-v1" not in workflow
    assert "security-disposition-review-v1" in workflow
    assert ".github/workflows/security-disposition-review.yml" in workflow
    assert "--signer-workflow" in workflow and "--source-digest" in workflow
    assert "--expected-producer-actor" in workflow
    assert "--lifecycle-signature" in workflow and "--trust trusted/trust.json" in workflow
    assert "cmp reviewed/security/disposition-verification.json trusted/revalidated.json" in workflow
    assert "scripts/verify_security_dispositions.py verify" in workflow
    assert "environment: ghcr-security" in workflow
    assert "packages: write" not in workflow
    assert "actions/attest@" in workflow


@pytest.mark.parametrize("variation", [
    "same", "changed-severity", "changed-fixed-version",
    "changed-description", "other-result",
])
def test_v2_collection_rejects_conflicting_underlying_findings(tmp_path, variation):
    """Mirrors the three corrected #93 cases: identity excludes scanner metadata."""
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path, "HIGH")
    report_path = reports / "portal.vuln.json"
    report = strict_load(report_path)
    first = report["Results"][0]["Vulnerabilities"][0]
    alternate = deepcopy(first)
    if variation == "changed-severity":
        alternate["Severity"] = "LOW"
    elif variation == "changed-fixed-version":
        alternate["FixedVersion"] = "9.9.9"
    elif variation == "changed-description":
        alternate["Description"] = "Metadata altered, same CVE/package occurrence"
    if variation == "other-result":
        second_result = deepcopy(report["Results"][0])
        second_result["Vulnerabilities"] = [alternate]
        report["Results"].append(second_result)
    else:
        report["Results"][0]["Vulnerabilities"].append(alternate)
    report_path.write_text(json.dumps(report))
    with pytest.raises(EvidenceError, match="Ambiguous duplicate finding identity"):
        collect_v2_context(plan, reports, metadata(), policy,
                           lock, scanner, SOURCE, 113, 235, "github:scan-bot", NOW)


@pytest.mark.parametrize("field", ["context", "review"])
def test_v2_strict_schema_integer_disallows_json_boolean(tmp_path, field):
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path)
    document, verified = synthetic_review(context, [])
    if field == "context":
        context["schema_version"] = True
    else:
        verified["schema_version"] = True
    with pytest.raises(EvidenceError):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, document, verified)


def test_v2_merged_verifier_adapter_rejects_v1_or_forged_review_hash(tmp_path):
    from scripts.verify_security_dispositions import (
        DispositionError, require_r4_contract_v2,
    )
    plan, reports, lock, scanner, policy, context = v2_fixture(tmp_path)
    document, reviewed = synthetic_review(context, [])
    signed_bytes = json.dumps(reviewed).encode()
    contract = synthetic_finalize(plan, reports, lock, scanner, policy,
                                  context, document, reviewed)
    # Structural compatibility with the actual merged #93 helper, not a
    # replacement for B's independent Ed25519/OIDC cryptographic verification.
    require_r4_contract_v2(contract, reviewed, signed_bytes)
    contract["schema_version"] = 1
    with pytest.raises(DispositionError):
        require_r4_contract_v2(contract, reviewed, signed_bytes)
    contract["schema_version"] = 2
    contract["disposition_review"]["verification_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(DispositionError):
        require_r4_contract_v2(contract, reviewed, signed_bytes)


def test_v2_workflow_checks_actual_environment_and_independent_review_actor():
    workflow = Path(".github/workflows/trivy-digest-security.yml").read_text()
    assert workflow.count('environments/ghcr-security') == 2
    assert workflow.count('".protected == true"') == 0  # jq uses single quotes
    assert workflow.count(".protected == true") == 2
    assert "required_reviewers" in workflow
    assert 'test "$SCAN_ACTOR" != "$REVIEW_ACTOR"' in workflow
    assert '.inputs.stage == "collect"' in workflow
    assert "ghcr-security-contract-v1" not in workflow
    assert "ghcr-security-contract-v2" in workflow


# Regression for F-01 and the independent Issue #94 verifier's binary64
# finite-decimal contract. No real scan, review signature, or CVE is claimed.
def decimal_trivy_fixture(tmp_path, *, severity="HIGH", score_text="3.7"):
    plan, reports, lock, scanner, policy, _ = v2_fixture(tmp_path, severity)
    report_path = reports / "portal.vuln.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    vuln = report["Results"][0]["Vulnerabilities"][0]
    vuln["CVSS"] = {
        "redhat": {"V2Vector": "AV:N/AC:L/Au:N/C:P/I:P/A:P",
                   "V2Score": 3.7, "V3Score": 7.8},
        "nvd": {"V3Score": 8.1},
    }
    report["Results"][0]["Class"] = "os-pkgs"
    raw = json.dumps(report, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8") + b"\n"
    assert b'"V2Score":3.7' in raw
    raw = raw.replace(b'"V2Score":3.7', b'"V2Score":' + score_text.encode("ascii"))
    report_path.write_bytes(raw)
    context = collect_v2_context(
        plan, reports, metadata(), policy, lock, scanner,
        SOURCE, 113, 235, "github:scan-bot", NOW)
    return plan, reports, lock, scanner, policy, context, report_path


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_original_nested_finite_cvss_preserved_in_a_and_reviewed_c(tmp_path, severity):
    plan, reports, lock, scanner, policy, context, path = decimal_trivy_fixture(
        tmp_path, severity=severity)
    original_bytes = path.read_bytes()
    original_hash = "sha256:" + hashlib.sha256(original_bytes).hexdigest()
    parsed = strict_load(path, scanner_evidence=True)
    vulnerability = parsed["Results"][0]["Vulnerabilities"][0]
    assert vulnerability["CVSS"]["redhat"]["V2Score"] == 3.7
    assert vulnerability["CVSS"]["redhat"]["V3Score"] == 7.8
    assert vulnerability["CVSS"]["nvd"]["V3Score"] == 8.1
    assert context["images"]["portal"]["trivy_report_sha256"] == original_hash
    # Collection is not a pass. It still contains a severe finding and
    # preserves every raw Trivy byte for independent human review.
    assert parsed["Results"][0]["Vulnerabilities"][0]["Severity"] == severity
    subject = severe_inventory(context, reports)[("portal", 0, 0)]
    canonical = json.dumps(vulnerability, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode()
    assert subject["finding_sha256"] == (
        "sha256:" + hashlib.sha256(canonical).hexdigest())
    assert b'"V2Score":3.7' in canonical
    record = {"status": "FIXED", "subject": subject, "proof_path": "proofs/synthetic.json",
              "proof_sha256": "sha256:" + "d" * 64,
              "reviewer_id": "github:synthetic-independent-reviewer"}
    document, reviewed = synthetic_review(context, [record])
    # This is *only* the C structural/hash adapter: B's independently
    # authenticated Ed25519 review and lifecycle remain mandatory at runtime.
    contract = synthetic_finalize(plan, reports, lock, scanner, policy,
                                  context, document, reviewed)
    assert contract["schema_version"] == 2
    assert contract["images"]["portal"]["decision"] == "pass"
    assert contract["images"]["portal"]["vulnerability_report_sha256"] == original_hash
    assert path.read_bytes() == original_bytes


def test_original_cvss_lexical_variation_changes_raw_hash_not_canonical_finding(tmp_path):
    plan, reports, lock, scanner, policy, first, path = decimal_trivy_fixture(
        tmp_path, score_text="3.7")
    original = path.read_bytes()
    first_finding = severe_inventory(first, reports)[("portal", 0, 0)]["finding_sha256"]
    alternate = original.replace(b'"V2Score":3.7', b'"V2Score":3.700')
    assert original != alternate
    path.write_bytes(alternate)
    second = collect_v2_context(plan, reports, metadata(), policy, lock,
                                scanner, SOURCE, 113, 235, "github:scan-bot", NOW)
    second_finding = severe_inventory(second, reports)[("portal", 0, 0)]["finding_sha256"]
    assert second_finding == first_finding
    assert first["images"]["portal"]["trivy_report_sha256"] != (
        second["images"]["portal"]["trivy_report_sha256"])
    assert strict_load(path, scanner_evidence=True)["Results"][0][
        "Vulnerabilities"][0]["CVSS"]["redhat"]["V2Score"] == 3.7


def test_modified_original_cvss_report_cannot_reuse_signed_a_context(tmp_path):
    plan, reports, lock, scanner, policy, context, path = decimal_trivy_fixture(tmp_path)
    doc, result = synthetic_review(context, [{
        "status": "FIXED",
        "subject": severe_inventory(context, reports)[("portal", 0, 0)],
        "proof_path": "proofs/synthetic.json",
        "proof_sha256": "sha256:" + "d" * 64,
        "reviewer_id": "github:synthetic-reviewer",
    }])
    original = path.read_bytes()
    path.write_bytes(original.replace(b'"V2Score":3.7', b'"V2Score":3.8'))
    assert path.read_bytes() != original
    with pytest.raises(EvidenceError, match="Altered signed A"):
        synthetic_finalize(plan, reports, lock, scanner, policy,
                           context, doc, result)


@pytest.mark.parametrize("bad_number", [
    "NaN", "Infinity", "-Infinity", "1e309", "-1e309", "9.9e99999",
])
def test_original_trivy_nonfinite_cvss_is_rejected(tmp_path, bad_number):
    path = tmp_path / "report.vuln.json"
    path.write_text('{"CVSS":{"nvd":{"V3Score":' + bad_number + '}}}',
                    encoding="utf-8")
    with pytest.raises(EvidenceError, match="numeric|Nonfinite"):
        strict_load(path, scanner_evidence=True)


def test_original_trivy_nested_duplicate_cvss_field_is_rejected(tmp_path):
    path = tmp_path / "report.vuln.json"
    path.write_text('{"CVSS":{"nvd":{"V3Score":3.7,"V3Score":8.1}}}',
                    encoding="utf-8")
    with pytest.raises(EvidenceError, match="Duplicate"):
        strict_load(path, scanner_evidence=True)


@pytest.mark.parametrize("payload", [
    '{"schema_version":1.0}', '{"r3_run_id":2.0}',
    '{"CVSS":{"nvd":{"V3Score":3.7}}}',
])
def test_signed_control_and_default_evidence_loader_stay_decimal_strict(tmp_path, payload):
    path = tmp_path / "control.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(EvidenceError, match="numeric"):
        strict_load(path)


def test_spdx_and_scanner_metadata_are_not_decimal_scanner_evidence(tmp_path):
    plan, reports, lock, scanner, policy, context, path = decimal_trivy_fixture(tmp_path)
    spdx = reports / "portal.sbom.spdx.json"
    spdx.write_text(spdx.read_text()[:-1] + ',"unexpected":3.7}')
    with pytest.raises(EvidenceError, match="numeric"):
        collect_v2_context(plan, reports, metadata(), policy, lock, scanner,
                           SOURCE, 113, 235, "github:scan-bot", NOW)
    spdx.unlink()
    control = tmp_path / "scanner.json"
    control.write_text('{"Version":"0.76.2","VulnerabilityDB":{"Version":1.0}}')
    with pytest.raises(EvidenceError, match="numeric"):
        strict_load(control)


@pytest.mark.parametrize("bad_bytes", [
    b'{"CVSS":',
    b'{"CVSS":"' + bytes([255]) + b'"}',
])
def test_malformed_original_trivy_json_or_utf8_still_fails(tmp_path, bad_bytes):
    path = tmp_path / "report.vuln.json"
    path.write_bytes(bad_bytes)
    with pytest.raises((ValueError, UnicodeError)):
        strict_load(path, scanner_evidence=True)


@pytest.mark.parametrize("severity,status", [
    ("HIGH", "FIXED"), ("CRITICAL", "NOT_AFFECTED"),
])
def test_v2_actual_merged_verifier_authenticates_decimal_a_b_c(
        tmp_path, severity, status):
    """Real merged verifier, synthetic Ed25519 signers and complete R2 evidence.

    No OIDC attestation, live R3 images, owner identity or production review
    is created here. The B decision is computed cryptographically by the
    independent verifier rather than fabricated by the producer fixture.
    """
    import base64
    from datetime import timedelta
    import shutil

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from scripts import verify_security_dispositions as verifier

    plan, reports, lock_path, scanner_path, policy, context, original_path = (
        decimal_trivy_fixture(tmp_path, severity=severity)
    )
    now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)

    # Authenticated Stage A's original byte streams are delivered unmodified
    # to the independently implemented Stage B evidence directory.
    evidence = tmp_path / "authenticated"
    (evidence / "reports").mkdir(parents=True)
    shutil.copyfile(lock_path, evidence / "release-lock.json")
    shutil.copyfile(scanner_path, evidence / "scanner.json")
    for source in reports.glob("*.vuln.json"):
        shutil.copyfile(source, evidence / "reports" / source.name)
    for source in reports.glob("*.sbom.spdx.json"):
        shutil.copyfile(source, evidence / "reports" / source.name)

    report = verifier.load_json(evidence / "reports/portal.vuln.json",
                                scanner_evidence=True)
    vulnerability = report["Results"][0]["Vulnerabilities"][0]
    assert vulnerability["CVSS"]["redhat"]["V2Score"] == 3.7
    assert vulnerability["CVSS"]["redhat"]["V3Score"] == 7.8
    assert vulnerability["CVSS"]["nvd"]["V3Score"] == 8.1
    subject = severe_inventory(context, reports)[("portal", 0, 0)]
    verifier_subject = verifier.finding_subject(
        "portal", 0, 0, report["Results"][0], vulnerability,
        context["images"]["portal"])
    assert subject == verifier_subject
    assert subject["finding_sha256"] == verifier.canonical_digest(vulnerability)
    assert context["images"]["portal"]["trivy_report_sha256"] == (
        verifier.raw_digest(evidence / "reports/portal.vuln.json"))
    assert context["images"]["portal"]["trivy_report_sha256"] == (
        verifier.raw_digest(original_path))

    reviewer = Ed25519PrivateKey.generate()
    owner = Ed25519PrivateKey.generate()
    def utc(value):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    def public(key):
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
    def sign(key, domain, value):
        digest = bytes.fromhex(verifier.canonical_digest(value)[7:])
        return base64.b64encode(key.sign(domain + digest)).decode("ascii")

    proof = {
        "schema_version": 1, "kind": status,
        "source_sha": context["source_sha"],
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": context["r3_run_id"],
        "scan_run_id": context["scan_run_id"],
        "image_repository": subject["image_repository"],
        "manifest_digest": subject["manifest_digest"],
        "platform_digest": subject["platform_digest"],
        "finding_sha256": subject["finding_sha256"],
        "reference_url": "https://security.example.org/synthetic-2099",
        "reference_sha256": "sha256:" + "d" * 64,
        "verification_method": "Inspect exact signed synthetic installed image",
        "binary_sha256": "sha256:" + "e" * 64,
        "installed_version": subject["installed_version"],
        "technical_basis": ("authoritative-remediation-and-installed-image"
                            if status == "FIXED" else
                            "vulnerable-implementation-absent"),
    }
    proof_dir = tmp_path / "review"
    (proof_dir / "proofs").mkdir(parents=True)
    proof_path = proof_dir / "proofs/synthetic.json"
    proof_path.write_bytes(verifier.canonical(proof) + b"\n")
    document = {
        "schema_version": 1, "repository": context["repository"],
        "source_sha": context["source_sha"],
        "producer_actor": context["producer_actor"],
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": context["r3_run_id"],
        "scan_run_id": context["scan_run_id"],
        "created_at": utc(now - timedelta(hours=2)),
        "reviewed_at": utc(now - timedelta(hours=1)),
        "expires_at": utc(now + timedelta(days=20)),
        "records": [{
            "status": status, "subject": subject,
            "proof_path": "proofs/synthetic.json",
            "proof_sha256": verifier.raw_digest(proof_path),
            "reviewer_id": "github:independent-reviewer",
        }],
    }
    signatures = {
        "schema_version": 1,
        "document_sha256": verifier.canonical_digest(document),
        "signatures": [{
            "role": "reviewer", "identity": "github:independent-reviewer",
            "key_id": "independent-synthetic-key",
            "signature_base64": sign(reviewer, b"foxden.dispositions.v1\n", document),
        }],
    }
    if severity == "CRITICAL" and status == "NOT_AFFECTED":
        signatures["signatures"].append({
            "role": "owner", "identity": "github:ItsFoxxin",
            "key_id": "owner-synthetic-key",
            "signature_base64": sign(owner, b"foxden.dispositions.v1\n", document),
        })
    trust = {
        "schema_version": 1, "repository": verifier.REPOSITORY,
        "review_workflow": verifier.REVIEW_WORKFLOW,
        "producer_workflow": verifier.PRODUCER_WORKFLOW,
        "reviewers": {"github:independent-reviewer": {
            "key_id": "independent-synthetic-key",
            "public_key_pem": public(reviewer),
        }},
        "owner": {
            "identity": "github:ItsFoxxin",
            "key_id": "owner-synthetic-key",
            "public_key_pem": public(owner),
        },
    }
    lifecycle = {
        "schema_version": 1,
        "issued_at": utc(now - timedelta(minutes=30)),
        "expires_at": utc(now + timedelta(hours=10)),
        "revoked_document_sha256": [],
        "superseded_document_sha256": [],
    }
    arguments = {
        "context": context, "dispositions": document,
        "signatures": signatures, "lifecycle": lifecycle,
        "lifecycle_signature": sign(owner, b"foxden.lifecycle.v1\n", lifecycle),
        "trust": trust, "evidence_dir": evidence, "proofs_dir": proof_dir,
        "lock_path": evidence / "release-lock.json",
        "scanner": metadata(), "scanner_path": evidence / "scanner.json",
        "exceptions": policy, "expected_source_sha": SOURCE,
        "expected_r3_run_id": 113, "expected_scan_run_id": 235,
        "expected_producer_actor": "github:scan-bot", "now": now,
    }
    independently_verified = verifier.verify(**arguments)
    assert independently_verified["decision"] == "pass"
    assert independently_verified["cleared_finding_count"] == 1
    signed_result_bytes = verifier.canonical(independently_verified) + b"\n"

    final = final_v2_contract(
        plan, reports, metadata(), policy, lock_path, scanner_path,
        context, independently_verified, independently_verified,
        signed_result_bytes, document, SOURCE, 113, 235,
        "github:scan-bot", 236, now)
    verifier.require_r4_contract_v2(
        final, independently_verified, signed_result_bytes)
    assert final["schema_version"] == 2
    assert final["images"]["portal"]["decision"] == "pass"

    if severity == "CRITICAL":
        # Authentic reviewer alone cannot authorize CRITICAL NOT_AFFECTED.
        missing_owner = deepcopy(signatures)
        missing_owner["signatures"] = missing_owner["signatures"][:1]
        with pytest.raises(verifier.DispositionError, match="owner concurrence"):
            verifier.verify(**{**arguments, "signatures": missing_owner})

    # Original bytes are immutable even with otherwise valid signatures.
    signed_report = evidence / "reports/portal.vuln.json"
    signed_report.write_bytes(signed_report.read_bytes().replace(
        b'"V3Score":8.1', b'"V3Score":8.2'))
    with pytest.raises(verifier.DispositionError, match="Modified original"):
        verifier.verify(**arguments)
