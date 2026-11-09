"""Independent, fail-closed synthetic-capable R4/R5 disposition verifier.

This verifies local evidence and independent Ed25519 signatures. Callers MUST
independently authenticate R3/scan runs, approved lock and workflow OIDC
attestations; a JSON context alone is not GitHub provenance.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPOSITORY = "ItsFoxxin/Fox_Den_Media"
REVIEW_WORKFLOW = ".github/workflows/security-disposition-review.yml"
PRODUCER_WORKFLOW = ".github/workflows/trivy-digest-security.yml"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
CVE = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}\Z")
COMPONENT = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
PROOF = re.compile(r"proofs/[a-z0-9_-]+\.json\Z")
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}
CONTEXT_FIELDS = {"schema_version", "repository", "source_sha", "producer_actor",
                  "release_lock_sha256", "r3_run_id", "scan_run_id",
                  "scanner_metadata_sha256", "images"}
IMAGE_FIELDS = {"image_repository", "manifest_digest", "platform_digest",
                "trivy_report_sha256", "spdx_sbom_sha256"}
DOCUMENT_FIELDS = {"schema_version", "repository", "source_sha", "producer_actor",
                   "release_lock_sha256", "r3_run_id", "scan_run_id",
                   "created_at", "reviewed_at", "expires_at", "records"}
SUBJECT_FIELDS = {"component", "result_index", "vulnerability_index",
                  "cve_id", "target", "ecosystem", "package_name",
                  "installed_version", "finding_sha256", "image_repository",
                  "manifest_digest", "platform_digest",
                  "trivy_report_sha256", "spdx_sbom_sha256"}
RECORD_FIELDS = {"status", "subject", "proof_path", "proof_sha256", "reviewer_id"}
PROOF_FIELDS = {"schema_version", "kind", "source_sha", "release_lock_sha256",
                "r3_run_id", "scan_run_id", "image_repository", "manifest_digest",
                "platform_digest", "finding_sha256", "reference_url",
                "reference_sha256", "verification_method", "binary_sha256",
                "installed_version", "technical_basis"}


class DispositionError(ValueError):
    """A missing, ambiguous or unauthenticated fact blocks acceptance."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise DispositionError(reason)


def keys(obj: object, exact: set[str], label: str) -> dict:
    require(type(obj) is dict and set(obj) == exact, "Invalid " + label + " keys")
    return obj


def nonempty(value: object, label: str) -> str:
    require(type(value) is str and bool(value.strip()) and
            "*" not in value and "?" not in value, "Invalid " + label)
    return value


def digest(value: object, label: str) -> str:
    require(type(value) is str and bool(DIGEST.fullmatch(value)), "Invalid " + label)
    return value


def integer(value: object, label: str, minimum: int = 1) -> int:
    require(type(value) is int and value >= minimum, "Invalid " + label)
    return value


def load_json(path: Path) -> dict:
    raw = path.read_bytes()
    require(len(raw) <= 32 * 1024 * 1024, "Oversized JSON evidence")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def reject(_):
        raise DispositionError("Unsupported floating-point or nonfinite JSON")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                         parse_float=reject, parse_constant=reject)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DispositionError("Invalid UTF-8 JSON") from exc
    require(type(obj) is dict, "JSON root must be object")
    return obj


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def canonical_digest(obj: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


def raw_digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "Missing or symlinked evidence")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(value: object) -> datetime:
    require(type(value) is str and bool(re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value)), "Invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise DispositionError("Invalid UTC calendar timestamp") from exc


def verify_sig(public_pem: str, signature: str, domain: bytes,
               subject_hash: str) -> bytes:
    digest(subject_hash, "signature subject")
    try:
        key = serialization.load_pem_public_key(public_pem.encode("ascii"))
        require(isinstance(key, Ed25519PublicKey), "Non-Ed25519 trust key")
        value = base64.b64decode(signature, validate=True)
        require(len(value) == 64, "Wrong Ed25519 signature size")
        key.verify(value, domain + bytes.fromhex(subject_hash[7:]))
        return key.public_bytes(encoding=serialization.Encoding.Raw,
                                format=serialization.PublicFormat.Raw)
    except (ValueError, UnicodeError, binascii.Error, InvalidSignature,
            TypeError) as exc:
        raise DispositionError("Invalid or unauthorized Ed25519 signature") from exc


