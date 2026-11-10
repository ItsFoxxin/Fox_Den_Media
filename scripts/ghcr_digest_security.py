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


def check_gh_cli_version(version: str) -> None:
    """GitHub CLI <= 2.101 can accept workflow-name prefix matches."""
    ensure(type(version) is str and bool(re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", version)),
           "Unrecognized GitHub CLI version")
    ensure(tuple(int(x) for x in version.split(".")) >= (2, 102, 0),
           "GitHub CLI >= 2.102.0 required for exact workflow signer verification")


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
    """Validate an OCI index OR a platform-specific single-image manifest.

    A registry digest reference identifies the manifest returned by imagetools;
    the runner separately checks the pulled image's OS/architecture. A
    single-manifest upstream has platform_digest == its top-level digest.
    """
    ensure(name in plan and type(plan[name]) is dict, "Unknown manifest subject")
    ensure(type(manifest) is dict and manifest.get("schemaVersion") == 2,
           "Malformed OCI/Docker manifest")
    if type(manifest.get("manifests")) is list:
        entries = manifest["manifests"]
        digests = [item.get("digest") for item in entries
                   if type(item) is dict and type(item.get("platform")) is dict and
                   item["platform"].get("os") == "linux" and
                   item["platform"].get("architecture") == "amd64" and
                   not item["platform"].get("variant")]
        ensure(len(digests) == 1 and digests[0] == plan[name]["platform_digest"],
               f"Missing, duplicated or changed amd64 platform digest: {name}")
    else:
        ensure(manifest.get("mediaType") in {
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
        } and type(manifest.get("config")) is dict and
            type(manifest.get("layers")) is list and bool(manifest["layers"]),
            "Unexpected single-image manifest structure")
        ensure(plan[name]["digest"] == plan[name]["platform_digest"],
               f"Single image digest and platform digest differ: {name}")


def check_report(report: dict, expected_ref: str, image_id: str, *, allow_severe: bool = False) -> None:
    ensure(bool(DIGEST.fullmatch(image_id)), "Missing inspected Docker config digest")
    ensure(report.get("ArtifactType") == "container_image" and
           report.get("ArtifactName") == expected_ref and
           type(report.get("Metadata")) is dict and
           report["Metadata"].get("ImageID") == image_id,
           "Trivy report is not bound to inspected immutable image")
    ensure(type(report.get("Results")) is list and bool(report["Results"]),
           "Missing or empty Trivy scan results")
    identities = set()
    for result in report["Results"]:
        ensure(type(result) is dict and type(result.get("Target")) is str and
               bool(result["Target"]) and type(result.get("Type")) is str and
               bool(result["Type"]), "Malformed Trivy scan target/ecosystem")
        vulnerabilities = result.get("Vulnerabilities", [])
        ensure(vulnerabilities is None or type(vulnerabilities) is list,
               "Malformed Trivy vulnerability list")
        for vuln in vulnerabilities or []:
            ensure(type(vuln) is dict and type(vuln.get("VulnerabilityID")) is str and
                   bool(vuln["VulnerabilityID"]) and
                   type(vuln.get("PkgName")) is str and bool(vuln["PkgName"]) and
                   type(vuln.get("InstalledVersion")) is str and
                   bool(vuln["InstalledVersion"]) and
                   bool(re.fullmatch(r"CVE-[0-9]{4}-[0-9]{4,}", vuln["VulnerabilityID"])) and
                   type(vuln.get("Severity")) is str and
                   vuln["Severity"] in VALID_SEVERITIES,
                   "Malformed, unidentifiable or unknown vulnerability")
            # Match the merged #93 verifier's underlying finding identity.
            # Scanner metadata differences must not split duplicate CVE occurrences.
            identity = (result["Target"], result["Type"], vuln["VulnerabilityID"],
                        vuln["PkgName"], vuln["InstalledVersion"])
            ensure(identity not in identities, "Ambiguous duplicate finding identity")
            identities.add(identity)
            ensure(allow_severe or vuln["Severity"] not in {"HIGH", "CRITICAL", "UNKNOWN"},
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
    ensure(type(db) is dict and type(db.get("Version")) is int and
           db["Version"] > 0 and type(db.get("UpdatedAt")) is str and
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
                   source: str, publisher_run: int, now: datetime | None = None,
                   *, allow_reviewed_severe: bool = False) -> dict:
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
        check_report(report, item["ref"], id_path.read_text().strip(),
                     allow_severe=allow_reviewed_severe)
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



# V2 is a separate, non-cyclic A -> independently reviewed B -> C interface.
# The legacy v1 helper above remains for fixture regression; there is NO
# operational v1 fallback or v1 output in the workflow.
CONTEXT_FIELDS = {"schema_version", "repository", "source_sha", "producer_actor",
                  "release_lock_sha256", "r3_run_id", "scan_run_id",
                  "scanner_metadata_sha256", "images"}
IMAGE_FIELDS = {"image_repository", "manifest_digest", "platform_digest",
                "trivy_report_sha256", "spdx_sbom_sha256"}
RESULT_FIELDS = {"schema_version", "decision", "disposition_document_sha256",
                 "lifecycle_sha256", "source_sha", "release_lock_sha256",
                 "r3_run_id", "scan_run_id", "reviewed_at", "expires_at",
                 "cleared_finding_count", "image_count"}


def strict_load(path: Path) -> dict:
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= 32 * 1024 * 1024, "Missing or unsafe evidence")
    def pairs(items):
        out = {}
        for k, v in items:
            ensure(k not in out, "Duplicate JSON evidence field")
            out[k] = v
        return out
    def reject(_):
        raise EvidenceError("Unsupported JSON numeric evidence")
    obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                     parse_float=reject, parse_constant=reject)
    ensure(type(obj) is dict, "Evidence root must be JSON object")
    return obj


