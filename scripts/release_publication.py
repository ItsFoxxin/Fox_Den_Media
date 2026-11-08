#!/usr/bin/env python3
"""Fox Den Media R5: validate already-published evidence; never build or deploy.

R3/R4 own image creation, scanning and artifact attestation. This script can
only consume their immutable evidence. The workflow supplies the authorization
boundary, then re-runs these checks immediately before publishing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

REPOSITORY = "ItsFoxxin/Fox_Den_Media"
VERSION = "1.0.0"
TAG = "v1.0.0"
R4_WORKFLOW = ".github/workflows/release-verify.yml"
R3_WORKFLOW = "ItsFoxxin/Fox_Den_Media/.github/workflows/release-candidate.yml"
R4_ARTIFACT = "foxden-r4-release-ready-v1.0.0"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FIRST_PARTY = {
    "portal": "ghcr.io/itsfoxxin/fox-den-media-portal",
    "music": "ghcr.io/itsfoxxin/fox-den-media-music",
    "media": "ghcr.io/itsfoxxin/fox-den-media-media",
}
REQUIRED_CHECKS = (
    "Monorepo strict gate",
    "CodeQL (python)",
    "CodeQL (javascript-typescript)",
    "CodeQL",
)
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
    data = json.loads(path.read_text(encoding="utf-8"))
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
    require(valid_sha(source_sha), "Source SHA must be a full 40-character hex commit")
    checks = payload.get("check_runs")
    require(isinstance(checks, list) and checks, "Missing check-run evidence")
    for name in REQUIRED_CHECKS:
        matches = [c for c in checks if isinstance(c, dict) and c.get("name") == name]
        require(matches, "Missing required check: " + name)
        # The live API uses filter=latest; do not choose a stale green run.
        require(all(c.get("head_sha") == source_sha for c in matches),
                "Required check has wrong source identity: " + name)
        require(all(c.get("status") == "completed" and c.get("conclusion") == "success"
                    for c in matches), "Required check not successful: " + name)


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
        r"\b(?:10|192\\.168|172\\.(?:1[6-9]|2[0-9]|3[01]))"
        r"\\.\\d{1,3}\\.\\d{1,3}(?:\\.\\d{1,3})?\\b", notes),
        "Release notes may contain private infrastructure addresses")
    require(not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                          r"(?i:(?:password|api[_-]?key|secret|access[_-]?token)\\s*[=:]\\s*\\S{8,})",
                          notes), "Release notes may contain credentials")


def validate_bundle(root: Path, source_sha: str, r4_id: int) -> dict:
    require(valid_sha(source_sha), "Invalid release source SHA")
    require(root.is_dir(), "R4 evidence bundle is missing")
    verification = read_json(safe_file(root, "verification.json"))
    lock_path = safe_file(root, "release-lock.json")
    lock = read_json(lock_path)
    require(verification.get("schema_version") == 1 and lock.get("schema_version") == 1,
            "Unrecognized verification or release-lock schema")
    require(verification.get("version") == VERSION and lock.get("version") == VERSION,
            "Release evidence version mismatch")
    require(verification.get("source_sha") == source_sha and lock.get("source_sha") == source_sha,
            "Release evidence does not match the approved main source")
    require(verification.get("r4_run_id") == r4_id and lock.get("r4_run_id") == r4_id,
            "R4 identity mismatch in evidence or release lock")
    require(isinstance(lock.get("r3_run_id"), int) and lock["r3_run_id"] > 0
            and verification.get("r3_run_id") == lock["r3_run_id"],
            "Missing or mismatched R3 candidate build run identity")
    require(verification.get("decision") == "pass"
            and verification.get("security_policy_result") == "pass"
            and verification.get("no_rebuild_integration") == "passed",
            "R4 security policy or no-rebuild integration is not approved")
    require(isinstance(verification.get("security_policy_version"), str)
            and verification["security_policy_version"].strip(),
            "Missing shared vulnerability-policy version")
    require(verification.get("high_critical_unaccepted") == 0,
            "Unaccepted high/critical vulnerability findings")
    require(isinstance(lock.get("compose_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", lock["compose_sha256"]) is not None,
            "Invalid Compose SHA-256")
    rollback = lock.get("rollback")
    require(isinstance(rollback, dict) and rollback.get("verified") is True
            and valid_digest("sha256:" + str(rollback.get("lock_sha256", ""))),
            "Missing verified rollback artifact identity")
    exceptions = verification.get("exceptions", [])
    require(isinstance(exceptions, list), "Invalid exception records")
    now = dt.datetime.now(dt.timezone.utc)
    for item in exceptions:
        require(isinstance(item, dict) and item.get("approved_by") and item.get("issue"),
                "Security exception lacks independent approval or tracked issue")
        try:
            expires = dt.datetime.fromisoformat(str(item["expires_at"]).replace("Z", "+00:00"))
            require(expires.tzinfo is not None and expires > now, "Expired security exception")
        except (TypeError, KeyError, ValueError) as error:
            raise ReleaseBlocked("Invalid or expired security exception") from error

    image_list = lock.get("images")
    require(isinstance(image_list, list) and image_list, "Release lock has no images")
    seen, components = set(), {}
    for image in image_list:
        require(isinstance(image, dict), "Invalid image lock entry")
        component = image.get("component")
        name, digest = image.get("name"), image.get("digest")
        require(isinstance(name, str) and name and valid_digest(digest), "Missing immutable image")
        require((name, digest) not in seen, "Duplicate image in release lock")
        seen.add((name, digest))
        require(image.get("platform") == "linux/amd64", "Unapproved image architecture")
        require(image.get("security_decision") == "pass", "Image security decision not approved")
        if image.get("kind") == "first-party":
            require(component in FIRST_PARTY and name == FIRST_PARTY[component],
                    "Unexpected first-party image")
            require(component not in components, "Duplicate first-party component")
            require(image.get("source_sha") == source_sha
                    and image.get("candidate_tag") == "sha-" + source_sha,
                    "First-party image has wrong SHA identity")
            require(all(isinstance(image.get(key), str) and image[key]
                        for key in ("sbom", "provenance", "vulnerability_report")),
                    "First-party SBOM/provenance/Trivy reports missing")
            components[component] = image
        elif image.get("kind") == "upstream":
            require(image.get("approved_upstream") is True,
                    "Upstream image was not independently reviewed")
        else:
            raise ReleaseBlocked("Unknown image kind")
    require(set(components) == set(FIRST_PARTY), "Missing a first-party container")
    require(lock.get("music_worker_digest") == components["music"]["digest"],
            "Music worker and web must share exactly one image digest")
    require(isinstance(lock.get("profiles"), list) and lock["profiles"],
            "Selected Compose profiles missing from lock")

    files = verification.get("files")
    require(isinstance(files, dict) and files, "R4 checksum manifest absent")
    needed = {"release-lock.json", "release-notes.md"}
    for image in components.values():
        needed.update(image[key] for key in ("sbom", "provenance", "vulnerability_report"))
    require(needed.issubset(files), "Release evidence is missing required files")
    require("verification.json" not in files, "Self-referential evidence checksum")
    for item in root.rglob("*"):
        require(not item.is_symlink(), "Evidence bundle contains a symlink")
    for path, checksum in files.items():
        require(path in ("release-lock.json", "release-notes.md")
                or (isinstance(path, str) and re.fullmatch(
                    r"(?:sboms|provenance|reports|integration)/[A-Za-z0-9_.-]+\\.json",
                    path) is not None),
                "Unexpected or potentially sensitive release evidence path")
        require(isinstance(checksum, str)
                and re.fullmatch(r"[0-9a-f]{64}", checksum) is not None,
                "Invalid evidence checksum: " + str(path))
        require(hash_file(safe_file(root, path)) == checksum,
                "Evidence checksum mismatch: " + str(path))
    actual_files = {str(x.relative_to(root)) for x in root.rglob("*") if x.is_file()}
    require(actual_files == set(files) | {"verification.json"},
            "Unexpected or missing evidence bundle files")
    lock_sha = hash_file(lock_path)
    validate_notes(safe_file(root, "release-notes.md").read_text(encoding="utf-8"),
                   source_sha, lock_sha, image_list)
    return {"lock_sha256": lock_sha, "lock": lock, "verification": verification}


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


def api(path: str, *, missing_ok: bool = False) -> dict | list | None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
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
    branch = api("repos/" + REPOSITORY + "/branches/main")
    require(branch["commit"]["sha"] == source_sha, "main advanced since approval")
    checks = api("repos/" + REPOSITORY +
                 "/commits/" + source_sha + "/check-runs?filter=latest&per_page=100")
    require(isinstance(checks, dict) and checks.get("total_count", 0) <= 100,
            "Cannot attest to complete check history")
    validate_checks(checks, source_sha)
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
    parser.add_argument("command", choices=("live", "bundle", "registry", "assets", "approval", "published"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--r4-run-id", required=True, type=int)
    parser.add_argument("--evidence-dir", type=Path, default=Path("release-evidence"))
    parser.add_argument("--assets-dir", type=Path, default=Path("release-assets"))
    parser.add_argument("--approval-issue", type=int, default=0)
    args = parser.parse_args()
    try:
        require(valid_sha(args.source_sha) and args.r4_run_id > 0,
                "Invalid source commit or R4 run ID")
        if args.command == "published":
            check_published(args.source_sha, args.evidence_dir, args.r4_run_id)
        elif args.command in ("live", "approval"):
            summary = None
            if args.command == "approval":
                summary = validate_bundle(args.evidence_dir, args.source_sha, args.r4_run_id)
            live_check(args.source_sha, args.r4_run_id,
                       approval_issue=args.approval_issue,
                       lock_sha=summary["lock_sha256"] if summary else "",
                       require_approval=args.command == "approval")
        elif args.command in ("bundle", "registry", "assets"):
            summary = validate_bundle(args.evidence_dir, args.source_sha, args.r4_run_id)
            if args.command == "registry":
                verify_registry(summary["lock"], args.source_sha)
            elif args.command == "assets":
                stage_assets(args.evidence_dir, args.assets_dir)
        print("R5 " + args.command + " checks passed")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("R5 BLOCKED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