def validate_trust(trust: dict) -> tuple[dict, dict]:
    keys(trust, {"schema_version", "repository", "review_workflow",
                 "producer_workflow", "reviewers", "owner"}, "trust policy")
    require(trust["schema_version"] == 1 and trust["repository"] == REPOSITORY and
            trust["review_workflow"] == REVIEW_WORKFLOW and
            trust["producer_workflow"] == PRODUCER_WORKFLOW,
            "Unauthorized repository or signer workflow")
    reviewers = trust["reviewers"]
    require(type(reviewers) is dict, "Missing independent reviewer trust")
    seen_keys = set()
    for identity, info in reviewers.items():
        require(type(identity) is str and
                bool(re.fullmatch(r"github:[A-Za-z0-9-]{1,39}", identity)),
                "Unrecognized reviewer identity")
        keys(info, {"key_id", "public_key_pem"}, "reviewer trust")
        nonempty(info["key_id"], "reviewer key id")
        nonempty(info["public_key_pem"], "reviewer public key")
        require(info["key_id"] not in seen_keys, "Duplicate trusted key ID")
        seen_keys.add(info["key_id"])
    owner = keys(trust["owner"], {"identity", "key_id", "public_key_pem"}, "owner trust")
    nonempty(owner["identity"], "owner identity")
    nonempty(owner["key_id"], "owner key ID")
    nonempty(owner["public_key_pem"], "owner public key")
    require(owner["identity"] not in reviewers and owner["key_id"] not in seen_keys,
            "Reviewer and owner cannot share identity/key ID")
    return reviewers, owner


def validate_signatures(document: dict, signatures: dict, trust: dict,
                        needs_owner: bool) -> None:
    reviewers, owner = validate_trust(trust)
    keys(signatures, {"schema_version", "document_sha256", "signatures"}, "signatures")
    require(signatures["schema_version"] == 1 and
            signatures["document_sha256"] == canonical_digest(document),
            "Modified disposition document or incorrect signature subject")
    entries = signatures["signatures"]
    require(type(entries) is list, "Invalid signatures list")
    valid_reviewers = set()
    owner_valid = False
    owner_key_bytes = serialization.load_pem_public_key(
        owner["public_key_pem"].encode("ascii")).public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    seen_entries = set()
    domain = b"foxden.dispositions.v1\n"
    for entry in entries:
        keys(entry, {"role", "identity", "key_id", "signature_base64"}, "signature entry")
        role = entry["role"]
        identity = entry["identity"]
        require(type(role) is str and role in {"reviewer", "owner"} and
                type(identity) is str and (role, identity) not in seen_entries,
                "Unrecognized or duplicated signing principal")
        seen_entries.add((role, identity))
        if role == "reviewer":
            require(identity in reviewers, "Unauthorized reviewer")
            info = reviewers[identity]
            require(entry["key_id"] == info["key_id"], "Reviewer key mismatch")
            key_bytes = serialization.load_pem_public_key(
                info["public_key_pem"].encode("ascii")).public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw)
            require(key_bytes != owner_key_bytes, "Reviewer shares owner key")
            verify_sig(info["public_key_pem"], entry["signature_base64"],
                       domain, signatures["document_sha256"])
            valid_reviewers.add(identity)
        else:
            require(identity == owner["identity"] and
                    entry["key_id"] == owner["key_id"], "Unauthorized owner")
            verify_sig(owner["public_key_pem"], entry["signature_base64"],
                       domain, signatures["document_sha256"])
            owner_valid = True
    requested = {rec["reviewer_id"] for rec in document["records"]}
    require(requested == valid_reviewers, "Missing or unassigned independent reviewer")
    require(not needs_owner or owner_valid,
            "CRITICAL NOT AFFECTED requires separately signed owner concurrence")


def validate_lifecycle(lifecycle: dict, signature_text: str, trust: dict,
                       document_hash: str, now: datetime) -> str:
    keys(lifecycle, {"schema_version", "issued_at", "expires_at",
                     "revoked_document_sha256", "superseded_document_sha256"},
         "lifecycle")
    require(lifecycle["schema_version"] == 1, "Unknown lifecycle version")
    issued = timestamp(lifecycle["issued_at"])
    expires = timestamp(lifecycle["expires_at"])
    require(issued <= now < expires and timedelta(0) < expires - issued <= timedelta(hours=24),
            "Missing, stale or future lifecycle")
    for field in ("revoked_document_sha256", "superseded_document_sha256"):
        records = lifecycle[field]
        require(type(records) is list and len(records) == len(set(map(str, records))),
                "Duplicate/ambiguous lifecycle hashes")
        for value in records:
            digest(value, "lifecycle disposition digest")
        require(document_hash not in records, "Revoked or superseded disposition")
    owner = trust["owner"]
    verify_sig(owner["public_key_pem"], signature_text.strip(),
               b"foxden.lifecycle.v1\n", canonical_digest(lifecycle))
    return canonical_digest(lifecycle)