def assert_empty_policy(ledger: dict) -> None:
    ensure(type(ledger) is dict and set(ledger) == {"schema_version", "exceptions"}
           and type(ledger["schema_version"]) is int and
           ledger["schema_version"] == 1 and ledger["exceptions"] == [],
           "V2 never permits security exceptions")


def collect_v2_context(plan: dict, reports: Path, scanner: dict, policy: dict,
                       lock_path: Path, scanner_path: Path, source: str,
                       r3_run: int, scan_run: int, actor: str,
                       now: datetime | None = None) -> dict:
    """A: strict integrity and complete image scope, but NOT vulnerability pass."""
    now = now or datetime.now(timezone.utc)
    assert_empty_policy(policy)
    ensure(type(scan_run) is int and scan_run > 0 and type(r3_run) is int and
           r3_run > 0 and bool(SHA.fullmatch(source)), "Invalid approved scan/R3/source")
    ensure(type(actor) is str and bool(re.fullmatch(
        r"github:[A-Za-z0-9-]{1,39}", actor)), "Invalid authenticated scan actor")
    check_scanner(scanner, now)
    lock = strict_load(lock_path)
    ensure(type(plan) is dict and set(FIRST_PARTY) <= set(plan) and
           "nginx" in plan and set(plan) <= set(FIRST_PARTY) | set(UPSTREAM) and
           lock.get("source_sha") == source and
           type(lock.get("images")) is dict and set(lock["images"]) == set(plan) and
           type(lock.get("services")) is dict and
           set(lock["services"].values()) == set(plan) and
           lock.get("publisher") == {"workflow": PUBLISHER, "run_id": r3_run,
                                     "source_sha": source},
           "Missing or untrusted complete R2 image/service coverage")
    images = {}
    for name, item in plan.items():
        ensure(type(item) is dict and item.get("digest") == image_digest(item.get("ref"))
               and item.get("kind") == ("first_party" if name in FIRST_PARTY else "upstream"),
               "Unexpected scan image")
        report_path = reports / (name + ".vuln.json")
        sbom_path = reports / (name + ".sbom.spdx.json")
        report = strict_load(report_path)
        check_report(report, item["ref"],
                     (reports / (name + ".image-id")).read_text().strip(),
                     allow_severe=True)
        check_spdx(strict_load(sbom_path))
        check_manifest(name, plan, strict_load(reports / (name + ".manifest.json")))
        images[name] = {
            "image_repository": item["ref"].split("@", 1)[0],
            "manifest_digest": item["digest"],
            "platform_digest": item["platform_digest"],
            "trivy_report_sha256": sha256(report_path),
            "spdx_sbom_sha256": sha256(sbom_path),
        }
    return {
        "schema_version": 1, "repository": "ItsFoxxin/Fox_Den_Media",
        "source_sha": source, "producer_actor": actor,
        "release_lock_sha256": sha256(lock_path), "r3_run_id": r3_run,
        "scan_run_id": scan_run, "scanner_metadata_sha256": sha256(scanner_path),
        "images": images,
    }


