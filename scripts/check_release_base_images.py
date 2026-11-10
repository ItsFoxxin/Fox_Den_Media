"""Reject mutable/unreviewed Python base image references before any GHCR write."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

# This release uses one independently reviewed linux/amd64 Python base digest
# for all first-party containers; the exact digest is committed in Dockerfiles.
BASE = re.compile(r"FROM python:3\.12\.15-slim-bookworm@sha256:([0-9a-f]{64})(?:\s+AS\s+[A-Za-z][A-Za-z0-9_-]*)?\Z", re.I)
DOCKERFILES = (
    "apps/portal/Dockerfile",
    "apps/music/backend/Dockerfile",
    "apps/media/Dockerfile",
)

class BaseImageError(ValueError):
    pass

def verify_base_images(root: Path) -> str:
    pinned = []
    for path in DOCKERFILES:
        text = (root / path).read_text(encoding="utf-8")
        instructions = [
            line.strip() for line in text.splitlines()
            if line.lstrip().upper().startswith("FROM ")
        ]
        if len(instructions) != 1:
            raise BaseImageError(f"{path}: exactly one reviewed FROM required")
        match = BASE.fullmatch(instructions[0])
        if match is None:
            raise BaseImageError(f"{path}: Python base must be immutable digest pinned")
        pinned.append(match.group(1))
    if len(set(pinned)) != 1:
        raise BaseImageError("All three first-party Dockerfiles must share reviewed Python base digest")
    return pinned[0]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        digest = verify_base_images(args.root)
    except (OSError, BaseImageError) as error:
        parser.exit(1, f"R3 base image preflight blocked: {error}\n")
    print(f"R3 source base-image digest is pinned: sha256:{digest}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