def finding_subject(component: str, index: int, ordinal: int, result: dict,
                    vuln: dict, image: dict) -> dict:
    return {
        "component": component, "result_index": index, "vulnerability_index": ordinal,
        "cve_id": vuln["VulnerabilityID"], "target": result["Target"],
        "ecosystem": result["Type"], "package_name": vuln["PkgName"],
        "installed_version": vuln["InstalledVersion"],
        "finding_sha256": canonical_digest(vuln),
        "image_repository": image["image_repository"],
        "manifest_digest": image["manifest_digest"],
        "platform_digest": image["platform_digest"],
        "trivy_report_sha256": image["trivy_report_sha256"],
        "spdx_sbom_sha256": image["spdx_sbom_sha256"],
    }


def collect_findings(context: dict, evidence_dir: Path) -> dict:
    findings = {}
    identities = set()
    for component, image in context["images"].items():
        require(bool(COMPONENT.fullmatch(component)), "Invalid component path")
        keys(image, IMAGE_FIELDS, "image")
        nonempty(image["image_repository"], "image repository")
        require("@" not in image["image_repository"] and
                "/" in image["image_repository"], "Unpinned or malformed image repository")
        for field in IMAGE_FIELDS - {"image_repository"}:
            digest(image[field], "image " + field)
        report_path = evidence_dir / "reports" / (component + ".vuln.json")
        spdx_path = evidence_dir / "reports" / (component + ".sbom.spdx.json")
        require(raw_digest(report_path) == image["trivy_report_sha256"],
                "Modified original vulnerability report")
        require(raw_digest(spdx_path) == image["spdx_sbom_sha256"],
                "Modified original SPDX SBOM")
        sbom = load_json(spdx_path)
        require(sbom.get("spdxVersion") == "SPDX-2.3" and
                sbom.get("SPDXID") == "SPDXRef-DOCUMENT" and
                type(sbom.get("packages")) is list and len(sbom["packages"]) > 0,
                "Invalid SPDX evidence")
        report = load_json(report_path)
        require(report.get("ArtifactName") ==
                image["image_repository"] + "@" + image["manifest_digest"] and
                report.get("ArtifactType") == "container_image" and
                type(report.get("Results")) is list and len(report["Results"]) > 0,
                "Wrong report subject or absent Trivy results")
        for i, result in enumerate(report["Results"]):
            require(type(result) is dict and
                    type(result.get("Target")) is str and bool(result["Target"]) and
                    type(result.get("Type")) is str and bool(result["Type"]),
                    "Missing Trivy target/ecosystem")
            vulns = result.get("Vulnerabilities")
            require(vulns is None or type(vulns) is list,
                    "Invalid original vulnerability list")
            for j, vulnerability in enumerate(vulns or []):
                require(type(vulnerability) is dict and
                        type(vulnerability.get("VulnerabilityID")) is str and
                        bool(CVE.fullmatch(vulnerability["VulnerabilityID"])) and
                        type(vulnerability.get("PkgName")) is str and
                        bool(vulnerability["PkgName"]) and
                        type(vulnerability.get("InstalledVersion")) is str and
                        bool(vulnerability["InstalledVersion"]) and
                        type(vulnerability.get("Severity")) is str and
                        vulnerability["Severity"] in SEVERITIES,
                        "Unidentified or unknown severity/package finding")
                full = canonical_digest(vulnerability)
                identity = (component, result["Target"], result["Type"],
                            vulnerability["VulnerabilityID"], vulnerability["PkgName"],
                            vulnerability["InstalledVersion"], full)
                require(identity not in identities, "Ambiguous duplicate finding identity")
                identities.add(identity)
                severity = vulnerability["Severity"]
                require(severity != "UNKNOWN", "UNKNOWN severity blocks acceptance")
                if severity in {"HIGH", "CRITICAL"}:
                    findings[(component, i, j)] = (
                        finding_subject(component, i, j, result, vulnerability, image),
                        severity)
    return findings


