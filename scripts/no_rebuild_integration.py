"""Disposable integration against published digest images, never Docker builds.

This runs on a GitHub-hosted runner with synthetic state. It is not NAS
acceptance, production deployment, or a substitute for real client checks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import urllib.request

from scripts.integration_stack import ROOT, RUNTIME, COMPOSE, run, write_private_text

def shell(*cmd, env=None):
    return subprocess.check_output(cmd, cwd=ROOT, env=env, text=True).strip()

def render_no_build(config: dict, images: dict) -> dict:
    services = config.get("services")
    if not isinstance(services, dict):
        raise ValueError("Bad rendered Compose services")
    expected = {"volume-init", "ingress", "portal", "music", "music-worker", "media"}
    if set(services) != expected:
        raise ValueError("Unexpected integration services")
    service_image = {
        "volume-init": "portal", "ingress": "nginx", "portal": "portal",
        "music": "music", "music-worker": "music", "media": "media",
    }
    for service, name in service_image.items():
        if name not in images:
            raise ValueError("Required image absent from verified lock: " + name)
        entry = services[service]
        entry.pop("build", None)
        entry["image"] = images[name]["ref"]
    if services["music"]["image"] != services["music-worker"]["image"]:
        raise ValueError("Music web/worker digest mismatch")
    if any("build" in record for record in services.values()):
        raise ValueError("Source build directive survived")
    return config

def prepare(portal_ref: str, port: int) -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    RUNTIME.chmod(0o700)
    if any(RUNTIME.iterdir()):
        raise RuntimeError("Integration runtime already exists; refuse to overwrite state")
    # Use the actual pulled Portal digest for all key-generation/ownership
    # commands; never build or tag a local replacement.
    run("docker", "run", "--rm", "--user", "0",
        "-v", f"{RUNTIME.resolve()}:/keys", portal_ref,
        "foxden-identity-keygen", "--private", "/keys/private.pem",
        "--public", "/keys/public.json", "--kid", "integration-1")
    ingress_secret = secrets.token_urlsafe(48)
    write_private_text(RUNTIME / "ingress-auth", ingress_secret)
    template = (ROOT / "infra/gateway/portal-ingress.conf").read_text()
    write_private_text(RUNTIME / "portal-ingress.conf",
                       template.replace("__PORTAL_INGRESS_AUTH_SECRET__", ingress_secret))
    for uid_gid, path in [("101:101", "portal-ingress.conf"),
                         ("10001:10001", "private.pem"), ("10001:10001", "ingress-auth")]:
        run("docker", "run", "--rm", "--user", "0",
            "-v", f"{RUNTIME.resolve()}:/keys", portal_ref,
            "chown", uid_gid, "/keys/" + path)
    env = RUNTIME / "integration.env"
    values = {
        "MUSIC_SOURCE_PATH": (ROOT / "apps/music").resolve().as_posix(),
        "INTEGRATION_PORT": str(port),
        "INTEGRATION_PUBLIC_ORIGIN": f"http://127.0.0.1:{port}",
        "INTEGRATION_PORTAL_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_BOOTSTRAP_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_CSRF_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_MEDIA_TOKEN": secrets.token_urlsafe(48),
    }
    write_private_text(env, "".join(f"{k}={v}\n" for k, v in values.items()))
    return env

def exercise(lock: dict, port: int) -> None:
    images = lock["images"]
    for name in ("portal", "music", "media", "nginx"):
        if name not in images:
            raise ValueError("Missing required locked integration image: " + name)
        shell("docker", "pull", "--platform", "linux/amd64", images[name]["ref"])
    env = prepare(images["portal"]["ref"], port)
    with tempfile.TemporaryDirectory(prefix="foxden-r4-") as directory:
        rendered = Path(directory) / "integration.json"
        try:
            raw = shell("docker", "compose", "--env-file", str(env),
                        "-f", str(COMPOSE), "config", "--format", "json")
            cfg = render_no_build(json.loads(raw), images)
            rendered.write_text(json.dumps(cfg), encoding="utf-8")
            shell("docker", "compose", "-f", str(rendered),
                  "config", "--quiet")
            shell("docker", "compose", "-f", str(rendered),
                  "up", "-d", "--no-build", "--wait", "--wait-timeout", "120")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
                if response.status >= 400:
                    raise RuntimeError("Ingress/Portal smoke request failed")
            # A real HTTP path through ingress proves the published containers
            # are interacting, not merely that each image can be imported.
            for service in ("portal", "music", "music-worker", "media"):
                result = shell("docker", "compose", "-f", str(rendered),
                               "ps", "--status", "running", "--services")
                if service not in result.splitlines():
                    raise RuntimeError("Integration service not running: " + service)
        finally:
            subprocess.run(["docker", "compose", "-f", str(rendered),
                            "down", "--volumes", "--remove-orphans"],
                           cwd=ROOT, check=False)
            # Do not log generated private environment or keys.
            from shutil import rmtree
            rmtree(RUNTIME, ignore_errors=True)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--report", type=Path, help="Write source/digest-bound proof ONLY after successful pull integration")
    parser.add_argument("--source-sha", help="Exact approved source for report subject")
    parser.add_argument("--r4-run-id", type=int, help="Actual R4 signer run ID")
    args = parser.parse_args()
    if args.report is not None and (
        not args.source_sha or re.fullmatch(r"[0-9a-f]{40}", args.source_sha) is None
        or not args.r4_run_id or args.r4_run_id < 1
    ):
        parser.error("An integration proof requires an exact source SHA and R4 run ID")
    if RUNTIME.exists() and any(RUNTIME.iterdir()):
        parser.error("Existing integration runtime would be overwritten")
    lock_bytes = args.lock.read_bytes()
    lock = json.loads(lock_bytes)
    exercise(lock, args.port)
    # A receipt is emitted only when the pulled-digest integration returned
    # successfully. A fixture, skipped job, or error cannot create a pass.
    if args.report is not None:
        if args.report.exists():
            parser.error("Refuse to overwrite an existing integration proof")
        payload = {
            "schema_version": 1, "source_sha": args.source_sha,
            "r4_run_id": args.r4_run_id,
            "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "decision": "pass", "mode": "pulled-digest-no-build",
            "images": {name: image["ref"] for name, image in lock["images"].items()},
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    print("R4 published-image no-rebuild synthetic integration passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
