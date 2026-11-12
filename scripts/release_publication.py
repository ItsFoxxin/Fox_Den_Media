#!/usr/bin/env python3
"""Fox Den Media R5: validate already-published evidence; never build or deploy.

R3/R4 own image creation, scanning and artifact attestation. This script can
only consume their immutable evidence. The workflow supplies the authorization
boundary, then re-runs these checks immediately before publishing.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import stat
import urllib.error
import urllib.request

from scripts.verify_publisher_checks import (
    REQUIRED as REQUIRED_CHECK_APPS,
    RequiredChecksError,
    verify_checks as verify_publisher_checks,
)

REPOSITORY = "ItsFoxxin/Fox_Den_Media"
VERSION = "1.0.0"
TAG = "v1.0.0"
R4_WORKFLOW = ".github/workflows/ghcr-verify.yml"
R4_SIGNER_WORKFLOW = REPOSITORY + "/" + R4_WORKFLOW
RELEASE_READY_SCHEMA = "foxden.r4.release-ready.v1"
R3_WORKFLOW = "ItsFoxxin/Fox_Den_Media/.github/workflows/ghcr-candidates.yml"
R4_ARTIFACT = "foxden-r4-release-ready-v1.0.0"  # Signed R4-owned artifact
REVIEW_WORKFLOW = ".github/workflows/security-disposition-review.yml"
SCAN_WORKFLOW = ".github/workflows/trivy-digest-security.yml"
REVIEW_ARTIFACT = "security-disposition-review-v1"
REVIEW_FIELDS = {"schema_version", "artifact_name", "verification_file",
                 "verification_sha256", "dispositions_sha256",
                 "review_workflow", "review_run_id", "verified_at"}
RESULT_FIELDS = {"schema_version", "decision", "disposition_document_sha256",
                 "lifecycle_sha256", "source_sha", "release_lock_sha256",
                 "r3_run_id", "scan_run_id", "reviewed_at", "expires_at",
                 "cleared_finding_count", "image_count"}
OWNER_STATE_VARIABLES = ("SECURITY_DISPOSITION_TRUST_B64",
                         "SECURITY_DISPOSITION_LIFECYCLE_B64",
                         "SECURITY_DISPOSITION_LIFECYCLE_SIG_B64",
                         "SECURITY_DISPOSITION_LIFECYCLE_SHA256")
REVIEW_PROOF = re.compile(r"proofs/([a-z0-9_-]+)\.json\Z")
UTC_SECONDS = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FIRST_PARTY = {
    "portal": "ghcr.io/itsfoxxin/fox-den-media-portal",
    "music": "ghcr.io/itsfoxxin/fox-den-media-music",
    "media": "ghcr.io/itsfoxxin/fox-den-media-media",
}
REQUIRED_CHECKS = tuple(REQUIRED_CHECK_APPS)
# Protected-main ruleset 26667058; no unapproved publisher substitution.
PROTECTED_MAIN_CHECK_APPS = {
    "Monorepo strict gate": 15368,
    "CodeQL (python)": 15368,
    "CodeQL (javascript-typescript)": 15368,
    "CodeQL": 57789,
}
CHECK_PAGE_SIZE = 100
MAX_CHECK_RUNS = 10_000
NOTE_HEADINGS = (
    "Release summary", "Major features", "Bug fixes", "Security changes",
    "Compatibility", "Installation and upgrade", "Images and immutable digests",
    "SBOM", "Build provenance", "Checksums", "Known limitations",
    "Rollback", "Documentation",
)


class ReleaseBlocked(ValueError):
    """A release precondition or source/artifact identity was not met."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReleaseBlocked(reason)


def read_json(path: Path) -> dict:
    def reject_duplicate_keys(items):
        obj = {}
        for key, value in items:
            require(key not in obj, "Duplicate JSON key in evidence: " + key)
            obj[key] = value
        return obj
    data = json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=reject_duplicate_keys)
    require(isinstance(data, dict), "Expected a JSON object: " + str(path))
    return data


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def validate_extracted_artifact(root: Path) -> None:
    """Reject symlink/special/unsafe artifact entries before copying to workspace.

    The workflow gates gh >= 2.102.0 *before* any gh run download and extracts
    into a fresh private RUNNER_TEMP directory, never directly into repo state.
    """
    require(root.is_dir() and not root.is_symlink(),
            "Missing or unsafe isolated R5 artifact extraction directory")
    root_resolved = root.resolve()
    require((root / "release-ready.json").is_file() and
            not (root / "release-ready.json").is_symlink(),
            "Missing regular signed R4 release-ready root")
    entries = 0
    for item in root.rglob("*"):
        entries += 1
        require(entries <= 20_000,
                "Oversized untrusted artifact path inventory")
        relative = item.relative_to(root)
        require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and
                    part not in (".", "..") and
                    not part.startswith(".") for part in relative.parts),
                "Unsafe extracted artifact path")
        require(not item.is_symlink() and
                item.resolve().is_relative_to(root_resolved),
                "Symlink or escaping R5 artifact path")
        mode = item.stat(follow_symlinks=False).st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode),
                "Nonregular file in downloaded R5 evidence")
    require(entries > 0, "Empty extracted R5 artifact")


def safe_file(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and not relative.startswith("/"),
            "Invalid artifact path")
    path = Path(relative)
    require(".." not in path.parts and "." not in path.parts and "\\" not in relative,
            "Unsafe artifact path")
    resolved_root = root.resolve()
    dest = root / path
    require(dest.is_file() and not dest.is_symlink(), "Missing or symlinked evidence: " + relative)
    require(dest.resolve().is_relative_to(resolved_root), "Evidence escapes artifact directory")
    return dest


def validate_checks(payload: dict, source_sha: str) -> None:
    """Reuse merged R3 check provenance; no weaker R5 approval shortcut."""
    require(REQUIRED_CHECK_APPS == PROTECTED_MAIN_CHECK_APPS,
            "Protected-main required publisher mapping changed; owner review required")
    try:
        verify_publisher_checks(payload, source_sha)
    except (RequiredChecksError, TypeError, AttributeError) as exc:
        raise ReleaseBlocked("Unauthenticated or incomplete required source checks: " +
                             str(exc)) from exc


