"""R4 consumer for digest-bound scan contracts from the independent security pipeline.

This validates claimed policy data only. A trusted R4 workflow MUST first
verify the security artifact's attestation/signing workflow and each image's
GitHub build attestation and registry digest before consuming these fields.
"""
from __future__ import annotations
import argparse
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
                      publisher_run_id: int) -> None:
    require(bool(SHA.fullmatch(source_sha)), "Bad approved source SHA")
    required = {"schema_version", "producer", "source_sha", "publisher_run_id",
                "platform", "scanner", "policy_version", "images"}
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

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True,
                        help="Folder with portal.json, music.json and media.json from approved R3 run")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--publisher-run-id", required=True, type=int)
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text())
        candidates = {name: json.loads((args.candidates / (name + ".json")).read_text())
                      for name in COMPONENTS}
        validate_contract(contract, candidates, args.source_sha, args.publisher_run_id)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"R4 security contract rejected: {exc}\n")
    print("R4 security evidence structurally aligned with all three candidate digests")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
