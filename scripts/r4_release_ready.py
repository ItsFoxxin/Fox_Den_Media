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


def assemble_bundle(*, source: str, r3_id: int, r4_id: int,
                    acceptance_id: int, approval_issue: int,
                    security_dir: Path, candidates_dir: Path,
                    provenance_dir: Path, integration_path: Path,
                    acceptance_dir: Path, issue_path: Path,
                    comments_path: Path, alerts_dir: Path,
                    compose_path: Path, policy_path: Path,
                    output: Path) -> dict:
    """Create files only after validating genuine independent input subjects."""
    require(type(source) is str and bool(SHA.fullmatch(source)) and
            all(type(i) is int and i > 0 for i in (r3_id, r4_id, acceptance_id)),
            "Bad R3/R4/source or independent acceptance run identity")
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
    validate_scanner_policy(security, scanner, ledger, now=now)
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
    review = {
        "schema_version": 1, "source_sha": source,
        "source_promotion": promotion, "native_alert_counts": counts,
        "acceptance_run_id": acceptance_id,
    }
    review_path = output / "integration/security-review.json"
    review_path.write_text(json.dumps(review, sort_keys=True, indent=2) + "\n")
    file_hashes = {str(p.relative_to(output)): sha_file(p)
                   for p in output.rglob("*") if p.is_file()}
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
    parser.add_argument("--acceptance-run-id", type=int, required=True)
    parser.add_argument("--approval-issue", type=int, required=True)
    for field in ("security-dir", "candidates-dir", "provenance-dir",
                  "integration-path", "acceptance-dir", "issue-path",
                  "comments-path", "alerts-dir", "compose-path", "policy-path",
                  "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    try:
        assemble_bundle(
            source=args.source_sha, r3_id=args.r3_run_id,
            r4_id=args.r4_run_id, acceptance_id=args.acceptance_run_id,
            approval_issue=args.approval_issue,
            security_dir=args.security_dir, candidates_dir=args.candidates_dir,
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
