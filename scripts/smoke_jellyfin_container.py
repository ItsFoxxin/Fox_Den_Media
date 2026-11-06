#!/usr/bin/env python3
"""Start the official Jellyfin image with disposable state and no NAS mounts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid


IMAGE = os.getenv("JELLYFIN_SMOKE_IMAGE", "jellyfin/jellyfin:12.4")


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, text=True, capture_output=True)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    name = f"foxden-jellyfin-{suffix}"
    root = Path(tempfile.mkdtemp(prefix="foxden-jellyfin-smoke-"))
    config = root / "config"
    cache = root / "cache"
    media = root / "media"
    try:
        for directory in (config, cache, media):
            directory.mkdir()
        (media / "README.txt").write_text("Synthetic CI media root; contains no production data.\n", encoding="utf-8")
        uid = str(os.getuid()) if hasattr(os, "getuid") else "10001"
        gid = str(os.getgid()) if hasattr(os, "getgid") else "10001"
        result = docker(
            "run", "-d", "--name", name, "--network", "none", "--read-only",
            "--user", f"{uid}:{gid}", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
            "-v", f"{config.resolve()}:/config", "-v", f"{cache.resolve()}:/cache",
            "-v", f"{media.resolve()}:/media:ro", IMAGE,
        )
        print(f"Started {IMAGE}: {result.stdout.strip()[:12]}")
        health = None
        for _ in range(180):
            state = json.loads(docker("inspect", name).stdout)[0]["State"]
            if not state["Running"]:
                raise RuntimeError("Jellyfin exited:\n" + docker("logs", name).stdout[-4000:])
            health = docker(
                "exec", name, "curl", "--noproxy", "localhost", "-fsS",
                "http://localhost:8096/health", check=False,
            )
            if health.returncode == 0 and health.stdout.strip().lower() == "healthy":
                break
            time.sleep(1)
        else:
            last_health = health.stdout.strip() if health else "unreachable"
            raise RuntimeError(
                f"Jellyfin did not become ready (last health: {last_health!r}):\n"
                + docker("logs", name).stdout[-4000:]
            )
        assert docker("exec", name, "id", "-u").stdout.strip() == uid
        web = docker("exec", name, "curl", "--noproxy", "localhost", "-LfsS", "http://localhost:8096/web/index.html")
        assert "jellyfin" in web.stdout.lower()
        print("Official Jellyfin image passed non-root, read-only, health, and web-client smoke checks.")
    finally:
        logs = docker("logs", "--tail", "80", name, check=False)
        print(logs.stdout, logs.stderr)
        docker("rm", "-f", name, check=False)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
