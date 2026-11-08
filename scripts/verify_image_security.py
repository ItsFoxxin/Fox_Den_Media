"""R4 consumer for digest-bound scan contracts from the independent security pipeline.

This validates claimed policy data only. A trusted R4 workflow MUST first
verify the security artifact's attestation/signing workflow and each image's
GitHub build attestation and registry digest before consuming these fields.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMPONENTS = {
    "portal": "ghcr.io/itsfoxxin/fox-den-media-portal",
    "music": "ghcr.io/itsfoxxin/fox-den-media-music",
    "media": "ghcr.io/itsfoxxin/fox-den-media-media",
}

class SecurityContractError(ValueError):
    pass

def require(ok: bool, message: str) -> None:
    if not ok:
        raise SecurityContractError(message)

def validate_contract(contract: dict, candidates: dict, source_sha: str,
                      publisher_run_id: int, lock: dict | None = None,
                      evidence_dir: Path | None = None) -> None:
    require(bool(SHA.fullmatch(source_sha)), "Bad approved source SHA")
    required = {"schema_version", "producer", "source_sha", "publisher_run_id",
                "platform", "scanner", "policy_version", "images", "upstream"}
    require(type(contract) is dict and set(contract) == required, "Bad security contract schema")
    require(type(contract["schema_version"]) is int and contract["schema_version"] == 1, "Unknown contract")
    require(contract["producer"] == ".github/workflows/trivy-digest-security.yml", "Unapproved scanner producer")
    require(contract["source_sha"] == source_sha and
            contract["publisher_run_id"] == publisher_run_id, "Wrong source/publisher identity")
    require(contract["platform"] == "linux/amd64", "Wrong platform")
    scanner = contract["scanner"]
    require(type(scanner) is dict and set(scanner) == {"name", "version", "db_updated_at"}, "Missing scanner metadata")
    require(scanner["name"] == "trivy" and
            type(scanner["version"]) is str and bool(scanner["version"]) and
            type(scanner["db_updated_at"]) is str and bool(scanner["db_updated_at"]),
            "Unknown scanner or vulnerability database")
    require(type(contract["policy_version"]) is str and bool(contract["policy_version"]),
            "No vulnerability policy version")
    require(type(candidates) is dict and set(candidates) == set(COMPONENTS), "Missing candidate artifacts")
    require(type(contract["images"]) is dict and set(contract["images"]) == set(COMPONENTS),
            "Missing/extra scan subjects")
    for component, repo in COMPONENTS.items():
        candidate = candidates[component]
        require(type(candidate) is dict and
                set(candidate) == {"component", "image", "source_sha", "digest",
                                   "platform", "platform_digest", "workflow", "run_id"},
                f"Invalid publisher artifact: {component}")
        require(candidate["component"] == component and candidate["image"] == repo and
                candidate["source_sha"] == source_sha and
                candidate["workflow"] == "ghcr-candidates.yml" and
                candidate["run_id"] == publisher_run_id and
                candidate["platform"] == "linux/amd64",
                f"Untrusted image source: {component}")
        require(type(candidate["digest"]) is str and bool(DIGEST.fullmatch(candidate["digest"])) and
                type(candidate["platform_digest"]) is str and bool(DIGEST.fullmatch(candidate["platform_digest"])),
                f"Bad OCI digest: {component}")
        record = contract["images"][component]
        fields = {"ref", "platform_digest", "source_sha", "provenance",
                  "sbom_format", "sbom_sha256", "sbom_subject",
                  "vulnerability_report_sha256", "scan_subject", "decision", "exceptions"}
        require(type(record) is dict and set(record) == fields,
                f"Missing/extra scan fields: {component}")
        ref = f"{repo}@{candidate['digest']}"
        require(record["ref"] == ref and
                record["platform_digest"] == candidate["platform_digest"] and
                record["source_sha"] == source_sha, f"Subject/source mismatch: {component}")
        require(record["provenance"] == "verified" and
                record["sbom_format"] == "spdx-json" and
                record["sbom_subject"] == candidate["digest"] and
                record["scan_subject"] == candidate["digest"],
                f"Missing or incorrect attestation/SBOM/scan: {component}")
        for field in ("sbom_sha256", "vulnerability_report_sha256"):
            require(type(record[field]) is str and bool(DIGEST.fullmatch(record[field])),
                    f"Missing artifact hash: {component}/{field}")
        require(record["decision"] == "pass" and record["exceptions"] == [],
                f"Vulnerability policy not passed without unreviewed exceptions: {component}")
    upstream = contract["upstream"]
    require(type(upstream) is dict and bool(upstream), "Missing upstream security coverage")
    if lock is not None:
        expected = set(lock["images"]) - set(COMPONENTS)
        require(set(upstream) == expected, "Missing/unexpected upstream image scan")
    for component, record in upstream.items():
        require(type(record) is dict and set(record) == {
            "ref", "platform_digest", "scan_subject", "sbom_subject", "sbom_sha256",
            "vulnerability_report_sha256", "decision", "exceptions", "provenance_status"
        }, f"Invalid upstream evidence: {component}")
        require(type(record["ref"]) is str and "@sha256:" in record["ref"], "Upstream must be digest pinned")
        digest = "sha256:" + record["ref"].rsplit("@sha256:", 1)[1]
        require(bool(DIGEST.fullmatch(digest)) and record["scan_subject"] == digest and
                record["sbom_subject"] == digest and record["provenance_status"] == "verified" and
                record["decision"] == "pass" and record["exceptions"] == [], 
                f"Upstream verification or policy incomplete: {component}")
        for field in ("sbom_sha256", "vulnerability_report_sha256", "platform_digest"):
            require(type(record[field]) is str and bool(DIGEST.fullmatch(record[field])),
                    f"Bad upstream artifact hash: {component}/{field}")
        if lock is not None:
            image = lock["images"][component]
            require(image["ref"] == record["ref"] and
                    "sha256:" + image["platform_digest"] == record["platform_digest"],
                    f"Untrusted upstream lock binding: {component}")
    if evidence_dir is not None:
        for component, record in {**contract["images"], **upstream}.items():
            for filename, field in ((".sbom.spdx.json", "sbom_sha256"),
                                    (".vuln.json", "vulnerability_report_sha256")):
                path = evidence_dir / (component + filename)
                data = path.read_bytes()
                actual = "sha256:" + hashlib.sha256(data).hexdigest()
                require(actual == record[field], f"Evidence checksum mismatch: {component}/{field}")


def validate_scanner_policy(contract: dict, metadata: dict, ledger: dict,
                            now: datetime | None = None) -> None:
    """Cross-check signed raw scanner DB and exact checked-out source policy."""
    require(type(contract) is dict and type(contract.get("scanner")) is dict,
            "Missing signed scanner contract")
    declared = contract["scanner"]
    require(type(metadata) is dict and type(metadata.get("Version")) is str and
            declared.get("name") == "trivy" and
            metadata["Version"] == declared.get("version") == "0.76.2",
            "Wrong scanner tool or version")
    db = metadata.get("VulnerabilityDB")
    require(type(db) is dict and type(db.get("Version")) is int and
            db["Version"] > 0 and type(db.get("UpdatedAt")) is str and
            db["UpdatedAt"] == declared.get("db_updated_at"),
            "Wrong scanner DB schema version or timestamp")
    try:
        timestamp = datetime.fromisoformat(db["UpdatedAt"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SecurityContractError("Invalid signed Trivy DB timestamp") from exc
    now = now or datetime.now(timezone.utc)
    require(timestamp.tzinfo is not None and now.tzinfo is not None and
            0 <= (now - timestamp).total_seconds() <= 14 * 86400,
            "Stale or future Trivy vulnerability DB")
    require(type(ledger) is dict and set(ledger) == {"schema_version", "exceptions"} and
            ledger["schema_version"] == 1 and ledger["exceptions"] == [],
            "Unapproved or incompatible security exception ledger")
    hash_value = hashlib.sha256(json.dumps(
        ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(contract.get("policy_version") == "v1:" + hash_value,
            "Signed security contract differs from reviewed source exception policy")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True,
                        help="Folder with portal.json, music.json and media.json from approved R3 run")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--scanner-metadata", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--publisher-run-id", required=True, type=int)
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text())
        candidates = {name: json.loads((args.candidates / (name + ".json")).read_text())
                      for name in COMPONENTS}
        lock = json.loads(args.lock.read_text())
        validate_contract(contract, candidates, args.source_sha, args.publisher_run_id,
                          lock=lock, evidence_dir=args.evidence_dir)
        validate_scanner_policy(contract, json.loads(args.scanner_metadata.read_text()),
                                json.loads(args.policy.read_text()))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"R4 security contract rejected: {exc}\n")
    print("R4 security evidence structurally aligned with all three candidate digests")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