def severe_inventory(context: dict, reports: Path) -> dict:
    """Rebuild every distinct HIGH/CRITICAL occurrence from untouched Trivy bytes."""
    out, identities = {}, set()
    for name, image in context["images"].items():
        doc = strict_load(reports / (name + ".vuln.json"))
        for i, result in enumerate(doc["Results"]):
            for j, vuln in enumerate(result.get("Vulnerabilities") or []):
                severity = vuln["Severity"]
                ensure(severity != "UNKNOWN", "UNKNOWN finding cannot be cleared")
                finding_hash = "sha256:" + hashlib.sha256(json.dumps(
                    vuln, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()
                identity = (name, result["Target"], result["Type"],
                            vuln["VulnerabilityID"], vuln["PkgName"],
                            vuln["InstalledVersion"])
                ensure(identity not in identities, "Ambiguous duplicate finding")
                identities.add(identity)
                if severity in {"HIGH", "CRITICAL"}:
                    out[(name, i, j)] = {
                        "component": name, "result_index": i,
                        "vulnerability_index": j,
                        "cve_id": vuln["VulnerabilityID"], "target": result["Target"],
                        "ecosystem": result["Type"], "package_name": vuln["PkgName"],
                        "installed_version": vuln["InstalledVersion"],
                        "finding_sha256": finding_hash, **image,
                    }
    return out


def final_v2_contract(plan: dict, reports: Path, scanner: dict, policy: dict,
                      lock_path: Path, scanner_path: Path, context: dict,
                      reviewed: dict, revalidated: dict, reviewed_raw: bytes,
                      dispositions: dict, source: str, r3_run: int, scan_run: int,
                      producer_actor: str, review_run: int,
                      now: datetime | None = None) -> dict:
    """C: called ONLY after separately authenticated review B and current CLI verify.

    Actual Ed25519 review/owner keys, latest lifecycle and OIDC verification
    are validated by the independent PR #93 verifier plus trusted workflow.
    A JSON "pass" by itself is NOT an authorization.
    """
    now = now or datetime.now(timezone.utc)
    ensure(type(context) is dict and set(context) == CONTEXT_FIELDS and
           type(context.get("schema_version")) is int and
           context["schema_version"] == 1,
           "Missing or extra signed scan context fields")
    expected = collect_v2_context(plan, reports, scanner, policy, lock_path,
                                  scanner_path, source, r3_run, scan_run,
                                  producer_actor, now)
    ensure(context == expected, "Altered signed A image/source/report/lock context")
    ensure(type(review_run) is int and review_run > 0 and review_run != scan_run,
           "Nonindependent review run")
    ensure(type(reviewed) is dict and set(reviewed) == RESULT_FIELDS and
           reviewed == revalidated and
           type(reviewed.get("schema_version")) is int and
           reviewed["schema_version"] == 1 and
           reviewed.get("decision") == "pass",
           "No matching signed and freshly revalidated independent review")
    ensure(reviewed["source_sha"] == source and reviewed["r3_run_id"] == r3_run
           and reviewed["scan_run_id"] == scan_run and
           reviewed["release_lock_sha256"] == context["release_lock_sha256"]
           and type(reviewed["image_count"]) is int and
           reviewed["image_count"] == len(context["images"]),
           "Review not bound to exact source/R3/A/lock/image inventory")
    for name in ("disposition_document_sha256", "lifecycle_sha256"):
        ensure(type(reviewed[name]) is str and bool(DIGEST.fullmatch(reviewed[name])),
               "Missing signed review/lifecycle hash")
    doc_hash = "sha256:" + hashlib.sha256(json.dumps(
        dispositions, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    ensure(doc_hash == reviewed["disposition_document_sha256"] and
           dispositions.get("source_sha") == source and
           dispositions.get("scan_run_id") == scan_run and
           dispositions.get("r3_run_id") == r3_run and
           dispositions.get("producer_actor") == producer_actor and
           dispositions.get("release_lock_sha256") == context["release_lock_sha256"],
           "Tampered or misbound disposition review document")
    ensure(type(dispositions.get("records")) is list, "Missing review records")
    inventory = severe_inventory(context, reports)
    ensure(len(inventory) == len(dispositions["records"]) and
           type(reviewed["cleared_finding_count"]) is int and
           len(inventory) == reviewed["cleared_finding_count"],
           "Missing or extra HIGH/CRITICAL dispositions")
    seen = set()
    for rec in dispositions["records"]:
        ensure(type(rec) is dict and rec.get("status") in {"FIXED", "NOT_AFFECTED"}
               and type(rec.get("subject")) is dict, "Forged disposition record")
        subject = rec["subject"]
        key = (subject.get("component"), subject.get("result_index"),
               subject.get("vulnerability_index"))
        ensure(key in inventory and key not in seen and subject == inventory[key],
               "Wrong digest, CVE, finding hash or duplicate disposition")
        seen.add(key)
    def valid_time(value: str) -> datetime:
        ensure(type(value) is str and bool(re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value)),
            "Invalid security review timestamp")
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    ensure(valid_time(reviewed["reviewed_at"]) <= now <
           valid_time(reviewed["expires_at"]), "Expired or future security review")
    ensure(type(reviewed_raw) is bytes and bool(reviewed_raw),
           "Missing original signed review result bytes")
    contract = build_contract(plan, reports, scanner, policy, source, r3_run,
                              now, allow_reviewed_severe=True)
    contract["schema_version"] = 2
    contract["disposition_review"] = {
        "schema_version": 1, "artifact_name": "security-disposition-review-v1",
        "verification_file": "disposition-verification.json",
        "verification_sha256": "sha256:" + hashlib.sha256(reviewed_raw).hexdigest(),
        "dispositions_sha256": doc_hash,
        "review_workflow": ".github/workflows/security-disposition-review.yml",
        "review_run_id": review_run,
        "verified_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return contract



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
    cli = sub.add_parser("check-gh-version")
    cli.add_argument("version")
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
    for mode in ("collect-v2", "finalize-v2"):
        p = sub.add_parser(mode)
        fields = ("plan", "reports", "scanner", "policy", "lock", "source-sha",
                  "publisher-run-id", "scan-run-id", "producer-actor", "output")
        if mode == "finalize-v2":
            fields += ("context", "reviewed-result", "revalidated-result",
                       "dispositions", "review-run-id")
        for field in fields:
            p.add_argument("--" + field, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "collect-v2":
            value = collect_v2_context(
                strict_load(Path(args.plan)), Path(args.reports),
                strict_load(Path(args.scanner)), strict_load(Path(args.policy)),
                Path(args.lock), Path(args.scanner), args.source_sha,
                int(args.publisher_run_id), int(args.scan_run_id),
                args.producer_actor)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
            return
        if args.mode == "finalize-v2":
            reviewed_bytes = Path(args.reviewed_result).read_bytes()
            value = final_v2_contract(
                strict_load(Path(args.plan)), Path(args.reports),
                strict_load(Path(args.scanner)), strict_load(Path(args.policy)),
                Path(args.lock), Path(args.scanner),
                strict_load(Path(args.context)), strict_load(Path(args.reviewed_result)),
                strict_load(Path(args.revalidated_result)), reviewed_bytes,
                strict_load(Path(args.dispositions)), args.source_sha,
                int(args.publisher_run_id), int(args.scan_run_id),
                args.producer_actor, int(args.review_run_id))
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            # Cross-check the merged #93 v2 adapter; OIDC and current reviewer
            # signatures/lifecycle are verified independently by Phase C workflow.
            from scripts.verify_security_dispositions import require_r4_contract_v2
            require_r4_contract_v2(value, strict_load(Path(args.reviewed_result)),
                                   reviewed_bytes)
            output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
            return
        if args.mode == "prepare":
            candidates = {name: load(args.candidates / f"{name}.json") for name in FIRST_PARTY}
            plan = prepare(load(args.lock), load(args.rendered), candidates,
                           load(args.upstream_provenance), args.source_sha,
                           args.publisher_run_id)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
        elif args.mode == "check-gh-version":
            check_gh_cli_version(args.version)
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
