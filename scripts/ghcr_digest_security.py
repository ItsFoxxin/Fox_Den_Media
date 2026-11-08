#!/usr/bin/env python3
"""Fail-closed R4 security producer for exact OCI digests; no publishing or builds.

The GitHub workflow authenticates publisher runs, OCI attestations and artifact
signatures. These offline functions verify data identities, scope and policy.
No caller-provided claim of provenance substitutes for workflow verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

FIRST_PARTY = {
    "portal": "ghcr.io/itsfoxxin/fox-den-media-portal",
    "music": "ghcr.io/itsfoxxin/fox-den-media-music",
    "media": "ghcr.io/itsfoxxin/fox-den-media-media",
}
UPSTREAM = {
    "nginx": "docker.io/library/nginx",
    "browser": "docker.io/jlesage/firefox",
    "jellyfin": "docker.io/jellyfin/jellyfin",
    "gluetun": "docker.io/qmcgaw/gluetun",
    "qbittorrent": "lscr.io/linuxserver/qbittorrent",
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
GITHUB_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
VALID_SEVERITIES = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
PRODUCER = ".github/workflows/trivy-digest-security.yml"
PUBLISHER = "ghcr-candidates.yml"


class EvidenceError(ValueError):
    """A required security invariant failed."""


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    ensure(type(data) is dict, f"Expected JSON object: {path}")
    return data


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def image_digest(ref: str) -> str:
    ensure(type(ref) is str and ref.count("@") == 1, "Image must be digest-only")
    digest = ref.rsplit("@", 1)[1]
    ensure(bool(DIGEST.fullmatch(digest)), "Invalid image manifest digest")
    return digest


def prepare(lock: dict, rendered: dict, candidates: dict,
            upstream_provenance: dict, source: str, publisher_run: int) -> dict:
    """Prepare a complete scan plan; downstream workflow must verify attestations."""
    ensure(bool(SHA.fullmatch(source)), "Invalid approved source SHA")
    ensure(type(publisher_run) is int and publisher_run > 0, "Invalid R3 run")
    ensure(lock.get("source_sha") == source and lock.get("platform") == "linux/amd64",
           "Unapproved lock source/platform")
    ensure(lock.get("version") == "1.0.0", "Wrong release version")
    pub = lock.get("publisher")
    ensure(type(pub) is dict and pub == {
        "workflow": PUBLISHER, "run_id": publisher_run, "source_sha": source
    }, "Lock publisher differs from authenticated R3")
    images = lock.get("images")
    ensure(type(images) is dict and set(FIRST_PARTY) <= set(images), "Missing first-party images")
    ensure(set(images) <= set(FIRST_PARTY) | set(UPSTREAM) and "nginx" in images,
           "Missing ingress or unsupported image")
    ensure({"music", "media"} <= set(lock.get("profiles", [])),
           "R4 requires all three first-party components enabled")
    ensure(type(candidates) is dict and set(candidates) == set(FIRST_PARTY),
           "Exactly three R3 candidate artifacts required")
    ensure(type(upstream_provenance) is dict and
           set(upstream_provenance) == {"schema_version", "upstream"} and
           upstream_provenance["schema_version"] == 1 and
           type(upstream_provenance["upstream"]) is dict, "Invalid reviewed upstream provenance ledger")
    expected_upstream = set(images) - set(FIRST_PARTY)
    ensure(set(upstream_provenance["upstream"]) == expected_upstream,
           "Missing or unreviewed enabled upstream signer")
    services = rendered.get("services")
    ensure(type(rendered) is dict and set(rendered) == {"services"} and
           type(services) is dict, "Rendered evidence must contain services only")
    ensure(type(lock.get("services")) is dict and set(services) == set(lock["services"]),
           "Rendered release services differ from lock")
    for service, config in services.items():
        ensure(type(config) is dict and set(config) == {"image"} and
               config["image"] == images[lock["services"][service]]["ref"],
               "Rendered Compose evidence must contain image only (no secrets or build)")
    plan = {}
    for name, repo in {**FIRST_PARTY, **UPSTREAM}.items():
        if name not in images:
            continue
        entry = images[name]
        ensure(type(entry) is dict and
               set(entry) == {"ref", "platform", "platform_digest", "source_sha"},
               f"Incomplete R2 image: {name}")
        digest = image_digest(entry["ref"])
        ensure(entry["ref"] == f"{repo}@{digest}" and entry["platform"] == "linux/amd64" and
               type(entry["platform_digest"]) is str and
               bool(DIGEST.fullmatch("sha256:" + entry["platform_digest"])),
               f"Bad lock image identity: {name}")
        if name in FIRST_PARTY:
            ensure(entry["source_sha"] == source, f"Wrong first-party source: {name}")
            candidate = candidates[name]
            ensure(type(candidate) is dict and
                   set(candidate) == {"component", "image", "source_sha", "digest",
                                      "platform", "platform_digest", "workflow", "run_id"} and
                   candidate == {"component": name, "image": repo, "source_sha": source,
                                 "digest": digest, "platform": "linux/amd64",
                                 "platform_digest": "sha256:" + entry["platform_digest"],
                                 "workflow": PUBLISHER, "run_id": publisher_run},
                   f"R3 candidate mismatch: {name}")
            signer = {"source_repo": "ItsFoxxin/Fox_Den_Media", "source_sha": source,
                      "source_ref": "refs/heads/main",
                      "signer_workflow": "ItsFoxxin/Fox_Den_Media/.github/workflows/ghcr-candidates.yml"}
        else:
            ensure(entry["source_sha"] is None, f"Upstream impersonates source: {name}")
            signer = upstream_provenance["upstream"][name]
            ensure(type(signer) is dict and set(signer) == {
                "ref", "source_repo", "source_sha", "source_ref", "signer_workflow"
            } and signer["ref"] == entry["ref"], f"Unapproved upstream ref: {name}")
            ensure(type(signer["source_repo"]) is str and
                   bool(GITHUB_REPO.fullmatch(signer["source_repo"])) and
                   type(signer["source_sha"]) is str and
                   bool(SHA.fullmatch(signer["source_sha"])) and
                   type(signer["source_ref"]) is str and
                   signer["source_ref"].startswith(("refs/tags/", "refs/heads/")) and
                   signer["signer_workflow"].startswith(
                       signer["source_repo"] + "/.github/workflows/") and
                   signer["signer_workflow"].endswith((".yml", ".yaml")),
                   f"Unverifiable upstream signer metadata: {name}")
        plan[name] = {
            "ref": entry["ref"], "digest": digest,
            "platform_digest": "sha256:" + entry["platform_digest"],
            "source_sha": source if name in FIRST_PARTY else None,
            "kind": "first_party" if name in FIRST_PARTY else "upstream",
            **signer,
        }
    return plan


def check_manifest(name: str, plan: dict, manifest: dict) -> None:
    ensure(name in plan, "Unknown manifest subject")
    ensure(type(manifest) is dict and manifest.get("schemaVersion") == 2 and
           type(manifest.get("manifests")) is list, "Expected OCI index/manifest list")
    digests = [item.get("digest") for item in manifest["manifests"]
               if type(item) is dict and type(item.get("platform")) is dict and
               item["platform"].get("os") == "linux" and
               item["platform"].get("architecture") == "amd64" and
               not item["platform"].get("variant")]
    ensure(len(digests) == 1 and digests[0] == plan[name]["platform_digest"],
           f"Missing, duplicated or changed amd64 platform digest: {name}")


def check_report(report: dict, expected_ref: str, image_id: str) -> None:
    ensure(bool(DIGEST.fullmatch(image_id)), "Missing inspected Docker config digest")
    ensure(report.get("ArtifactType") == "container_image" and
           report.get("ArtifactName") == expected_ref and
           type(report.get("Metadata")) is dict and
           report["Metadata"].get("ImageID") == image_id,
           "Trivy report is not bound to inspected immutable image")
    ensure(type(report.get("Results")) is list, "Missing Trivy scan results")
    for result in report["Results"]:
        ensure(type(result) is dict, "Malformed Trivy result")
        for vuln in result.get("Vulnerabilities") or []:
            ensure(type(vuln) is dict and type(vuln.get("VulnerabilityID")) is str and
                   bool(vuln["VulnerabilityID"]) and
                   type(vuln.get("PkgName")) is str and bool(vuln["PkgName"]) and
                   type(vuln.get("InstalledVersion")) is str and
                   bool(vuln["InstalledVersion"]) and
                   vuln.get("Severity") in VALID_SEVERITIES,
                   "Malformed, unidentifiable or unknown vulnerability")
            ensure(vuln["Severity"] not in {"HIGH", "CRITICAL", "UNKNOWN"},
                   f"Undispositioned required finding: {vuln['VulnerabilityID']}")


def check_spdx(sbom: dict) -> None:
    ensure(type(sbom) is dict and sbom.get("spdxVersion") == "SPDX-2.3" and
           sbom.get("SPDXID") == "SPDXRef-DOCUMENT" and
           type(sbom.get("creationInfo")) is dict and
           type(sbom.get("packages")) is list and len(sbom["packages"]) > 0,
           "Missing or structurally invalid Trivy SPDX SBOM")


def check_scanner(metadata: dict, now: datetime) -> dict:
    ensure(type(metadata) is dict and
           re.fullmatch(r"\d+\.\d+\.\d+", str(metadata.get("Version", ""))) and
           metadata["Version"] == "0.76.2", "Unapproved scanner version")
    db = metadata.get("VulnerabilityDB")
    ensure(type(db) is dict and type(db.get("Version")) is int and\n           db["Version"] > 0 and type(db.get("UpdatedAt")) is str and
           bool(db["UpdatedAt"]), "Vulnerability DB metadata missing")
    try:
        updated = datetime.fromisoformat(db["UpdatedAt"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("Invalid vulnerability DB timestamp") from exc
    ensure(updated.tzinfo is not None and 0 <= (now - updated).total_seconds() <= 14 * 86400,
           "Vulnerability DB expired or in future")
    return {"name": "trivy", "version": metadata["Version"],
            "db_updated_at": db["UpdatedAt"]}


def build_contract(plan: dict, reports_dir: Path, scanner: dict, ledger: dict,
                   source: str, publisher_run: int, now: datetime | None = None) -> dict:
    """Only call after workflow verified every source, manifest and attestation."""
    now = now or datetime.now(timezone.utc)
    ensure(type(ledger) is dict and set(ledger) == {"schema_version", "exceptions"} and
           ledger["schema_version"] == 1 and type(ledger["exceptions"]) is list,
           "Invalid reviewed security policy")
    # R4's current consumer accepts only []. Never silently downgrade a
    # reviewed waiver to pass; its expiry/owner checks require a later revision.
    ensure(not ledger["exceptions"], "R4 cannot accept exceptions; owner disposition required")
    ensure(type(plan) is dict and set(FIRST_PARTY) <= set(plan) and "nginx" in plan and
           set(plan) <= set(FIRST_PARTY) | set(UPSTREAM),
           "Incomplete image security plan")
    scanner_record = check_scanner(scanner, now)
    first, upstream = {}, {}
    for name, item in plan.items():
        ensure(type(item) is dict and item.get("digest") == image_digest(item.get("ref")) and
               item.get("kind") == ("first_party" if name in FIRST_PARTY else "upstream"),
               f"Untrusted scan plan: {name}")
        report_path = reports_dir / f"{name}.vuln.json"
        sbom_path = reports_dir / f"{name}.sbom.spdx.json"
        id_path = reports_dir / f"{name}.image-id"
        manifest_path = reports_dir / f"{name}.manifest.json"
        report, sbom = load(report_path), load(sbom_path)
        check_manifest(name, plan, load(manifest_path))
        check_report(report, item["ref"], id_path.read_text().strip())
        check_spdx(sbom)
        if type(report.get("Trivy")) is dict and report["Trivy"].get("Version"):
            ensure(report["Trivy"]["Version"] == scanner_record["version"],
                   "Scan/metadata version mismatch")
        base = {
            "ref": item["ref"], "platform_digest": item["platform_digest"],
            "sbom_subject": item["digest"], "sbom_sha256": sha256(sbom_path),
            "scan_subject": item["digest"],
            "vulnerability_report_sha256": sha256(report_path),
            "decision": "pass", "exceptions": [],
        }
        if name in FIRST_PARTY:
            first[name] = {
                **base, "source_sha": source, "provenance": "verified",
                "sbom_format": "spdx-json",
            }
        else:
            upstream[name] = {**base, "provenance_status": "verified"}
    ensure(set(first) == set(FIRST_PARTY), "Missing first-party subjects")
    return {
        "schema_version": 1, "producer": PRODUCER, "source_sha": source,
        "publisher_run_id": publisher_run, "platform": "linux/amd64",
        "scanner": scanner_record,
        "policy_version": "v1:" + hashlib.sha256(
            json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "images": first, "upstream": upstream,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pre = sub.add_parser("prepare")
    pre.add_argument("--lock", type=Path, required=True)
    pre.add_argument("--rendered", type=Path, required=True)
    pre.add_argument("--candidates", type=Path, required=True)
    pre.add_argument("--upstream-provenance", type=Path, required=True)
    pre.add_argument("--source-sha", required=True)
    pre.add_argument("--publisher-run-id", type=int, required=True)
    pre.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("check-manifest")
    check.add_argument("--plan", type=Path, required=True)
    check.add_argument("--name", required=True)
    check.add_argument("--manifest", type=Path, required=True)
    build = sub.add_parser("assemble")
    build.add_argument("--plan", type=Path, required=True)
    build.add_argument("--reports", type=Path, required=True)
    build.add_argument("--scanner", type=Path, required=True)
    build.add_argument("--policy", type=Path, required=True)
    build.add_argument("--source-sha", required=True)
    build.add_argument("--publisher-run-id", type=int, required=True)
    build.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            candidates = {name: load(args.candidates / f"{name}.json") for name in FIRST_PARTY}
            plan = prepare(load(args.lock), load(args.rendered), candidates,
                           load(args.upstream_provenance), args.source_sha,
                           args.publisher_run_id)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
        elif args.mode == "check-manifest":
            check_manifest(args.name, load(args.plan), load(args.manifest))
        else:
            plan = load(args.plan)
            ensure(all(item.get("source_sha") == args.source_sha for item in plan.values()
                       if item.get("kind") == "first_party"), "Wrong approved source")
            contract = build_contract(plan, args.reports, load(args.scanner),
                                      load(args.policy), args.source_sha,
                                      args.publisher_run_id)
            args.output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Digest security producer rejected: {exc}\n")


if __name__ == "__main__":
    main()
