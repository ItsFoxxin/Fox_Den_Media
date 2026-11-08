"""Require successful post-merge GitHub check-runs on exact approved main SHA."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REQUIRED = {"Monorepo strict gate", "CodeQL (python)", "CodeQL (javascript-typescript)"}

class RequiredChecksError(ValueError):
    pass

def verify_checks(payload: dict, source_sha: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise RequiredChecksError("Invalid source SHA")
    if type(payload) is not dict or type(payload.get("check_runs")) is not list:
        raise RequiredChecksError("Missing check-run API response")
    runs = payload["check_runs"]
    for name in REQUIRED:
        matching = [
            run for run in runs if type(run) is dict and
            run.get("name") == name and run.get("head_sha") == source_sha
        ]
        if not matching:
            raise RequiredChecksError(f"Missing required check on source SHA: {name}")
        newest = max(matching, key=lambda run: run.get("id", -1))
        if newest.get("status") != "completed" or newest.get("conclusion") != "success":
            raise RequiredChecksError(f"Required source check failed/incomplete: {name}")
    if payload.get("total_count", 0) > len(runs):
        # There may be more pages with newer duplicates. Fail instead of choosing
        # a potentially stale result from a truncated API page.
        raise RequiredChecksError("Checks API response truncated: cannot prove latest checks")

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_publisher_checks.py checks.json source_sha")
    try:
        verify_checks(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"R3 source checks rejected: {exc}") from exc
    print("R3 post-merge checks passed for exact main SHA")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
