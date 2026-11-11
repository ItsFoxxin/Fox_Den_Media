"""Verify every required protected-main check with exact GitHub App provenance.

The R3 workflow fetches *all* paginated GitHub check runs for the approved
source commit. The highest check-run ID for each required context must belong
to the ruleset's expected GitHub App and have completed successfully. An old
green result cannot conceal a newer failure or impersonated publisher.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

# Active protected-main ruleset 26667058; fail closed if this contract changes.
# 15368 = GitHub Actions; 57789 = GitHub CodeQL.
REQUIRED = {
    "Monorepo strict gate": 15368,
    "CodeQL (python)": 15368,
    "CodeQL (javascript-typescript)": 15368,
    "CodeQL": 57789,
}


class RequiredChecksError(ValueError):
    pass


def verify_checks(payload: dict, source_sha: str) -> None:
    if type(source_sha) is not str or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise RequiredChecksError("Invalid source SHA")
    if type(payload) is not dict or type(payload.get("check_runs")) is not list:
        raise RequiredChecksError("Missing check-run API response")
    runs = payload["check_runs"]
    count = payload.get("total_count")
    if type(count) is not int or count != len(runs):
        # GitHub check-runs API is paginated; accepting any subset could
        # allow a superseded successful check to hide a newer failure.
        raise RequiredChecksError("Checks API response truncated or inconsistent")
    seen_ids = set()
    newest = {}
    for run in runs:
        if type(run) is not dict:
            raise RequiredChecksError("Malformed check-run API record")
        ident = run.get("id")
        if type(ident) is not int or ident <= 0 or ident in seen_ids:
            raise RequiredChecksError("Missing, duplicate or malformed check-run ID")
        seen_ids.add(ident)
        name = run.get("name")
        if name not in REQUIRED:
            continue
        if run.get("head_sha") != source_sha:
            raise RequiredChecksError(f"Required check bound to wrong SHA: {name}")
        if name not in newest or ident > newest[name]["id"]:
            newest[name] = run
    for name, expected_app_id in REQUIRED.items():
        run = newest.get(name)
        if run is None:
            raise RequiredChecksError(f"Missing required check on source SHA: {name}")
        app = run.get("app")
        if type(app) is not dict or type(app.get("id")) is not int or (
                app["id"] != expected_app_id):
            raise RequiredChecksError(f"Untrusted required check publisher: {name}")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise RequiredChecksError(f"Required source check failed/incomplete: {name}")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_publisher_checks.py checks.json source_sha")
    try:
        verify_checks(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"R3 source checks rejected: {exc}") from exc
    print("R3 post-merge checks passed for exact main SHA and required GitHub Apps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
