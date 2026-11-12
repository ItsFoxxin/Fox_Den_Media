"""R4 -> R5 immutable release-ready evidence producer; offline, no package writes.

The R4 workflow MUST authenticate the PR #84 file attestations, acceptance
attestations, OCI signer identities and live GitHub API responses *before*
calling this program. This program independently validates their structural,
source, digest, policy, provenance, rollback and hash bindings. It never
manufactures source GO, no-rebuild, security-review or rollback evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

from scripts.release_lock import FIRST_PARTY, validate_lock
from scripts.verify_image_security import (
    COMPONENTS, validate_contract, validate_scanner_policy,
)

REPO = "ItsFoxxin/Fox_Den_Media"
SCHEMA = "foxden.r4.release-ready.v1"
R4_WORKFLOW = ".github/workflows/ghcr-verify.yml"
ACCEPTANCE_WORKFLOW = ".github/workflows/release-acceptance.yml"
HASH = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
NOTE_HEADINGS = (
    "Release summary", "Major features", "Bug fixes", "Security changes",
    "Compatibility", "Installation and upgrade", "Images and immutable digests",
    "SBOM", "Build provenance", "Checksums", "Known limitations",
    "Rollback", "Documentation",
)


class ReleaseEvidenceError(ValueError):
    """A genuine independent release acceptance prerequisite is missing."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ReleaseEvidenceError(reason)


def read_json(path: Path) -> dict | list:
    def no_dupes(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate evidence JSON field: " + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_dupes)


def sha_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "Missing or symlinked evidence: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_evidence(source: Path, destination: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "Missing immutable evidence: " + str(source))
    require(not destination.exists(), "Duplicate output evidence: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def require_successful_acceptance(run: dict, source: str, run_id: int) -> None:
    require(type(run) is dict and type(run_id) is int and run_id > 0,
            "Missing independent acceptance run")
    require(run.get("id") == run_id and
            run.get("repository", {}).get("full_name") == REPO and
            str(run.get("path", "")).split("@")[0] == ACCEPTANCE_WORKFLOW and
            run.get("event") == "workflow_dispatch" and
            run.get("head_sha") == source and run.get("head_branch") == "main" and
            run.get("status") == "completed" and run.get("conclusion") == "success",
            "Untrusted, failed or wrong-source independent acceptance producer")


def owner_decision(issue: dict, comments: list, issue_number: int,
                   command: str) -> dict:
    require(type(issue_number) is int and issue_number > 0 and
            type(issue) is dict and issue.get("number") == issue_number and
            issue.get("pull_request") is None and issue.get("state") == "open",
            "Invalid source approval issue")
    require(type(comments) is list, "Missing source approval comments")
    matches = []
    for comment in comments:
        require(type(comment) is dict, "Malformed issue comment response")
        user = comment.get("user")
        if (type(user) is dict and user.get("login") == "ItsFoxxin" and
                comment.get("author_association") == "OWNER" and
                comment.get("body", "").strip() == command):
            ident = comment.get("id")
            created = comment.get("created_at")
            require(type(ident) is int and ident > 0 and
                    type(created) is str and bool(re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created)),
                    "Malformed owner approval identity or timestamp")
            matches.append((created, ident))
    require(bool(matches), "Independent owner approval missing: " + command.split(" ")[0])
    timestamp, ident = max(matches)
    return {"decision": "approved", "approved_by": "ItsFoxxin",
            "record_url": f"https://github.com/{REPO}/issues/{issue_number}#issuecomment-{ident}",
            "comment_id": ident, "approved_at": timestamp}


def validate_rollback(report: dict, lock: dict, source: str, acceptance_run: int) -> None:
    require(type(report) is dict and set(report) == {
        "schema_version", "source_sha", "release_version", "previous_version",
        "previous_lock_sha256", "backup_manifest_sha256", "restore_report_sha256",
        "acceptance_run_id", "decision", "evidence_url",
    }, "Rollback report requires actual reviewed backup and restore evidence")
    require(report["schema_version"] == 1 and report["source_sha"] == source and
            report["release_version"] == "1.0.0" and
            report["previous_version"] == lock["rollback"]["version"] and
            report["previous_lock_sha256"] == lock["rollback"]["lock_sha256"] and
            report["acceptance_run_id"] == acceptance_run and
            report["decision"] == "pass",
            "Rollback receipt is not approved for this source/previous lock")
    for field in ("backup_manifest_sha256", "restore_report_sha256", "previous_lock_sha256"):
        require(type(report[field]) is str and bool(HASH.fullmatch(report[field])),
                "Rollback evidence missing actual archive/restore digest: " + field)
    require(type(report["evidence_url"]) is str and report["evidence_url"].startswith(
        f"https://github.com/{REPO}/actions/runs/{acceptance_run}"),
        "Rollback has no linked independently verified acceptance run")


def verify_native_alerts(alerts: dict) -> dict:
    require(type(alerts) is dict and set(alerts) == {
        "code-scanning", "dependabot", "secret-scanning",
    }, "Incomplete native GitHub security queries")
    counts = {}
    for family, records in alerts.items():
        require(type(records) is list, "Native GitHub alert API unavailable: " + family)
        require(all(type(item) is dict and item.get("state") == "open" for item in records),
                "Unrecognized native GitHub alerts: " + family)
        counts[family] = len(records)
    require(all(value == 0 for value in counts.values()),
            "Unresolved native GitHub CodeQL/Dependabot/secret alerts")
    return counts


def validate_notes(notes: str, source: str, lock_hash: str, lock: dict) -> None:
    headings = set(re.findall(r"(?m)^## ([^\n]+)$", notes))
    require(set(NOTE_HEADINGS) <= headings, "Unfinished independently reviewed release notes")
    require(source in notes and lock_hash in notes, "Notes do not bind source and lock")
    for component in FIRST_PARTY:
        require(lock["images"][component]["ref"] in notes,
                "Notes missing first-party immutable digest: " + component)
    require(not re.search(r"\{\{|TODO|TBD|PLACEHOLDER", notes, re.I),
            "Release notes still contain placeholders")
    require(not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                          r"(?i:(?:password|api[_-]?key|secret|access[_-]?token)\s*[=:]\s*\S{8,})",
                          notes), "Release notes may contain sensitive values")
    require(not re.search(
        r"\b(?:10|192\.168|172\.(?:1[6-9]|2[0-9]|3[01]))"
        r"\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", notes),
        "Release notes may contain private addresses")