def fetch_all_check_runs(source_sha: str) -> dict:
    """Fetch filter=all, every page; fail closed on incomplete/racing snapshots.

    GitHub returns a total_count on each response, but the API is not a
    transactional snapshot. Changed totals, shifted/duplicated IDs, oversized
    or truncated pages cannot be treated as proof of a successful latest run.
    """
    require(valid_sha(source_sha), "Invalid check-run source commit")
    base = ("repos/" + REPOSITORY + "/commits/" + source_sha +
            "/check-runs?filter=all&per_page=100&page=")
    total = None
    collected = []
    page = 1
    while True:
        batch = api(base + str(page))
        require(isinstance(batch, dict) and
                type(batch.get("total_count")) is int and
                0 <= batch["total_count"] <= MAX_CHECK_RUNS and
                type(batch.get("check_runs")) is list,
                "Malformed or oversized GitHub check-run page")
        count = batch["total_count"]
        if total is None:
            total = count
            require(total > 0, "Required check-run history is empty")
        require(count == total, "GitHub check-run total changed during pagination")
        expected = min(CHECK_PAGE_SIZE, total - len(collected))
        require(expected > 0 and len(batch["check_runs"]) == expected,
                "Truncated, duplicated or oversized check-run page")
        collected.extend(batch["check_runs"])
        if len(collected) == total:
            break
        page += 1
    result = {"total_count": total, "check_runs": collected}
    validate_checks(result, source_sha)
    return result


def validate_adopted_policy(content: str) -> None:
    require("PR #63" in content
            and "Before source promotion" in content
            and "After independent source-promotion approval" in content
            and "Before NAS production cutover" in content
            and "After authorized cutover" in content,
            "Current main release checklist does not contain adopted approval policy")


def validate_master_acceptance_issue(issue: dict) -> None:
    """Issue #18 is a hard release gate regardless of label changes."""
    require(isinstance(issue, dict) and issue.get("number") == 18
            and issue.get("pull_request") is None
            and issue.get("state") == "closed",
            "Master 1.0 NAS acceptance issue #18 is not closed/accepted")


def validate_blockers(items: list) -> None:
    require(isinstance(items, list), "Blocker API response must be a list")
    blockers = [x for x in items if isinstance(x, dict)
                and not x.get("pull_request") and x.get("state") == "open"]
    require(not blockers, "Unresolved release-blocker issues: " +
            ", ".join("#" + str(x.get("number")) for x in blockers))


def validate_r4_run(data: dict, source_sha: str, run_id: int) -> None:
    require(data.get("id") == run_id and run_id > 0, "R4 run ID mismatch")
    require(data.get("repository", {}).get("full_name", "").casefold() == REPOSITORY.casefold(),
            "R4 run belongs to another repository")
    require(str(data.get("path", "")).split("@")[0] == R4_WORKFLOW,
            "R4 run is not from the approved verification workflow")
    require(data.get("event") == "workflow_dispatch" and data.get("head_branch") == "main",
            "R4 run is not an approved main-branch execution")
    require(data.get("head_sha") == source_sha, "R4 run checked a different source SHA")
    require(data.get("status") == "completed" and data.get("conclusion") == "success",
            "R4 verification run has not succeeded")


def validate_notes(notes: str, source_sha: str, lock_sha: str, images: list) -> None:
    headings = set(re.findall(r"^## ([^\n]+)$", notes, flags=re.M))
    for heading in NOTE_HEADINGS:
        require(heading in headings, "Release notes missing: " + heading)
    require(source_sha in notes and lock_sha in notes,
            "Release notes do not identify the exact main source and release lock")
    for image in images:
        if image.get("kind") == "first-party":
            require(image["name"] + "@" + image["digest"] in notes,
                    "Release notes omit a first-party immutable image reference")
    require(not re.search(r"\{\{|TODO|TBD|PLACEHOLDER", notes, flags=re.I),
            "Release notes contain unresolved template placeholders")
    require(not re.search(
        r"\b(?:10|192\.168|172\.(?:1[6-9]|2[0-9]|3[01]))"
        r"\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", notes),
        "Release notes may contain private infrastructure addresses")
    require(not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                          r"(?i:(?:password|api[_-]?key|secret|access[_-]?token)\s*[=:]\s*\S{8,})",
                          notes), "Release notes may contain credentials")



def utc_instant(value: object) -> dt.datetime:
    require(isinstance(value, str) and UTC_SECONDS.fullmatch(value) is not None,
            "Malformed UTC-second review timestamp")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ReleaseBlocked("Invalid review timestamp") from exc


