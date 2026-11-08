"""Read-only R1 release metadata and exact main commit validation."""
from __future__ import annotations
import argparse
from datetime import date
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
    readme = (root / "README.md").read_text(encoding="utf-8")
    if not re.search(rf"(?m)^Current source milestone:\s+\*\*{re.escape(target)}\*\*(?:\.|\s|$)", readme):
        raise ReleaseMetadataError("README current source milestone mismatch")
    changelog = (root / "CHANGELOG.md").read_text()
    candidates = re.findall(rf"(?m)^##\s+{re.escape(target)}(?=\s|$).*?$", changelog)
    if len(candidates) != 1:
        raise ReleaseMetadataError("Expected exactly one target changelog section")
    dated = re.fullmatch(rf"## {re.escape(target)} - ([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})", candidates[0])
    if dated is None:
        raise ReleaseMetadataError("Target changelog heading must contain an ISO date")
    try:
        date.fromisoformat(dated.group(1))
    except ValueError as exc:
        raise ReleaseMetadataError("Invalid target changelog calendar date") from exc
    if f"MEDIA_IMAGE:-fox-den-media:{target}" not in (root / "deploy/compose.yaml").read_text():
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