def verify_attested_provenance(document: list, name: str, digest: str) -> None:
    """Do not turn an arbitrary JSON 'verified' flag into signer evidence."""
    require(type(document) is list and bool(document),
            "Missing verified GH attestation output: " + name)
    for item in document:
        if type(item) is not dict:
            continue
        verified = item.get("verificationResult")
        statement = verified.get("statement") if type(verified) is dict else None
        subjects = statement.get("subject") if type(statement) is dict else None
        if type(subjects) is not list:
            continue
        for subject in subjects:
            if (type(subject) is dict and subject.get("name") == name and
                    type(subject.get("digest")) is dict and
                    subject["digest"].get("sha256") == digest.split(":")[1]):
                return
    raise ReleaseEvidenceError("Attestation subject does not match locked image: " + name)


def verify_integration(report: dict, lock: dict, source: str, r4_id: int) -> None:
    require(type(report) is dict and set(report) == {
        "schema_version", "source_sha", "r4_run_id", "lock_sha256",
        "decision", "mode", "images",
    }, "Unverified no-rebuild report")
    images = {key: val["ref"] for key, val in lock["images"].items()}
    require(report["schema_version"] == 1 and report["source_sha"] == source and
            report["r4_run_id"] == r4_id and report["decision"] == "pass" and
            report["mode"] == "pulled-digest-no-build" and
            report["images"] == images,
            "No-rebuild integration not proved on these exact digests")



def require_unmodified_scan_collection(*, lock: dict, security_dir: Path,
                                       scan_dir: Path, policy_path: Path) -> None:
    """A raw reports, SPDX, scanner, lock and source policy survive C unchanged."""
    require(type(lock) is dict and type(lock.get("images")) is dict and
            bool(lock["images"]), "Missing complete R2 locked images")
    # A is the original, signed complete scan collection. C must not swap
    # its lock, scanner, ledger or any raw per-image report/SBOM before review.
    for name in ("context.json", "release-lock.json", "scanner.json",
                 "rendered-release-compose.json", "vulnerability-exceptions.json"):
        require(sha_file(scan_dir / name) == sha_file(security_dir / name),
                "Final C has altered signed scan A evidence: " + name)
    require(sha_file(scan_dir / "vulnerability-exceptions.json") ==
            sha_file(policy_path),
            "Scan A exception ledger differs from checked-out source")
    for component in lock["images"]:
        require(type(component) is str and
                bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", component)),
                "Unsafe or missing locked scan component")
        for suffix in (".vuln.json", ".sbom.spdx.json"):
            rel = "reports/" + component + suffix
            require(sha_file(scan_dir / rel) == sha_file(security_dir / rel),
                    "Final C changed original scan A evidence: " + rel)