def validate_proof(record: dict, proof_dir: Path, context: dict) -> None:
    rel = record["proof_path"]
    require(type(rel) is str and bool(PROOF.fullmatch(rel)),
            "Unsafe or ambiguous proof path")
    proof_path = proof_dir / rel
    require(raw_digest(proof_path) == digest(record["proof_sha256"], "proof hash"),
            "Modified or missing proof bytes")
    proof = keys(load_json(proof_path), PROOF_FIELDS, "disposition proof")
    subject = record["subject"]
    for k in ("source_sha", "release_lock_sha256", "r3_run_id", "scan_run_id"):
        require(proof[k] == context[k], "Proof for wrong source/lock/run")
    for k in ("image_repository", "manifest_digest", "platform_digest",
              "finding_sha256", "installed_version"):
        require(proof[k] == subject[k], "Proof not bound to exact finding/image")
    require(proof["schema_version"] == 1 and proof["kind"] == record["status"],
            "Proof type mismatch")
    for k in ("binary_sha256", "reference_sha256"):
        digest(proof[k], "proof " + k)
    url = nonempty(proof["reference_url"], "technical evidence URL")
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and bool(parsed.hostname) and
            not parsed.username and not parsed.password and not parsed.fragment,
            "Non-authoritative or malformed evidence URL")
    method = nonempty(proof["verification_method"], "technical proof method")
    require(len(method) >= 20 and not re.search(
        r"non.?reproduc|failed.?exploit|passing.?test|compensating.?control|no.?observed.?call",
        method, flags=re.I), "Inconclusive technical proof")
    basis = proof["technical_basis"]
    if record["status"] == "FIXED":
        require(basis == "authoritative-remediation-and-installed-image",
                "FIXED requires authoritative remediation and installed-image proof")
    else:
        require(basis in {"vulnerable-implementation-absent",
                          "non-bypassable-exclusion"},
                "NOT AFFECTED requires conclusive technical proof")


