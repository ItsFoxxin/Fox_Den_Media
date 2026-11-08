"""R2 offline digest-lock structural and no-build Compose verifier.

R4 must separately verify actual registry manifests, provenance, shared scan
contract and no-rebuild integration; this validator does not authorize a release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
REF = re.compile(r"([a-z0-9./_-]+)@sha256:([0-9a-f]{64})\Z")
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
SERVICE_IMAGE = {
    "ingress": "nginx", "portal": "portal", "music": "music",
    "music-worker": "music", "media": "media", "download-browser": "browser",
    "jellyfin": "jellyfin", "gluetun": "gluetun", "qbittorrent": "qbittorrent",
}
PROFILE_SERVICES = {
    "music": {"music", "music-worker"}, "media": {"media"},
    "browser": {"download-browser"}, "jellyfin": {"jellyfin"},
    "managed": {"gluetun", "qbittorrent"},
}
ROOT_KEYS = {"schema_version", "version", "source_sha", "compose_sha256",
             "platform", "profiles", "images", "services", "rollback", "publisher"}
IMAGE_KEYS = {"ref", "platform", "platform_digest", "source_sha"}

class ReleaseLockError(ValueError):
    pass

def ensure(ok: bool, error: str) -> None:
    if not ok:
        raise ReleaseLockError(error)

def selected_services(profiles: set[str]) -> set[str]:
    result = {"ingress", "portal"}
    for profile, services in PROFILE_SERVICES.items():
        if profile in profiles:
            result.update(services)
    return result

def validate_lock(data: dict, *, compose: bytes | None = None,
                  rendered: dict | None = None,
                  expected_source: str | None = None) -> None:
    ensure(type(data) is dict and set(data) == ROOT_KEYS, "Missing/unexpected lock keys")
    ensure(type(data["schema_version"]) is int and data["schema_version"] == 1, "Unknown schema")
    ensure(type(data["version"]) is str and bool(VERSION.fullmatch(data["version"])), "Invalid version")
    source = data["source_sha"]
    ensure(type(source) is str and bool(SHA.fullmatch(source)), "Invalid source SHA")
    if expected_source is not None:
        ensure(source == expected_source, "Wrong approved source SHA")
    ensure(type(data["compose_sha256"]) is str and bool(HASH.fullmatch(data["compose_sha256"])), "Invalid Compose hash")
    if compose is not None:
        ensure(hashlib.sha256(compose).hexdigest() == data["compose_sha256"], "Compose hash mismatch")
    ensure(data["platform"] == "linux/amd64", "Unverified image architecture")
    profiles = data["profiles"]
    ensure(type(profiles) is list and all(type(p) is str for p in profiles), "Bad profiles")
    active = set(profiles)
    ensure(len(active) == len(profiles) and active <= set(PROFILE_SERVICES), "Duplicate/unknown profile")
    ensure("browser" not in active or "music" in active, "Browser requires Music profile")
    services = selected_services(active)
    mapping = data["services"]
    ensure(type(mapping) is dict and set(mapping) == services, "Missing/unexpected service or profile")
    ensure(all(mapping[service] == SERVICE_IMAGE[service] for service in services), "Wrong service-image mapping")
    images = data["images"]
    used = set(mapping.values())
    ensure(type(images) is dict and set(images) == used, "Missing/unused image")
    for name, value in images.items():
        ensure(type(value) is dict and set(value) == IMAGE_KEYS, f"Unknown/missing image fields: {name}")
        ref = value["ref"]
        matched = REF.fullmatch(ref) if type(ref) is str else None
        ensure(matched is not None, f"Mutable or invalid image reference: {name}")
        ensure(matched.group(1) == {**FIRST_PARTY, **UPSTREAM}[name], f"Wrong image source: {name}")
        ensure(value["platform"] == data["platform"], f"Wrong architecture: {name}")
        ensure(type(value["platform_digest"]) is str and bool(HASH.fullmatch(value["platform_digest"])),
               f"Invalid platform digest: {name}")
        if name in FIRST_PARTY:
            ensure(value["source_sha"] == source, f"Wrong first-party source SHA: {name}")
        else:
            ensure(value["source_sha"] is None, f"Upstream image impersonates source: {name}")
    publisher = data["publisher"]
    ensure(type(publisher) is dict and set(publisher) == {"workflow", "run_id", "source_sha"},
           "Missing/extra publisher fields")
    ensure(publisher["workflow"] == "ghcr-candidates.yml" and
           type(publisher["run_id"]) is int and publisher["run_id"] > 0 and
           publisher["source_sha"] == source, "Untrusted publisher identity")
    rollback = data["rollback"]
    ensure(type(rollback) is dict and set(rollback) == {"version", "lock_sha256"},
           "Missing rollback identity")
    ensure(type(rollback["version"]) is str and bool(VERSION.fullmatch(rollback["version"])) and
           type(rollback["lock_sha256"]) is str and bool(HASH.fullmatch(rollback["lock_sha256"])),
           "Invalid rollback identity")
    if rendered is not None:
        ensure(type(rendered) is dict and type(rendered.get("services")) is dict,
               "Invalid rendered Compose")
        config = rendered["services"]
        ensure(set(config) == services, "Rendered profiles/services mismatch")
        for service, image_key in mapping.items():
            image_cfg = config[service]
            ensure(type(image_cfg) is dict and "build" not in image_cfg,
                   f"Untrusted rebuild configured: {service}")
            ensure(image_cfg.get("image") == images[image_key]["ref"],
                   f"Rendered image digest mismatch: {service}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--compose", type=Path)
    parser.add_argument("--rendered", type=Path, help="Private build-free Compose config JSON")
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    try:
        data = json.loads(args.lock.read_text())
        rendered = json.loads(args.rendered.read_text()) if args.rendered else None
        validate_lock(data, compose=args.compose.read_bytes() if args.compose else None,
                      rendered=rendered, expected_source=args.source_sha)
    except (ReleaseLockError, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"R2 rejected: {exc}\n")
    print(f"R2 lock structurally valid: {data['version']} {data['source_sha']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