REVIEW_WORKFLOW = ".github/workflows/security-disposition-review.yml"
REVIEW_ARTIFACT = "security-disposition-review-v1"
PROOF_BASENAME = re.compile(r"proofs/([a-z0-9_-]+)\.json\Z")


def revalidate_independent_dispositions(*, security: dict, lock: dict,
                                        scanner: dict, ledger: dict,
                                        source: str, r3_id: int, scan_id: int,
                                        review_id: int, scan_actor: str,
                                        security_dir: Path, scan_dir: Path,
                                        policy_path: Path,
                                        review_dir: Path, trust_path: Path,
                                        lifecycle_path: Path,
                                        lifecycle_signature_path: Path) -> tuple[dict, dict]:
    """Fresh independent Ed25519/lifecycle and raw A/C evidence verification.

    The independently merged PR #93/#95 verifier is mandatory at runtime;
    a self-declared JSON "pass" never substitutes for its cryptographic checks.
    """
    try:
        from scripts.verify_security_dispositions import (
            verify, load_json, require_r4_contract_v2,
        )
    except ImportError as exc:
        raise ReleaseEvidenceError(
            "Mandatory integrated independent disposition verifier unavailable; R4 blocked"
        ) from exc
    binding = security["disposition_review"]
    require(binding["review_run_id"] == review_id,
            "Finalized C contract refers to a different authenticated B review")
    require(type(scan_actor) is str and
            bool(re.fullmatch(r"github:[A-Za-z0-9-]{1,39}", scan_actor)),
            "Missing independently authenticated scan A actor")
    require_unmodified_scan_collection(lock=lock, security_dir=security_dir,
                                       scan_dir=scan_dir, policy_path=policy_path)
    signed_path = review_dir / "security/disposition-verification.json"
    require(sha_file(security_dir / "review/disposition-verification.json") ==
            sha_file(signed_path),
            "Final C changed the independently signed B review result")
    signed_bytes = signed_path.read_bytes()
    signed_result = load_json(signed_path)
    require_r4_contract_v2(security, signed_result, signed_bytes)
    dispositions = load_json(review_dir / "review/dispositions.json")
    signatures = load_json(review_dir / "review/signatures.json")
    # The lifecycle and reviewer trust MUST originate from the independently
    # owner-managed environment, never from artifact B or C.
    # Absence or symlink substitution is a hard input failure, not a fallback.
    for owner_path in (trust_path, lifecycle_path, lifecycle_signature_path):
        require(owner_path.is_file() and not owner_path.is_symlink(),
                "Missing or unsafe owner-managed disposition trust/lifecycle input")
    fresh_result = verify(
        context=load_json(scan_dir / "context.json"),
        dispositions=dispositions,
        signatures=signatures,
        lifecycle=load_json(lifecycle_path),
        lifecycle_signature=lifecycle_signature_path.read_text(encoding="ascii"),
        trust=load_json(trust_path), evidence_dir=scan_dir,
        proofs_dir=review_dir / "review",
        lock_path=scan_dir / "release-lock.json",
        scanner=scanner, scanner_path=scan_dir / "scanner.json",
        exceptions=ledger, expected_source_sha=source,
        expected_r3_run_id=r3_id, expected_scan_run_id=scan_id,
        expected_producer_actor=scan_actor,
    )
    require(type(signed_result) is dict and
            set(signed_result) == set(fresh_result) and
            all(signed_result[k] == value for k, value in fresh_result.items()
                if k != "lifecycle_sha256"),
            "Signed B review differs from independently reconstructed current disposition")
    # A *newer* genuine lifecycle ledger can supersede the one B signed;
    # revalidate it now rather than trusting B's old lifecycle SHA.
    return signed_result, dispositions