def verify(*, context: dict, dispositions: dict, signatures: dict, lifecycle: dict,
           lifecycle_signature: str, trust: dict, evidence_dir: Path,
           proofs_dir: Path, lock_path: Path, scanner: dict, scanner_path: Path,
           exceptions: dict, expected_source_sha: str, expected_r3_run_id: int,
           expected_scan_run_id: int, expected_producer_actor: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, "Validation clock must have timezone")
    now = now.astimezone(timezone.utc)
    keys(context, CONTEXT_FIELDS, "signed R4 evidence context")
    require(context["schema_version"] == 1 and
            context["repository"] == REPOSITORY and
            context["source_sha"] == expected_source_sha and
            bool(SHA.fullmatch(expected_source_sha)) and
            context["r3_run_id"] == expected_r3_run_id and
            context["scan_run_id"] == expected_scan_run_id and
            context["producer_actor"] == expected_producer_actor and
            type(context["producer_actor"]) is str and
            bool(re.fullmatch(r"github:[A-Za-z0-9-]{1,39}", context["producer_actor"])),
            "Wrong source/R3/scan/producer identity")
    integer(context["r3_run_id"], "R3 run")
    integer(context["scan_run_id"], "scan run")
    digest(context["release_lock_sha256"], "lock digest")
    digest(context["scanner_metadata_sha256"], "scanner digest")
    require(context["release_lock_sha256"] == raw_digest(lock_path) and
            context["scanner_metadata_sha256"] == raw_digest(scanner_path),
            "Modified release lock or scanner metadata")
    require(type(context["images"]) is dict and len(context["images"]) > 0,
            "No authenticated image subjects")
    keys(exceptions, {"schema_version", "exceptions"}, "security exceptions")
    require(exceptions["schema_version"] == 1 and exceptions["exceptions"] == [],
            "Nonempty or unsupported security exceptions")
    require(scanner.get("Version") == "0.76.2" and
            type(scanner.get("VulnerabilityDB")) is dict and
            type(scanner["VulnerabilityDB"].get("Version")) is int and
            scanner["VulnerabilityDB"]["Version"] > 0,
            "Wrong scanner version or database schema")
    db_at = timestamp(scanner["VulnerabilityDB"].get("UpdatedAt"))
    require(timedelta(0) <= now - db_at <= timedelta(days=14),
            "Stale or future scanner database")
    findings = collect_findings(context, evidence_dir)
    keys(dispositions, DOCUMENT_FIELDS, "disposition document")
    require(dispositions["schema_version"] == 1 and
            dispositions["repository"] == context["repository"],
            "Unsupported disposition schema or repository")
    for field in ("source_sha", "release_lock_sha256", "r3_run_id", "scan_run_id", "producer_actor"):
        require(dispositions[field] == context[field],
                "Disposition source/lock/R3/scan mismatch")
    created = timestamp(dispositions["created_at"])
    reviewed = timestamp(dispositions["reviewed_at"])
    expires = timestamp(dispositions["expires_at"])
    require(created <= reviewed <= now < expires and
            timedelta(0) < expires - reviewed <= timedelta(days=30),
            "Missing, expired, future or overlong security review")
    records = dispositions["records"]
    require(type(records) is list, "Invalid disposition records")
    required = set(findings)
    seen = set()
    paths = set()
    needs_owner = False
    for record in records:
        keys(record, RECORD_FIELDS, "review record")
        require(record["status"] in {"FIXED", "NOT_AFFECTED"},
                "Unsupported security disposition")
        subject = keys(record["subject"], SUBJECT_FIELDS, "finding subject")
        component = subject["component"]
        require(type(component) is str and component in context["images"],
                "Cross-image or nonexistent component")
        i = integer(subject["result_index"], "result index", 0)
        j = integer(subject["vulnerability_index"], "vulnerability index", 0)
        occurrence = (component, i, j)
        require(occurrence in required and occurrence not in seen,
                "Duplicate, missing or cross-image disposition occurrence")
        seen.add(occurrence)
        expected, severity = findings[occurrence]
        require(subject == expected, "Changed CVE/package/target/version/digest finding")
        require(record["proof_path"] not in paths, "Duplicate proof path")
        paths.add(record["proof_path"])
        nonempty(record["reviewer_id"], "reviewer identity")
        require(record["reviewer_id"] != context["producer_actor"],
                "Security producer cannot approve own disposition")
        validate_proof(record, proofs_dir, context)
        needs_owner |= severity == "CRITICAL" and record["status"] == "NOT_AFFECTED"
    require(seen == required, "Unresolved HIGH or CRITICAL finding")
    doc_hash = canonical_digest(dispositions)
    validate_signatures(dispositions, signatures, trust, needs_owner)
    lifecycle_hash = validate_lifecycle(lifecycle, lifecycle_signature, trust,
                                        doc_hash, now)
    return {
        "schema_version": 1, "decision": "pass",
        "disposition_document_sha256": doc_hash, "lifecycle_sha256": lifecycle_hash,
        "source_sha": context["source_sha"],
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": context["r3_run_id"], "scan_run_id": context["scan_run_id"],
        "reviewed_at": dispositions["reviewed_at"],
        "expires_at": dispositions["expires_at"],
        "cleared_finding_count": len(seen), "image_count": len(context["images"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("verify")
    for name in ("context", "evidence-dir", "dispositions", "proofs-dir",
                 "signatures", "lifecycle", "lifecycle-signature", "trust",
                 "lock", "scanner", "exceptions", "expected-source-sha",
                 "expected-r3-run-id", "expected-scan-run-id", "expected-producer-actor", "output"):
        p.add_argument("--" + name, required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.unlink(missing_ok=True)
    try:
        result = verify(
            context=load_json(Path(args.context)),
            dispositions=load_json(Path(args.dispositions)),
            signatures=load_json(Path(args.signatures)),
            lifecycle=load_json(Path(args.lifecycle)),
            lifecycle_signature=Path(args.lifecycle_signature).read_text(encoding="ascii"),
            trust=load_json(Path(args.trust)),
            evidence_dir=Path(args.evidence_dir), proofs_dir=Path(args.proofs_dir),
            lock_path=Path(args.lock),
            scanner=load_json(Path(args.scanner)), scanner_path=Path(args.scanner),
            exceptions=load_json(Path(args.exceptions)),
            expected_source_sha=args.expected_source_sha,
            expected_r3_run_id=int(args.expected_r3_run_id),
            expected_scan_run_id=int(args.expected_scan_run_id),
            expected_producer_actor=args.expected_producer_actor,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(canonical(result) + b"\n")
        return 0
    except (DispositionError, OSError, ValueError) as exc:
        print("security disposition verification failed: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
