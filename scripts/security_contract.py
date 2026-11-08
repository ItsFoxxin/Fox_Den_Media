#!/usr/bin/env python3
"""Machine-readable container security assessment. Advisory CI is not a release gate."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from scripts.trivy_report import normalized_findings, compare

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
COMPONENTS = ("portal", "music", "media")
FIELDS = ("component", "finding_id", "package_type", "package", "installed",
          "owner", "approved_by", "justification", "issue", "expires")


class InvalidEvidence(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InvalidEvidence(message)


def read_json(path):
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(result, dict), "Expected JSON object")
    return result


def hash_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exceptions_by_identity(ledger, today):
    require(ledger.get("schema_version") == 1 and isinstance(ledger.get("exceptions"), list),
            "Invalid exception ledger")
    indexed, expired = {}, []
    for item in ledger["exceptions"]:
        require(isinstance(item, dict) and all(isinstance(item.get(f), str)
                and item[f].strip() for f in FIELDS), "Incomplete exception")
        require(item["component"] in COMPONENTS, "Unknown exception component")
        require(bool(re.fullmatch(
            r"https://github\.com/ItsFoxxin/Fox_Den_Media/issues/[1-9][0-9]*", item["issue"])),
            "Exception needs a linked repository issue")
        require(len(item["justification"].strip()) >= 20, "Justification too short")
        require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["expires"])), "Invalid expiry")
        try:
            expiry = date.fromisoformat(item["expires"])
        except ValueError as error:
            raise InvalidEvidence("Invalid expiry date") from error
        key = (item["component"], item["finding_id"], item["package_type"],
               item["package"], item["installed"])
        require(key not in indexed, "Duplicate exception")
        indexed[key] = item
        if expiry <= today:
            expired.append({"component": item["component"], "finding_id": item["finding_id"],
                            "expires": item["expires"], "issue": item["issue"]})
    return indexed, expired


def assess(*, component, report, sbom, scanner, ledger, source_sha,
           expected_source_sha, image_ref, image_id, image_digest=None,
           expected_image_digest=None, baseline=None, baseline_verified=False,
           mode="advisory", today=None, attestation_refs=None, evidence_hashes=None,
           scan_run_url=None):
    today = today or datetime.now(timezone.utc).date()
    require(component in COMPONENTS and mode in ("advisory", "enforce"), "Invalid mode/component")
    require(isinstance(source_sha, str) and bool(SHA.fullmatch(source_sha)),
            "Malformed source commit")
    if expected_source_sha is not None:
        require(source_sha == expected_source_sha, "Stale source commit")
    require(isinstance(image_id, str) and bool(DIGEST.fullmatch(image_id)),
            "Invalid local image ID")
    require(report.get("ArtifactType") == "container_image"
            and report.get("ArtifactName") == image_ref
            and (report.get("Metadata") or {}).get("ImageID") == image_id,
            "Wrong Trivy report image or image ID")
    require(sbom.get("bomFormat") == "CycloneDX"
            and isinstance(sbom.get("specVersion"), str)
            and bool(re.fullmatch(r"1\.[4-9]", sbom["specVersion"]))
            and isinstance(sbom.get("components"), list), "Invalid CycloneDX SBOM")
    require(isinstance(scanner.get("Version"), str)
            and bool(VERSION.fullmatch(scanner["Version"])), "Missing scanner version")
    require(not (report.get("Trivy") or {}).get("Version")
            or report["Trivy"]["Version"] == scanner["Version"], "Scanner mismatch")
    if image_digest is not None:
        require(bool(DIGEST.fullmatch(image_digest)), "Malformed OCI manifest digest")
    if expected_image_digest is not None:
        require(bool(DIGEST.fullmatch(expected_image_digest))
                and expected_image_digest == image_digest, "Incorrect OCI manifest digest")
    require(not baseline_verified or baseline is not None, "Verified baseline missing")
    require(all(isinstance(ref, str) and ref.startswith("https://")
                for ref in (attestation_refs or [])), "Invalid attestation reference")

    rows = normalized_findings(report)
    indexed, expired = exceptions_by_identity(ledger, today)
    blocked, waived = [], []
    for row in rows:
        if row["severity"] not in ("HIGH", "CRITICAL"):
            continue
        exception = indexed.get((component, row["id"], row["package_type"],
                                 row["package"], row["installed"]))
        if exception and exception not in expired and date.fromisoformat(exception["expires"]) > today:
            waived.append({"finding": row, "issue": exception["issue"],
                           "expires": exception["expires"]})
        else:
            blocked.append(row)

    delta = None
    if baseline is not None:
        require(baseline.get("component") == component
                and isinstance(baseline.get("findings"), list)
                and isinstance(baseline.get("source_sha"), str)
                and bool(SHA.fullmatch(baseline["source_sha"])), "Invalid baseline")
        delta = compare({"component": component, "findings": rows}, baseline)

    db_updated = (scanner.get("VulnerabilityDB") or {}).get("UpdatedAt")
    updated = None
    if db_updated:
        require(isinstance(db_updated, str), "Invalid DB timestamp")
        try:
            updated = datetime.fromisoformat(db_updated.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidEvidence("Invalid DB timestamp") from error
        require(updated.tzinfo is not None, "Timezone required in DB timestamp")
    reasons = []
    if blocked:
        reasons.append("unaccepted_high_or_critical")
    if expired:
        reasons.append("expired_exception")
    if any(row["severity"] == "UNKNOWN" for row in rows):
        reasons.append("unknown_severity")
    if not baseline_verified:
        reasons.append("trusted_baseline_unavailable")
    if not image_digest:
        reasons.append("immutable_manifest_digest_unavailable")
    if not updated:
        reasons.append("scanner_db_timestamp_unavailable")
    if mode == "enforce":
        if expected_source_sha is None:
            reasons.append("expected_source_sha_unavailable")
        if expected_image_digest is None:
            reasons.append("expected_digest_unavailable")
        if updated:
            age = (datetime.now(timezone.utc) - updated).total_seconds()
            if age < -86400 or age > 14 * 86400:
                reasons.append("scanner_db_stale")
    decision = ("fail" if blocked or expired or (mode == "enforce" and reasons)
                else "review_required" if reasons else "pass")
    return {
        "schema_version": 1, "component": component,
        "source": {"commit": source_sha, "expected_commit": expected_source_sha},
        "image": {"reference": image_ref, "local_config_id": image_id,
                  "manifest_digest": image_digest, "expected_manifest_digest": expected_image_digest},
        "evidence": {"files": evidence_hashes or {}, "scan_run_url": scan_run_url,
                     "scanner_version": scanner["Version"],
                     "vulnerability_db_updated_at": db_updated,
                     "sbom_format": "CycloneDX", "sbom_spec": sbom["specVersion"],
                     "attestation_references": attestation_refs or []},
        "baseline": {"verified_by_caller": baseline_verified,
                     "source_commit": baseline.get("source_sha") if baseline else None,
                     "new": len(delta["new"]) if delta else None,
                     "resolved": len(delta["resolved"]) if delta else None,
                     "unchanged": delta["unchanged"] if delta else None},
        "policy": {"mode": mode, "decision": decision, "reasons": reasons,
                   "critical_high_unaccepted": blocked, "approved_exceptions": waived,
                   "expired_exceptions": expired, "findings_total": len(rows),
                   "release_eligible": mode == "enforce" and decision == "pass"},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "sbom", "scanner-metadata", "exceptions", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--component", required=True, choices=COMPONENTS)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--expected-source-sha")
    p.add_argument("--image-ref", required=True)
    p.add_argument("--image-id", required=True)
    p.add_argument("--image-digest")
    p.add_argument("--expected-image-digest")
    p.add_argument("--baseline", type=Path)
    p.add_argument("--baseline-verified", action="store_true")
    p.add_argument("--attestation-ref", action="append", default=[])
    p.add_argument("--scan-run-url")
    p.add_argument("--mode", choices=("advisory", "enforce"), default="advisory")
    args = p.parse_args()
    try:
        paths = {"trivy_report": args.report, "cyclonedx_sbom": args.sbom,
                 "scanner_metadata": args.scanner_metadata, "exception_ledger": args.exceptions}
        result = assess(
            component=args.component, report=read_json(args.report),
            sbom=read_json(args.sbom), scanner=read_json(args.scanner_metadata),
            ledger=read_json(args.exceptions), source_sha=args.source_sha,
            expected_source_sha=args.expected_source_sha, image_ref=args.image_ref,
            image_id=args.image_id, image_digest=args.image_digest,
            expected_image_digest=args.expected_image_digest,
            baseline=read_json(args.baseline) if args.baseline else None,
            baseline_verified=args.baseline_verified, attestation_refs=args.attestation_ref,
            scan_run_url=args.scan_run_url, mode=args.mode,
            evidence_hashes={key: hash_file(path) for key, path in paths.items()})
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Security evidence rejected: " + str(error), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Security policy: " + result["policy"]["decision"] + " (" + args.mode + ")")
    return 2 if args.mode == "enforce" and result["policy"]["decision"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