def stage_independent_dispositions(*, review_dir: Path, output: Path,
                                   dispositions: dict,
                                   signed_result: dict, binding: dict,
                                   review_id: int) -> dict:
    """Flat, deterministic signed v1 manifest paths; no unsigned sidecar.

    This stages *already authenticated* B evidence. Upstream verification and
    latest owner lifecycle MUST succeed before the caller invokes it.
    """
    require(type(dispositions) is dict, "Invalid disposition document")
    require(type(dispositions.get("records")) is list,
            "Missing disposition records")
    review_root = review_dir / "review"
    paths = set()
    for record in dispositions["records"]:
        require(type(record) is dict, "Malformed disposition record")
        match = PROOF_BASENAME.fullmatch(record.get("proof_path", ""))
        require(match is not None and match.group(1) not in paths,
                "Missing, duplicate or unsafe disposition proof filename")
        paths.add(match.group(1))
        proof = review_root / record["proof_path"]
        require("sha256:" + sha_file(proof) == record.get("proof_sha256"),
                "Altered signed disposition proof bytes")
    proof_root = review_root / "proofs"
    if proof_root.exists() or proof_root.is_symlink():
        require(proof_root.is_dir() and not proof_root.is_symlink() and
                {p.name for p in proof_root.iterdir()} ==
                {slug + ".json" for slug in paths} and
                all(p.is_file() and not p.is_symlink()
                    for p in proof_root.iterdir()),
                "Missing, unreferenced or unsafe disposition proof")
    else:
        # GitHub artifact archives omit empty directories. Only an authenticated
        # zero-record document can legitimately have no proof directory.
        require(not paths, "Missing disposition proofs directory")
    copied = (
        ("security/disposition-verification.json",
         "integration/disposition-verification.json"),
        ("review/dispositions.json", "integration/security-dispositions.json"),
        ("review/signatures.json",
         "integration/security-disposition-signatures.json"),
    )
    for src, dst in copied:
        copy_evidence(review_dir / src, output / dst)
    for slug in sorted(paths):
        copy_evidence(proof_root / (slug + ".json"),
                      output / ("integration/disposition-proof-" + slug + ".json"))
    verification_hash = "sha256:" + sha_file(
        output / "integration/disposition-verification.json")
    require(verification_hash == binding["verification_sha256"] and
            signed_result.get("disposition_document_sha256") ==
                binding["dispositions_sha256"],
            "Altered signed disposition result/document binding")
    require(binding["review_run_id"] == review_id,
            "Wrong signed B review run for released disposition")
    return {
        "schema_version": 1,
        "artifact_name": REVIEW_ARTIFACT,
        "verification_file": "integration/disposition-verification.json",
        "verification_sha256": verification_hash,
        "dispositions_sha256": binding["dispositions_sha256"],
        "review_workflow": REVIEW_WORKFLOW,
        "review_run_id": review_id,
        "verified_at": binding["verified_at"],
    }


def validate_disposition_file_map(*, files: dict, output: Path,
                                  dispositions: dict, binding: dict) -> None:
    """Fail closed if any flat review proof is omitted from the signed v1 map."""
    require(type(files) is dict and type(dispositions) is dict and
            type(dispositions.get("records")) is list,
            "Malformed signed release-ready disposition inventory")
    fixed = {
        "integration/disposition-verification.json",
        "integration/security-dispositions.json",
        "integration/security-disposition-signatures.json",
    }
    expected = set(fixed)
    for item in dispositions["records"]:
        require(type(item) is dict, "Malformed review proof record")
        match = PROOF_BASENAME.fullmatch(item.get("proof_path", ""))
        require(match is not None, "Invalid disposition proof path")
        expected.add("integration/disposition-proof-" + match.group(1) + ".json")
    actual = {key for key in files if key in fixed or
              key.startswith("integration/disposition-proof-")}
    require(actual == expected, "Signed file map omitted or added disposition proof")
    for key in expected:
        require(type(files[key]) is str and bool(HASH.fullmatch(files[key])) and
                files[key] == sha_file(output / key),
                "Altered or unsealed disposition evidence in signed file map")
    require("sha256:" + files["integration/disposition-verification.json"] ==
            binding["verification_sha256"],
            "R4 signed file map has wrong independent verification hash")


