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
    check_gh_cli_version, prepare,
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