def canonical_hash(document: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def validate_disposition_bundle(root: Path, verification: dict,
                                source_sha: str, lock_sha: str,
                                lock: dict, now: dt.datetime | None = None) -> dict:
    """Only source/byte bindings; real reviewer signatures are checked separately.

    Never infer that a signed R4 'pass' remains a valid disposition at R5 time.
    The independent PR #93 verifier re-checks every occurrence and Ed25519 key.
    """
    binding = verification.get("disposition_review")
    require(isinstance(binding, dict) and set(binding) == REVIEW_FIELDS,
            "Missing or unknown R4 independent disposition-review binding")
    require(binding["schema_version"] == 1
            and binding["artifact_name"] == REVIEW_ARTIFACT
            and binding["verification_file"] == "integration/disposition-verification.json"
            and binding["review_workflow"] == REVIEW_WORKFLOW
            and type(binding["review_run_id"]) is int and binding["review_run_id"] > 0,
            "Wrong independent review workflow, version or run")
    utc_instant(binding["verified_at"])
    require(isinstance(binding["verification_sha256"], str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", binding["verification_sha256"])
            and isinstance(binding["dispositions_sha256"], str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", binding["dispositions_sha256"]),
            "Malformed R4 signed review hashes")
    names = set(verification["files"])
    required = {"integration/disposition-verification.json",
                "integration/security-dispositions.json",
                "integration/security-disposition-signatures.json"}
    require(required <= names, "Missing signed disposition-review input files")
    output_path = safe_file(root, "integration/disposition-verification.json")
    result = read_json(output_path)
    require(set(result) == RESULT_FIELDS and result["schema_version"] == 1
            and result["decision"] == "pass"
            and type(result["cleared_finding_count"]) is int
            and result["cleared_finding_count"] >= 0
            and type(result["image_count"]) is int
            and result["image_count"] == len(lock["images"]),
            "Unrecognized or incomplete independent disposition result")
    require(binding["verification_sha256"] == "sha256:" + hash_file(output_path),
            "Wrong raw signed independent review result hash")
    document = read_json(safe_file(root, "integration/security-dispositions.json"))
    require(set(document) == {"schema_version", "repository", "source_sha",
             "producer_actor", "release_lock_sha256", "r3_run_id",
             "scan_run_id", "created_at", "reviewed_at", "expires_at",
             "records"} and document["schema_version"] == 1
            and document["repository"] == REPOSITORY
            and document["source_sha"] == source_sha
            and isinstance(document["producer_actor"], str)
            and re.fullmatch(r"github:[A-Za-z0-9-]{1,39}", document["producer_actor"])
            and type(document["scan_run_id"]) is int and document["scan_run_id"] > 0
            and type(document["r3_run_id"]) is int
            and document["r3_run_id"] == lock["publisher"]["run_id"]
            and document["release_lock_sha256"] == "sha256:" + lock_sha
            and type(document["records"]) is list,
            "Disposition document has incompatible schema/source/image lock")
    doc_hash = canonical_hash(document)
    require(doc_hash == binding["dispositions_sha256"]
            and result["disposition_document_sha256"] == doc_hash
            and result["source_sha"] == source_sha
            and result["release_lock_sha256"] == "sha256:" + lock_sha
            and result["r3_run_id"] == document["r3_run_id"]
            and result["scan_run_id"] == document["scan_run_id"]
            and result["reviewed_at"] == document["reviewed_at"]
            and result["expires_at"] == document["expires_at"],
            "Signed review document/result/source/R3/scan mismatch")
    utc_instant(document["created_at"])
    reviewed = utc_instant(document["reviewed_at"])
    expires = utc_instant(document["expires_at"])
    now = now or dt.datetime.now(dt.timezone.utc)
    require(utc_instant(document["created_at"]) <= reviewed <= now < expires
            and dt.timedelta(0) < expires - reviewed <= dt.timedelta(days=30),
            "Independent review expired since R4 or has invalid period")
    signatures = read_json(safe_file(root, "integration/security-disposition-signatures.json"))
    require(set(signatures) == {"schema_version", "document_sha256", "signatures"}
            and signatures["schema_version"] == 1
            and signatures["document_sha256"] == doc_hash
            and isinstance(signatures["signatures"], list),
            "Missing or mismatched signed disposition signatures")
    expected_proofs = set()
    for record in document["records"]:
        require(isinstance(record, dict)
                and set(record) == {"status", "subject", "proof_path",
                                   "proof_sha256", "reviewer_id"}
                and record["status"] in ("FIXED", "NOT_AFFECTED")
                and isinstance(record["proof_path"], str),
                "Unsupported independent disposition record")
        match = REVIEW_PROOF.fullmatch(record["proof_path"])
        require(match is not None, "Unrecognized disposition proof path")
        flat = "integration/disposition-proof-" + match.group(1) + ".json"
        require(flat not in expected_proofs and flat in names,
                "Missing/duplicate original signed disposition proof")
        expected_proofs.add(flat)
        require(record.get("proof_sha256") == "sha256:" + hash_file(safe_file(root, flat)),
                "Disposition proof raw-byte SHA-256 mismatch")
    actual_proofs = {name for name in names
                     if name.startswith("integration/disposition-proof-")}
    require(expected_proofs == actual_proofs,
            "Unexpected or missing original signed disposition proof")
    require(result["cleared_finding_count"] == len(document["records"]),
            "Reviewed severe finding count does not match signed records")
    contract = read_json(safe_file(root, "security-contract.json"))
    contract_binding = contract.get("disposition_review")
    require(type(contract.get("schema_version")) is int
            and contract["schema_version"] == 2
            and isinstance(contract_binding, dict)
            and set(contract_binding) == REVIEW_FIELDS,
            "Strict security contract v2 required, no v1 fallback")
    require(contract_binding == {
        **binding, "verification_file": "disposition-verification.json",
    }, "R4 v2 security contract and signed root review disagree")
    require(utc_instant(binding["verified_at"]) <= now,
            "Future R4 disposition verification timestamp")
    return {"binding": binding, "result": result, "document": document,
            "lock_sha256": lock_sha}


def validate_bundle(root: Path, source_sha: str, r4_id: int) -> dict:
    """Validate the authoritative R2 lock plus separate R4 security evidence.

    The R2 lock has a strict component-keyed images object. Security reports
    must live in R4 verification.json, never as extra fields in the R2 lock.
    """
    require(valid_sha(source_sha), "Invalid release source SHA")
    require(root.is_dir(), "R4 release-ready evidence bundle is missing")
    verification = read_json(safe_file(root, "verification.json"))
    lock_path = safe_file(root, "release-lock.json")
    lock = read_json(lock_path)
    require(set(lock) == {
        "schema_version", "version", "source_sha", "compose_sha256",
        "platform", "profiles", "images", "services", "rollback", "publisher",
    }, "R4 release lock is not the authoritative R2 schema")
    require(verification.get("schema_version") == 1 and lock["schema_version"] == 1,
            "Unrecognized verification or R2 release-lock schema")
    require(verification.get("version") == VERSION and lock["version"] == VERSION,
            "Release evidence version mismatch")
    require(verification.get("source_sha") == source_sha and lock["source_sha"] == source_sha,
            "Release evidence does not match the approved main source")
    require(verification.get("r4_run_id") == r4_id,
            "R4 verification run identity mismatch")
    publisher = lock["publisher"]
    require(isinstance(publisher, dict)
            and set(publisher) == {"workflow", "run_id", "source_sha"}
            and publisher["workflow"] == "ghcr-candidates.yml"
            and isinstance(publisher["run_id"], int)
            and publisher["run_id"] > 0
            and publisher["source_sha"] == source_sha
            and verification.get("r3_run_id") == publisher["run_id"],
            "R3 candidate publisher identity mismatch")
    require(verification.get("decision") == "pass"
            and verification.get("security_policy_result") == "pass"
            and verification.get("no_rebuild_integration") == "passed",
            "R4 security or no-rebuild integration is not approved")
    require(isinstance(verification.get("security_policy_version"), str)
            and re.fullmatch(r"v1:[0-9a-f]{64}", verification["security_policy_version"]),
            "Missing or unreviewed signed v1 security policy hash")
    require(verification.get("high_critical_unaccepted") == 0,
            "Unaccepted high/critical vulnerability findings")
    source_approval = verification.get("source_promotion_approval")
    require(isinstance(source_approval, dict)
            and source_approval.get("decision") == "approved"
            and source_approval.get("source_sha") == source_sha
            and str(source_approval.get("approved_by", "")).casefold() == "itsfoxxin"
            and isinstance(source_approval.get("record_url"), str)
            and source_approval["record_url"].startswith(
                "https://github.com/ItsFoxxin/Fox_Den_Media/"),
            "Independent source-promotion approval record missing/mismatched")
    require(verification.get("github_security_review") == "pass"
            and verification.get("unapproved_security_findings") == 0,
            "Unreviewed native CodeQL, Dependabot or secret-scanning alerts")

    require(isinstance(lock.get("compose_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", lock["compose_sha256"]) is not None,
            "Invalid Compose source checksum")
    require(lock.get("platform") == "linux/amd64", "Unsupported release platform")
    require(isinstance(lock.get("profiles"), list), "Missing R2 profiles")
    rollback = lock.get("rollback")
    require(isinstance(rollback, dict)
            and set(rollback) == {"version", "lock_sha256"}
            and isinstance(rollback["version"], str)
            and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", rollback["version"]))
            and isinstance(rollback["lock_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", rollback["lock_sha256"]) is not None
            and verification.get("rollback_verified") is True,
            "Verified compatible rollback artifact identity absent")
    # The reviewed R4/Trivy v1 security contract categorically rejects exceptions.
    require(verification.get("exceptions") == [],
            "R4 signed security contract v1 rejects all exceptions")

    source_images = lock.get("images")
    service_map = lock.get("services")
    evidence_map = verification.get("image_evidence")
    require(isinstance(source_images, dict) and source_images,
            "R2 images must be a component-keyed object")
    require(isinstance(service_map, dict) and service_map
            and service_map.get("music") == "music"
            and service_map.get("music-worker") == "music",
            "Music web and worker must map to one image")
    require(isinstance(evidence_map, dict)
            and set(evidence_map) == set(source_images),
            "Missing security evidence for one or more enabled images")
    normalized = []
    required_components = set(FIRST_PARTY)
    for component, details in source_images.items():
        require(isinstance(details, dict) and set(details) == {
            "ref", "platform", "platform_digest", "source_sha",
        }, "Unknown image fields in R2 lock")
        ref = details["ref"]
        require(isinstance(ref, str)
                and re.fullmatch(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}", ref) is not None,
                "R2 image is missing immutable digest")
        name, digest_hex = ref.rsplit("@sha256:", 1)
        digest = "sha256:" + digest_hex
        require(details["platform"] == "linux/amd64"
                and isinstance(details["platform_digest"], str)
                and re.fullmatch(r"[0-9a-f]{64}", details["platform_digest"]) is not None,
                "Invalid image architecture/platform digest")
        evidence = evidence_map[component]
        require(isinstance(evidence, dict)
                and evidence.get("security_decision") == "pass",
                "Image security policy not approved")
        require(evidence.get("ref") == ref
                and evidence.get("platform_digest") == details["platform_digest"],
                "R4 image evidence has a different digest or platform subject")
        require(isinstance(evidence.get("sbom"), str)
                and isinstance(evidence.get("vulnerability_report"), str)
                and isinstance(evidence.get("provenance"), str)
                and evidence["provenance"],
                "Missing digest-bound scan, SBOM or provenance evidence")
        image = {
            "component": component, "name": name, "digest": digest,
            "kind": "first-party" if component in FIRST_PARTY else "upstream",
            "platform": details["platform"],
            "sbom": evidence["sbom"],
            "vulnerability_report": evidence["vulnerability_report"],
            "provenance": evidence["provenance"],
        }
        if component in FIRST_PARTY:
            require(name == FIRST_PARTY[component]
                    and details["source_sha"] == source_sha
                    and evidence.get("candidate_tag") == "sha-" + source_sha
                    , "First-party source or candidate tag missing")
            image["candidate_tag"] = evidence["candidate_tag"]
            required_components.discard(component)
        else:
            require(details["source_sha"] is None
                    and evidence.get("approved_upstream") is True,
                    "Unapproved upstream image or impersonated source identity")
        normalized.append(image)
    require(not required_components, "Missing required first-party image")
    require(set(service_map.values()) == set(source_images),
            "Service mapping and enabled release images differ")

    files = verification.get("files")
    require(isinstance(files, dict) and files, "R4 checksum manifest missing")
    required_files = {"release-lock.json", "release-notes.md",
                      "security-contract.json", "scanner.json",
                      "rendered-release-compose.json"}
    for image in normalized:
        required_files.add(image["sbom"])
        required_files.add(image["vulnerability_report"])
        required_files.add(image["provenance"])
    require(required_files.issubset(files), "Required release evidence missing")
    require("verification.json" not in files, "Self-referential checksum")
    for item in root.rglob("*"):
        require(not item.is_symlink(), "Symlink in release evidence")
    for rel, checksum in files.items():
        require(isinstance(rel, str)
                and (rel in ("release-lock.json", "release-notes.md",
                             "security-contract.json", "scanner.json",
                             "rendered-release-compose.json")
                     or re.fullmatch(
                         r"(?:sboms|provenance|reports|integration)/[A-Za-z0-9_.-]+\.json",
                         rel) is not None),
                "Unapproved or private release evidence path")
        require(isinstance(checksum, str)
                and re.fullmatch(r"[0-9a-f]{64}", checksum) is not None,
                "Malformed evidence checksum")
        require(hash_file(safe_file(root, rel)) == checksum,
                "Evidence hash mismatch: " + rel)
    # verification.json is sealed by the separately signed, versioned root manifest.
    manifest_path = safe_file(root, "release-ready.json")
    manifest = read_json(manifest_path)
    require(set(manifest) == {"schema_version", "version", "repository", "workflow",
                              "source_sha", "r3_run_id", "r4_run_id", "files"},
            "Unknown or missing release-ready manifest fields")
    require(manifest["schema_version"] == RELEASE_READY_SCHEMA
            and manifest["version"] == VERSION
            and manifest["repository"] == REPOSITORY
            and manifest["workflow"] == R4_WORKFLOW
            and manifest["source_sha"] == source_sha
            and manifest["r3_run_id"] == publisher["run_id"]
            and manifest["r4_run_id"] == r4_id,
            "Signed release-ready manifest source, run or workflow mismatch")
    manifest_files = manifest["files"]
    require(isinstance(manifest_files, dict)
            and set(manifest_files) == set(files) | {"verification.json"}
            and all(isinstance(v, str) and
                    re.fullmatch(r"[0-9a-f]{64}", v) for v in manifest_files.values()),
            "Incomplete or malformed signed release-ready file manifest")
    require(all(manifest_files[k] == v for k, v in files.items())
            and manifest_files["verification.json"] == hash_file(
                safe_file(root, "verification.json")),
            "Signed release-ready manifest hash differs from R4 evidence")
    actual_files = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    require(actual_files == set(manifest_files) | {"release-ready.json"},
            "Unexpected or missing signed release evidence files")
    lock_sha = hash_file(lock_path)
    validate_notes(safe_file(root, "release-notes.md").read_text(encoding="utf-8"),
                   source_sha, lock_sha, normalized)
    disposition = validate_disposition_bundle(root, verification, source_sha, lock_sha, lock)
    return {
        "lock_sha256": lock_sha,
        "lock": lock,
        "verification": verification,
        "release_ready": manifest,
        "images": normalized,
        "disposition": disposition,
    }


def validate_approval(comments: list, owner: str, main_sha: str,
                      lock_sha: str, r4_id: int, r4_completed: str) -> None:
    exact = ("APPROVE_FOXDEN_RELEASE " + TAG + " main=" + main_sha +
             " lock_sha256=" + lock_sha + " r4_run_id=" + str(r4_id))
    require(owner and owner.casefold() == "itsfoxxin", "Unexpected owner identity")
    approved = any(
        isinstance(comment, dict)
        and comment.get("user", {}).get("login", "").casefold() == owner.casefold()
        and comment.get("body", "").strip() == exact
        and str(comment.get("created_at", "")) >= r4_completed
        for comment in comments
    )
    require(approved, "Independent owner release-publication approval absent or stale")


def validate_release_absence(tag_ref: object, published_release: object) -> None:
    """No existing version identity may be overwritten or force-retagged."""
    require(tag_ref is None, "Version tag already exists; reject publication")
    require(published_release is None, "GitHub Release already exists; reject publication")


def api(path: str, *, missing_ok: bool = False,
        token: str | None = None) -> dict | list | None:
    token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Missing GitHub Actions API token")
    request = urllib.request.Request(
        "https://api.github.com/" + path.lstrip("/"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if missing_ok and err.code == 404:
            return None
        raise ReleaseBlocked("GitHub verification API unavailable (HTTP " + str(err.code) + ")") from err
    except (TimeoutError, urllib.error.URLError) as err:
        raise ReleaseBlocked("GitHub verification API unavailable") from err


def pages(path: str) -> list:
    items = []
    for page in range(1, 12):
        sep = "&" if "?" in path else "?"
        batch = api(path + sep + "per_page=100&page=" + str(page))
        require(isinstance(batch, list), "Malformed paginated GitHub response")
        items.extend(batch)
        if len(batch) < 100:
            return items
    raise ReleaseBlocked("GitHub pagination limit hit; cannot prove completeness")


def live_check(source_sha: str, r4_id: int, *, approval_issue: int = 0,
               lock_sha: str = "", require_approval: bool = False) -> dict:
    require(os.environ.get("GITHUB_REPOSITORY", "").casefold() == REPOSITORY.casefold(),
            "Untrusted repository")
    require(os.environ.get("GITHUB_REF") == "refs/heads/main",
            "Release workflow must execute on main, never dev or a PR")
    require(os.environ.get("GITHUB_SHA") == source_sha and valid_sha(source_sha),
            "Workflow ref does not match exact approved main SHA")
    require(Path("VERSION").read_text(encoding="utf-8").strip() == VERSION,
            "main has not been approved/promoted to VERSION 1.0.0")
    validate_adopted_policy(
        Path("docs/release-1.0-checklist.md").read_text(encoding="utf-8"))
    branch = api("repos/" + REPOSITORY + "/branches/main")
    require(branch["commit"]["sha"] == source_sha, "main advanced since approval")
    # Both read-only preflight and final publication approval use the exact
    # same complete, GitHub-App-authenticated source check history.
    fetch_all_check_runs(source_sha)
    # Do not depend only on a mutable label; master acceptance is mandatory.
    master = api("repos/" + REPOSITORY + "/issues/18")
    validate_master_acceptance_issue(master)
    blockers = pages("repos/" + REPOSITORY + "/issues?state=open&labels=release-blocker")
    validate_blockers(blockers)
    run = api("repos/" + REPOSITORY + "/actions/runs/" + str(r4_id))
    validate_r4_run(run, source_sha, r4_id)
    tag_ref = api("repos/" + REPOSITORY + "/git/ref/tags/" + TAG, missing_ok=True)
    published_release = api("repos/" + REPOSITORY + "/releases/tags/" + TAG, missing_ok=True)
    validate_release_absence(tag_ref, published_release)
    if require_approval:
        require(approval_issue > 0 and re.fullmatch(r"[0-9a-f]{64}", lock_sha) is not None,
                "Approval issue or release-lock checksum missing")
        issue = api("repos/" + REPOSITORY + "/issues/" + str(approval_issue))
        require(issue.get("pull_request") is None, "Approval target must be an issue, not PR")
        require(issue.get("state") == "open", "Release approval issue is not open")
        comments = pages("repos/" + REPOSITORY + "/issues/" + str(approval_issue) + "/comments")
        validate_approval(comments, REPOSITORY.split("/")[0], source_sha,
                          lock_sha, r4_id, run.get("updated_at", ""))
    return run


def run_command(command: list[str], *, output: bool = False) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    require(result.returncode == 0, "External image/attestation verifier failed: " + command[0:3].__repr__())
    return result.stdout if output else ""



def validate_authenticated_run(data: dict, source_sha: str, run_id: int,
                               workflow: str) -> None:
    require(type(run_id) is int and run_id > 0
            and isinstance(data, dict) and data.get("id") == run_id
            and data.get("repository", {}).get("full_name", "").casefold()
            == REPOSITORY.casefold()
            and str(data.get("path", "")).split("@")[0] == workflow
            and data.get("head_branch") == "main"
            and data.get("head_sha") == source_sha
            and data.get("event") == "workflow_dispatch"
            and data.get("status") == "completed"
            and data.get("conclusion") == "success"
            and type(data.get("run_attempt")) is int
            and data["run_attempt"] > 0,
            "Untrusted, failed, wrong-run or wrong-source disposition producer")



CHAIN_INPUTS = ("source_sha", "publisher_run_id", "scan_run_id",
                "review_run_id", "security_run_id")
CHAIN_R3 = ".github/workflows/ghcr-candidates.yml"


def run_input(run: dict, key: str, expected: str) -> None:
    inputs = run.get("inputs")
    require(isinstance(inputs, dict) and
            isinstance(inputs.get(key), str) and inputs[key] == expected,
            "Missing, stale or mismatched authenticated workflow input: " + key)


def authenticated_chain(*, source_sha: str, r4_run: dict, r3_run: dict,
                        scan_run: dict, review_run: dict, final_run: dict,
                        r3_id: int, scan_id: int, review_id: int,
                        final_id: int) -> None:
    """Independently authenticate R3/A/B/C/R4 before rechecking signed bytes.

    Workflow run inputs link C's otherwise absent ID to the independently
    authenticated R4 run. JSON reports from a producer cannot supply these.
    """
    validate_authenticated_run(r4_run, source_sha, r4_run.get("id"), R4_WORKFLOW)
    for run, ident, workflow in (
        (r3_run, r3_id, CHAIN_R3),
        (scan_run, scan_id, SCAN_WORKFLOW),
        (review_run, review_id, REVIEW_WORKFLOW),
        (final_run, final_id, SCAN_WORKFLOW),
    ):
        validate_authenticated_run(run, source_sha, ident, workflow)
        run_input(run, "source_sha", source_sha)
    require(len({r3_id, scan_id, review_id, final_id, r4_run["id"]}) == 5,
            "Reused candidate/scan/review/finalization/R4 run identity")
    for field, expected in (
        ("source_sha", source_sha), ("publisher_run_id", str(r3_id)),
        ("scan_run_id", str(scan_id)), ("review_run_id", str(review_id)),
        ("security_run_id", str(final_id)),
    ):
        run_input(r4_run, field, expected)
    run_input(scan_run, "stage", "collect")
    run_input(final_run, "stage", "finalize")
    run_input(scan_run, "publisher_run_id", str(r3_id))
    for key, value in (("publisher_run_id", str(r3_id)),
                       ("scan_run_id", str(scan_id)),
                       ("review_run_id", str(review_id))):
        run_input(final_run, key, value)
    run_input(review_run, "r3_run_id", str(r3_id))
    run_input(review_run, "scan_run_id", str(scan_id))
    require(isinstance(scan_run.get("actor"), dict)
            and isinstance(review_run.get("actor"), dict)
            and isinstance(scan_run["actor"].get("login"), str)
            and scan_run["actor"]["login"]
            and isinstance(review_run["actor"].get("login"), str)
            and review_run["actor"]["login"]
            and scan_run["actor"]["login"] != review_run["actor"]["login"],
            "Independent B reviewer workflow actor is the A producer")
    times = [utc_instant(run.get("created_at")) for run in
             (r3_run, scan_run, review_run, final_run, r4_run)]
    require(all(first < later for first, later in zip(times, times[1:])),
            "R3/A/B/C/R4 run sequence is not independent/chronological")


def verify_attested_review_file(path: Path, source_sha: str,
                                workflow: str, run: dict) -> None:
    """Validate GitHub's verified SLSA subject *and* exact workflow run.

    An arbitrary successful run next to an attestation from another run is
    insufficient; require signed SLSA invocationId identifying this run.
    """
    version = run_command(["gh", "--version"], output=True)
    match = re.search(r"^gh version (\d+)\.(\d+)\.(\d+)", version)
    require(match is not None and tuple(map(int, match.groups())) >= (2, 102, 0),
            "gh CLI >= 2.102 required for exact disposition attestation identity")
    payload = run_command([
        "gh", "attestation", "verify", str(path),
        "--repo", REPOSITORY, "--source-ref", "refs/heads/main",
        "--source-digest", source_sha,
        "--signer-workflow", REPOSITORY + "/" + workflow,
        "--predicate-type", "https://slsa.dev/provenance/v1",
        "--format", "json",
    ], output=True)
    try:
        entries = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise ReleaseBlocked("Unparseable GitHub signed review verification") from exc
    expected = "sha256:" + hash_file(path)
    prefix = f"https://github.com/{REPOSITORY}/actions/runs/{run['id']}/attempts/{run['run_attempt']}"
    require(isinstance(entries, list) and any(
        isinstance(item, dict)
        and isinstance(item.get("verificationResult"), dict)
        and isinstance(item["verificationResult"].get("statement"), dict)
        and any(isinstance(sub, dict)
                and isinstance(sub.get("digest"), dict)
                and "sha256:" + str(sub["digest"].get("sha256")) == expected
                for sub in item["verificationResult"]["statement"].get("subject", []))
        and isinstance(item["verificationResult"]["statement"].get("predicate"), dict)
        and item["verificationResult"]["statement"]["predicate"].get(
            "runDetails", {}).get("metadata", {}).get("invocationId") == prefix
        for item in entries),
        "No GitHub-verified exact review subject/signer/run invocation")


def owner_disposition_state(*, latest: bool) -> dict[str, bytes]:
    """Use job-start owner variables for preview; live API for final publish.

    No trust/lifecycle record is accepted from the R4 or review artifacts.
    The publication environment owns the variables-read credential.
    """
    encoded = {name: os.environ.get(name, "") for name in OWNER_STATE_VARIABLES}
    require(all(encoded.values()), "Missing owner-managed disposition trust/lifecycle")
    if latest:
        token = os.environ.get("SECURITY_DISPOSITION_STATE_READ_TOKEN")
        require(bool(token), "Missing protected, read-only latest owner-state credential")
        for name, snapshot in encoded.items():
            data = api("repos/" + REPOSITORY + "/actions/variables/" + name,
                       token=token)
            require(isinstance(data, dict) and data.get("name") == name
                    and isinstance(data.get("updated_at"), str)
                    and isinstance(data.get("value"), str)
                    and data["value"] == snapshot,
                    "Owner trust/lifecycle changed or current state unavailable: " + name)
    try:
        decoded = {name: base64.b64decode(encoded[name], validate=True)
                   for name in OWNER_STATE_VARIABLES[:-1]}
    except (binascii.Error, ValueError) as exc:
        raise ReleaseBlocked("Malformed owner-managed trust/lifecycle encoding") from exc
    require(all(0 < len(value) < 4 * 1024 * 1024 for value in decoded.values()),
            "Missing/oversized owner-signed disposition evidence")
    ledger_digest = encoded["SECURITY_DISPOSITION_LIFECYCLE_SHA256"]
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", ledger_digest) is not None
            and "sha256:" + hashlib.sha256(
                decoded["SECURITY_DISPOSITION_LIFECYCLE_B64"]).hexdigest() == ledger_digest,
            "Current owner lifecycle digest does not match committed state")
    return decoded


def revalidate_current_dispositions(root: Path, summary: dict,
                                    source_sha: str, *, latest: bool) -> None:
    """Never reuse R4's lifecycle snapshot as approval at publication time."""
    disposition = summary["disposition"]
    document = disposition["document"]
    binding = disposition["binding"]
    scan_id = document["scan_run_id"]
    review_id = binding["review_run_id"]
    # The signed R4 manifest does not carry a separate C run field. R4's
    # authenticated workflow_dispatch inputs bind that C run, R3, A and B.
    r4_id = summary["release_ready"]["r4_run_id"]
    r4_run = api("repos/" + REPOSITORY + "/actions/runs/" + str(r4_id))
    r3_id = summary["lock"]["publisher"]["run_id"]
    r3_run = api("repos/" + REPOSITORY + "/actions/runs/" + str(r3_id))
    scan_run = api("repos/" + REPOSITORY + "/actions/runs/" + str(scan_id))
    review_run = api("repos/" + REPOSITORY + "/actions/runs/" + str(review_id))
    inputs = r4_run.get("inputs") if isinstance(r4_run, dict) else None
    candidate_c = inputs.get("security_run_id") if isinstance(inputs, dict) else None
    require(isinstance(candidate_c, str) and
            re.fullmatch(r"[1-9][0-9]*", candidate_c) is not None,
            "Authenticated R4 run does not identify final C security producer")
    final_id = int(candidate_c)
    final_run = api("repos/" + REPOSITORY + "/actions/runs/" + str(final_id))
    authenticated_chain(
        source_sha=source_sha, r4_run=r4_run, r3_run=r3_run,
        scan_run=scan_run, review_run=review_run, final_run=final_run,
        r3_id=r3_id, scan_id=scan_id, review_id=review_id,
        final_id=final_id,
    )
    require(document["producer_actor"] ==
            "github:" + scan_run.get("actor", {}).get("login", ""),
            "Original scan actor differs from signed disposition producer identity")
    # PR #93 independently validates human signature identities and the
    # separately submitted reviewer actor; workflow dispatchers may overlap.
    attested = safe_file(root, "integration/disposition-verification.json")
    verify_attested_review_file(attested, source_sha, REVIEW_WORKFLOW, review_run)
    state = owner_disposition_state(latest=latest)

    # Use original, separately authenticated scan inputs; never reconstruct
    # missing report hashes from current scanner results or R4 summary flags.
    with tempfile.TemporaryDirectory(prefix="r5-disposition-") as temporary:
        staging = Path(temporary)
        security = staging / "security"
        review = staging / "review"
        security.mkdir()
        review.mkdir()
        run_command(["gh", "run", "download", str(scan_id),
                     "--repo", REPOSITORY,
                     "--name", "ghcr-security-contract-v2-inputs",
                     "--dir", str(security)])
        context_path = safe_file(security, "context.json")
        verify_attested_review_file(context_path, source_sha, SCAN_WORKFLOW,
                                    scan_run)
        context = read_json(context_path)
        require(context.get("source_sha") == source_sha
                and context.get("scan_run_id") == scan_id
                and context.get("r3_run_id") == document["r3_run_id"]
                and context.get("producer_actor") == document["producer_actor"]
                and context.get("release_lock_sha256") ==
                "sha256:" + disposition["lock_sha256"],
                "Signed original scan context differs from R4 image/lock identity")
        for name in ("release-lock.json", "scanner.json", "vulnerability-exceptions.json"):
            original = safe_file(security, name)
            reference = (Path("security") / name if name == "vulnerability-exceptions.json"
                         else root / name)
            require(hash_file(original) == hash_file(safe_file(
                reference.parent, reference.name)),
                "Original scan metadata differs from signed R4/main evidence: " + name)
        for component in summary["lock"]["images"]:
            for suffix in (".vuln.json", ".sbom.spdx.json"):
                rel = "reports/" + component + suffix
                require(hash_file(safe_file(security, rel)) ==
                        hash_file(safe_file(root, rel)),
                        "Original scan report/SPDX differs from signed R4 bytes: " + rel)
        # Independently authenticate finalized C, not just R4's assertion.
        # C's OIDC signature must identify the exact finalization run.
        finalized = staging / "final-c"
        finalized.mkdir()
        run_command(["gh", "run", "download", str(final_id),
                     "--repo", REPOSITORY,
                     "--name", "ghcr-security-contract-v2",
                     "--dir", str(finalized)])
        c_contract = safe_file(finalized, "security-contract.json")
        verify_attested_review_file(c_contract, source_sha, SCAN_WORKFLOW,
                                    final_run)
        for name in ("security-contract.json", "release-lock.json",
                     "scanner.json", "rendered-release-compose.json"):
            raw_c = safe_file(finalized, name)
            require(hash_file(raw_c) == hash_file(safe_file(root, name)),
                    "Final C authenticated bytes differ from signed R4: " + name)
        for name in ("context.json", "vulnerability-exceptions.json"):
            require(hash_file(safe_file(finalized, name)) ==
                    hash_file(safe_file(security, name)),
                    "Final C altered signed original A input: " + name)
        require(hash_file(safe_file(finalized,
                                   "review/disposition-verification.json")) ==
                hash_file(attested),
                "Final C independent B review bytes differ from signed R4")
        for component in summary["lock"]["images"]:
            for suffix in (".vuln.json", ".sbom.spdx.json"):
                rel = "reports/" + component + suffix
                require(hash_file(safe_file(finalized, rel)) ==
                        hash_file(safe_file(security, rel)),
                        "Final C changed original scanned evidence: " + rel)
        # R4 maps review/proofs/foo.json to exact integration/disposition-proof-foo.json.
        (review / "proofs").mkdir()
        shutil.copyfile(safe_file(root, "integration/security-dispositions.json"),
                        review / "dispositions.json")
        shutil.copyfile(safe_file(root, "integration/security-disposition-signatures.json"),
                        review / "signatures.json")
        for record in document["records"]:
            match = REVIEW_PROOF.fullmatch(record["proof_path"])
            require(match is not None, "Unsafe signed disposition proof name")
            shutil.copyfile(safe_file(
                root, "integration/disposition-proof-" + match.group(1) + ".json"),
                review / record["proof_path"])
        (review / "trust.json").write_bytes(
            state["SECURITY_DISPOSITION_TRUST_B64"])
        (review / "lifecycle.json").write_bytes(
            state["SECURITY_DISPOSITION_LIFECYCLE_B64"])
        (review / "lifecycle.sig").write_bytes(
            state["SECURITY_DISPOSITION_LIFECYCLE_SIG_B64"])
        output = staging / "current-verification.json"
        run_command([
            sys.executable, "-m", "scripts.verify_security_dispositions", "verify",
            "--context", str(context_path), "--evidence-dir", str(security),
            "--dispositions", str(review / "dispositions.json"),
            "--proofs-dir", str(review), "--signatures", str(review / "signatures.json"),
            "--lifecycle", str(review / "lifecycle.json"),
            "--lifecycle-signature", str(review / "lifecycle.sig"),
            "--trust", str(review / "trust.json"),
            "--lock", str(security / "release-lock.json"),
            "--scanner", str(security / "scanner.json"),
            "--exceptions", str(security / "vulnerability-exceptions.json"),
            "--expected-source-sha", source_sha,
            "--expected-r3-run-id", str(document["r3_run_id"]),
            "--expected-scan-run-id", str(scan_id),
            "--expected-producer-actor", document["producer_actor"],
            "--output", str(output),
        ])
        current = read_json(safe_file(staging, "current-verification.json"))
        prior = disposition["result"]
        require(set(current) == RESULT_FIELDS and current["decision"] == "pass"
                and all(current[key] == prior[key] for key in RESULT_FIELDS -
                        {"lifecycle_sha256"})
                and current["lifecycle_sha256"] != "" and
                re.fullmatch(r"sha256:[0-9a-f]{64}",
                             current["lifecycle_sha256"]) is not None,
                "Current independently signed review does not reproduce R4 decision")
        if latest:
            # Reject a changed owner ledger during computation. No cached R4
            # lifecycle or potentially older environment snapshot can authorize.
            require(owner_disposition_state(latest=True) == state,
                    "Owner revoked or changed reviewer trust during R5 verification")


def verify_registry(lock: dict, source_sha: str) -> None:
    """Read-only registry and cryptographic attestation verification; NO rebuild."""
    for image in lock["images"]:
        reference = image["name"] + "@" + image["digest"]
        manifest = run_command(["docker", "buildx", "imagetools", "inspect", reference], output=True)
        require(image["digest"] in manifest, "Registry manifest mismatch: " + image["name"])
        if image["kind"] != "first-party":
            continue
        tag_ref = image["name"] + ":" + image["candidate_tag"]
        tagged = run_command(["docker", "buildx", "imagetools", "inspect", tag_ref], output=True)
        match = re.search(r"(?m)^\s*Digest:\s*(sha256:[0-9a-f]{64})\s*$", tagged)
        require(match is not None and match.group(1) == image["digest"],
                "Commit-identified candidate tag has drifted: " + image["name"])
        for predicate in ("https://slsa.dev/provenance/v1", "https://spdx.dev/Document/v2.3"):
            run_command([
                "gh", "attestation", "verify", "oci://" + reference,
                "--repo", REPOSITORY, "--signer-workflow", R3_WORKFLOW,
                "--source-digest", source_sha, "--source-ref", "refs/heads/main",
                "--predicate-type", predicate,
            ])


def verify_signed_release_ready(root: Path, source_sha: str, r4_id: int,
                                *, run: dict | None = None) -> None:
    """Require the exact GitHub-attested R4 file and dispatch invocation.

    A genuine attestation from a *different* R4 run on the same main source
    must not authenticate this run's release-ready artifact.
    """
    require(valid_sha(source_sha) and type(r4_id) is int and r4_id > 0,
            "Invalid signed R4 identity")
    if run is None:
        run = api("repos/" + REPOSITORY + "/actions/runs/" + str(r4_id))
    validate_authenticated_run(run, source_sha, r4_id, R4_WORKFLOW)
    verify_attested_review_file(safe_file(root, "release-ready.json"),
                                source_sha, R4_WORKFLOW, run)


def stage_assets(root: Path, target: Path) -> None:
    """Copy a verified bundle to uniquely named GitHub Release assets."""
    require(target.is_dir() and not any(target.iterdir()), "Asset directory is not empty")
    assets = {}
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        relative = str(item.relative_to(root))
        safe_file(root, relative)
        name = relative.replace("/", "--")
        require(name not in assets and name != "assets.sha256", "Duplicate asset filename")
        dest = target / name
        shutil.copyfile(item, dest)
        assets[name] = hash_file(dest)
    require("release-lock.json" in assets and "verification.json" in assets
            and "release-notes.md" in assets, "Required release assets missing")
    (target / "assets.sha256").write_text(
        "".join(check + "  " + name + "\n" for name, check in sorted(assets.items())),
        encoding="utf-8")



def verify_published_records(tag_ref: dict, annotated_tag: dict, release: dict,
                             source_sha: str, expected_assets: dict[str, str]) -> None:
    """Pure idempotent release verification; never creates/changes remote refs."""
    require(tag_ref.get("ref") == "refs/tags/" + TAG
            and tag_ref.get("object", {}).get("type") == "tag",
            "Expected an existing annotated release tag")
    require(annotated_tag.get("tag") == TAG
            and annotated_tag.get("object", {}).get("type") == "commit"
            and annotated_tag["object"].get("sha") == source_sha,
            "Annotated tag does not point at approved main commit")
    require(release.get("tag_name") == TAG
            and release.get("draft") is False and release.get("prerelease") is False,
            "GitHub Release identity or publication state differs")
    require(source_sha in str(release.get("body", "")),
            "Release notes omit exact approved main SHA")
    assets = release.get("assets")
    require(isinstance(assets, list), "Release assets are unavailable")
    actual = {}
    for item in assets:
        require(isinstance(item, dict) and isinstance(item.get("name"), str),
                "Malformed release asset metadata")
        name = item["name"]
        require(name not in actual, "Duplicate release asset name")
        actual[name] = item.get("digest")
    require(set(actual) == set(expected_assets),
            "Release asset list differs from approved R4 evidence")
    for name, expected in expected_assets.items():
        require(actual[name] == "sha256:" + expected,
                "Published release asset digest drift: " + name)


def check_published(source_sha: str, root: Path, r4_id: int) -> None:
    """Verify an already-published release safely and repeatedly."""
    summary = validate_bundle(root, source_sha, r4_id)
    tag_ref = api("repos/" + REPOSITORY + "/git/ref/tags/" + TAG)
    require(tag_ref["object"].get("type") == "tag", "Release tag is not annotated")
    tag = api("repos/" + REPOSITORY + "/git/tags/" + tag_ref["object"]["sha"])
    release = api("repos/" + REPOSITORY + "/releases/tags/" + TAG)
    expected = {}
    for item in sorted(root.rglob("*")):
        if item.is_file():
            name = str(item.relative_to(root)).replace("/", "--")
            require(name not in expected, "Release asset filename collision")
            expected[name] = hash_file(item)
    checksums = "".join(value + "  " + name + "\n"
                        for name, value in sorted(expected.items()))
    expected["assets.sha256"] = hashlib.sha256(checksums.encode("utf-8")).hexdigest()
    verify_published_records(tag_ref, tag, release, source_sha, expected)
    require(summary["lock_sha256"] == hash_file(root / "release-lock.json"),
            "Release lock changed since validation")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("live", "bundle", "registry", "assets", "approval", "published", "dispositions", "extracted"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--r4-run-id", required=True, type=int)
    parser.add_argument("--evidence-dir", type=Path, default=Path("release-evidence"))
    parser.add_argument("--assets-dir", type=Path, default=Path("release-assets"))
    parser.add_argument("--approval-issue", type=int, default=0)
    parser.add_argument("--final", action="store_true", help="Require live owner state and publication approval")
    args = parser.parse_args()
    try:
        require(valid_sha(args.source_sha) and args.r4_run_id > 0,
                "Invalid source commit or R4 run ID")
        if args.command == "extracted":
            validate_extracted_artifact(args.evidence_dir)
        elif args.command == "published":
            verify_signed_release_ready(args.evidence_dir, args.source_sha, args.r4_run_id)
            check_published(args.source_sha, args.evidence_dir, args.r4_run_id)
        elif args.command in ("live", "approval"):
            summary = None
            if args.command == "approval":
                verify_signed_release_ready(args.evidence_dir, args.source_sha, args.r4_run_id)
                summary = validate_bundle(args.evidence_dir, args.source_sha, args.r4_run_id)
            live_check(args.source_sha, args.r4_run_id,
                       approval_issue=args.approval_issue,
                       lock_sha=summary["lock_sha256"] if summary else "",
                       require_approval=args.command == "approval")
        elif args.command in ("bundle", "registry", "assets", "dispositions"):
            verify_signed_release_ready(args.evidence_dir, args.source_sha, args.r4_run_id)
            summary = validate_bundle(args.evidence_dir, args.source_sha, args.r4_run_id)
            if args.command == "dispositions":
                revalidate_current_dispositions(
                    args.evidence_dir, summary, args.source_sha, latest=args.final)
                if args.final:
                    live_check(args.source_sha, args.r4_run_id,
                               approval_issue=args.approval_issue,
                               lock_sha=summary["lock_sha256"], require_approval=True)
            if args.command == "registry":
                verify_registry({"images": summary["images"]}, args.source_sha)
            elif args.command == "assets":
                stage_assets(args.evidence_dir, args.assets_dir)
        print("R5 " + args.command + " checks passed")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("R5 BLOCKED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