def assemble_bundle(*, source: str, r3_id: int, r4_id: int,
                    scan_id: int, review_id: int, scan_actor: str,
                    acceptance_id: int, approval_issue: int,
                    security_dir: Path, scan_dir: Path, review_dir: Path,
                    trust_path: Path, lifecycle_path: Path,
                    lifecycle_signature_path: Path,
                    candidates_dir: Path, provenance_dir: Path,
                    integration_path: Path, acceptance_dir: Path,
                    issue_path: Path, comments_path: Path, alerts_dir: Path,
                    compose_path: Path, policy_path: Path,
                    output: Path) -> dict:
    """Create files only after validating genuine independent input subjects."""
    require(type(source) is str and bool(SHA.fullmatch(source)) and
            all(type(i) is int and i > 0 for i in
                (r3_id, scan_id, review_id, r4_id, acceptance_id)),
            "Bad R3/A/B/C/R4/source or independent acceptance run identity")
    require(not output.exists() or not any(output.iterdir()),
            "Refusing to overwrite a release-ready bundle")
    security = read_json(security_dir / "security-contract.json")
    lock = read_json(security_dir / "release-lock.json")
    scanner = read_json(security_dir / "scanner.json")
    rendered = read_json(security_dir / "rendered-release-compose.json")
    ledger = read_json(policy_path)
    candidates = {name: read_json(candidates_dir / (name + ".json"))
                  for name in COMPONENTS}
    validate_lock(lock, compose=compose_path.read_bytes(), rendered=rendered,
                  expected_source=source)
    require(lock["version"] == "1.0.0" and lock["publisher"]["run_id"] == r3_id,
            "R2 release version / R3 identity mismatch")
    validate_contract(security, candidates, source, r3_id,
                      lock=lock, evidence_dir=security_dir / "reports")
    validate_scanner_policy(security, scanner, ledger)
    signed_review_result, dispositions = revalidate_independent_dispositions(
        security=security, lock=lock, scanner=scanner, ledger=ledger,
        source=source, r3_id=r3_id, scan_id=scan_id, review_id=review_id,
        scan_actor=scan_actor, security_dir=security_dir, scan_dir=scan_dir,
        policy_path=policy_path, review_dir=review_dir, trust_path=trust_path,
        lifecycle_path=lifecycle_path,
        lifecycle_signature_path=lifecycle_signature_path)
    require(security.get("policy_version") == "v1:" + hashlib.sha256(
        json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "Wrong independently reviewed security policy")
    acceptance_run = read_json(acceptance_dir / "run.json")
    require_successful_acceptance(acceptance_run, source, acceptance_id)
    rollback_path = acceptance_dir / "rollback-report.json"
    rollback = read_json(rollback_path)
    validate_rollback(rollback, lock, source, acceptance_id)
    issue = read_json(issue_path)
    comments = read_json(comments_path)
    promotion = owner_decision(issue, comments, approval_issue,
                               "FOX_DEN_SOURCE_PROMOTION_CONFIRMED " + source)
    promotion["source_sha"] = source
    rollback_hash = sha_file(rollback_path)
    owner_decision(issue, comments, approval_issue,
                   "FOX_DEN_ROLLBACK_VERIFIED " + source + " " +
                   lock["rollback"]["lock_sha256"] + " " + rollback_hash)
    native_alerts = {kind: read_json(alerts_dir / (kind + ".json"))
                     for kind in ("code-scanning", "dependabot", "secret-scanning")}
    counts = verify_native_alerts(native_alerts)
    integration = read_json(integration_path)
    verify_integration(integration, lock, source, r4_id)
    lock_hash = sha_file(security_dir / "release-lock.json")
    require(integration["lock_sha256"] == lock_hash,
            "No-rebuild report has wrong release lock hash")
    notes_path = acceptance_dir / "release-notes.md"
    notes = notes_path.read_text(encoding="utf-8")
    validate_notes(notes, source, lock_hash, lock)
    output.mkdir(parents=True, exist_ok=True)
    for filename in ("release-lock.json", "security-contract.json",
                     "scanner.json", "rendered-release-compose.json"):
        copy_evidence(security_dir / filename, output / filename)
    copy_evidence(notes_path, output / "release-notes.md")
    normalized = {}
    for component, data in lock["images"].items():
        record = security["images"][component] if component in COMPONENTS else security["upstream"][component]
        for suffix in (".vuln.json", ".sbom.spdx.json"):
            copy_evidence(security_dir / "reports" / (component + suffix),
                          output / "reports" / (component + suffix))
        provenance_path = provenance_dir / (component + ".json")
        provenance = read_json(provenance_path)
        image_name, image_digest = data["ref"].rsplit("@", 1)
        verify_attested_provenance(provenance, image_name, image_digest)
        copy_evidence(provenance_path, output / "provenance" / (component + ".json"))
        evidence = {
            "ref": data["ref"],
            "platform_digest": data["platform_digest"],
            "security_decision": record["decision"],
            "provenance": "provenance/" + component + ".json",
            "sbom": "reports/" + component + ".sbom.spdx.json",
            "vulnerability_report": "reports/" + component + ".vuln.json",
        }
        if component in COMPONENTS:
            require(data["source_sha"] == source and
                    candidates[component]["digest"] == image_digest,
                    "First-party source or signed OCI digest mismatch")
            evidence["candidate_tag"] = "sha-" + source
        else:
            require(data["source_sha"] is None and
                    record["provenance_status"] == "verified",
                    "Untrusted upstream signer")
            evidence["approved_upstream"] = True
        normalized[component] = evidence
    copy_evidence(integration_path, output / "integration/no-rebuild.json")
    copy_evidence(rollback_path, output / "integration/rollback-report.json")
    disposition_binding = stage_independent_dispositions(
        review_dir=review_dir, output=output, dispositions=dispositions,
        signed_result=signed_review_result,
        binding=security["disposition_review"], review_id=review_id)
    review = {
        "schema_version": 1, "source_sha": source,
        "source_promotion": promotion, "native_alert_counts": counts,
        "acceptance_run_id": acceptance_id,
    }
    review_path = output / "integration/security-review.json"
    review_path.write_text(json.dumps(review, sort_keys=True, indent=2) + "\n")
    file_hashes = {str(p.relative_to(output)): sha_file(p)
                   for p in output.rglob("*") if p.is_file()}
    validate_disposition_file_map(
        files=file_hashes, output=output, dispositions=dispositions,
        binding=disposition_binding)
    verification = {
        "schema_version": 1, "version": "1.0.0", "source_sha": source,
        "r3_run_id": r3_id, "r4_run_id": r4_id,
        "decision": "pass", "security_policy_result": "pass",
        "security_policy_version": security["policy_version"],
        "high_critical_unaccepted": 0, "exceptions": [],
        "no_rebuild_integration": "passed",
        "rollback_verified": True,
        "source_promotion_approval": {
            key: promotion[key] for key in
            ("decision", "approved_by", "source_sha", "record_url")
        },
        "github_security_review": "pass", "unapproved_security_findings": 0,
        "image_evidence": normalized, "files": file_hashes,
        "disposition_review": disposition_binding,
    }
    ver_path = output / "verification.json"
    ver_path.write_text(json.dumps(verification, sort_keys=True, indent=2) + "\n")
    root_hashes = dict(file_hashes)
    root_hashes["verification.json"] = sha_file(ver_path)
    manifest = {
        "schema_version": SCHEMA, "version": "1.0.0",
        "repository": REPO, "workflow": R4_WORKFLOW,
        "source_sha": source, "r3_run_id": r3_id, "r4_run_id": r4_id,
        "files": root_hashes,
    }
    (output / "release-ready.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--r3-run-id", type=int, required=True)
    parser.add_argument("--r4-run-id", type=int, required=True)
    parser.add_argument("--scan-run-id", type=int, required=True)
    parser.add_argument("--review-run-id", type=int, required=True)
    parser.add_argument("--scan-actor", required=True)
    parser.add_argument("--acceptance-run-id", type=int, required=True)
    parser.add_argument("--approval-issue", type=int, required=True)
    for field in ("security-dir", "scan-dir", "review-dir", "trust-path",
                  "lifecycle-path", "lifecycle-signature-path",
                  "candidates-dir", "provenance-dir",
                  "integration-path", "acceptance-dir", "issue-path",
                  "comments-path", "alerts-dir", "compose-path", "policy-path",
                  "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    try:
        assemble_bundle(
            source=args.source_sha, r3_id=args.r3_run_id,
            r4_id=args.r4_run_id, scan_id=args.scan_run_id,
            review_id=args.review_run_id, scan_actor=args.scan_actor,
            acceptance_id=args.acceptance_run_id,
            approval_issue=args.approval_issue,
            security_dir=args.security_dir, scan_dir=args.scan_dir,
            review_dir=args.review_dir, trust_path=args.trust_path,
            lifecycle_path=args.lifecycle_path,
            lifecycle_signature_path=args.lifecycle_signature_path,
            candidates_dir=args.candidates_dir,
            provenance_dir=args.provenance_dir, integration_path=args.integration_path,
            acceptance_dir=args.acceptance_dir, issue_path=args.issue_path,
            comments_path=args.comments_path, alerts_dir=args.alerts_dir,
            compose_path=args.compose_path, policy_path=args.policy_path,
            output=args.output)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f"R4 release-ready bundle REFUSED: {exc}\n")
    print("R4 immutable v1 release-ready bundle staged for R4 attestation (no publication)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
