"""Read-only R1 release metadata and exact main commit validation."""
from __future__ import annotations
import argparse
from pathlib import Path
import re

SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")

class ReleaseMetadataError(ValueError):
    pass

def validate_metadata(root: Path, source_sha: str, main_head: str, target: str = "1.0.0") -> None:
    if not SHA_RE.fullmatch(source_sha) or not SHA_RE.fullmatch(main_head):
        raise ReleaseMetadataError("Source/main SHA must each be 40 lowercase hex characters")
    if source_sha != main_head:
        raise ReleaseMetadataError("Approved source SHA does not match main HEAD")
    if not VERSION_RE.fullmatch(target):
        raise ReleaseMetadataError("Invalid release SemVer")
    if (root / "VERSION").read_text().strip() != target:
        raise ReleaseMetadataError("Root VERSION mismatch")
    if (root / "apps/media/VERSION").read_text().strip() != target:
        raise ReleaseMetadataError("Media VERSION mismatch")
    if f"**{target}**" not in (root / "README.md").read_text():
        raise ReleaseMetadataError("README version mismatch")
    changelog = (root / "CHANGELOG.md").read_text()
    sections = re.findall(r"^## ([0-9]+\.[0-9]+\.[0-9]+) - [0-9]{4}-[0-9]{2}-[0-9]{2}$", changelog, re.M)
    if sections.count(target) != 1:
        raise ReleaseMetadataError("Expected exactly one dated target changelog section")
    if f"fox-den-media:{target}" not in (root / "deploy/compose.yaml").read_text():
        raise ReleaseMetadataError("Compose version mismatch")
    if "COPY apps/media/VERSION ./VERSION" not in (root / "apps/media/Dockerfile").read_text():
        raise ReleaseMetadataError("Media Dockerfile must embed VERSION")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        validate_metadata(args.root, args.source_sha, args.main_head, args.version)
    except (OSError, ReleaseMetadataError) as exc:
        parser.exit(1, f"R1 rejected: {exc}\n")
    print(f"R1 metadata valid: {args.version} {args.source_sha}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
