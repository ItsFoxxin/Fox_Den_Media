#!/usr/bin/env python3
"""Enforce one-step SemVer releases and one tracked issue per patch.

This check is prospective: it compares the PR head against its target branch.
Already-recorded version history is not rewritten or retroactively rejected.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ENTRY_RE = re.compile(r"^## (?P<version>\d+\.\d+\.\d+) - \d{4}-\d{2}-\d{2}\s*$", re.M)
BUG_REFERENCE_RE = re.compile(r"\b(?:Fixes|Closes|Resolves|Refs)\s+#(\d+)\b", re.I)
PATCH_BULLET_RE = re.compile(r"^\s*-\s*(?:Fixes|Closes|Resolves)\s+#(\d+)\s*[:—-]\s*\S", re.I | re.M)
FIX_TITLE_RE = re.compile(r"^\s*(?:fix|bugfix|hotfix)(?:\([^)\r\n]+\))?!?:", re.I)
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


class VersionPolicyError(ValueError):
    """An unsafe or untracked release change was proposed."""


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value.strip())
    if match is None:
        raise VersionPolicyError(f"Invalid semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())


def release_kind(previous: str, proposed: str) -> str:
    """Accept exactly one SemVer component increment with normal resets."""
    before = parse_version(previous)
    after = parse_version(proposed)
    if after == before:
        return "unchanged"
    major, minor, patch = before
    if after == (major + 1, 0, 0):
        return "major"
    if after == (major, minor + 1, 0):
        return "minor"
    if after == (major, minor, patch + 1):
        return "patch"
    raise VersionPolicyError(
        f"Invalid version step {previous} -> {proposed}. "
        "Major: +1.0.0 (reset minor/patch); minor: +0.1.0 (reset patch); "
        "patch: +0.0.1. No skipped or combined releases."
    )


def changelog_entry(changelog: str, version: str) -> str:
    matches = list(ENTRY_RE.finditer(changelog))
    selected = [(index, match) for index, match in enumerate(matches)
                if match.group("version") == version]
    if len(selected) != 1:
        raise VersionPolicyError(f"CHANGELOG.md needs exactly one dated ## {version} entry")
    index, match = selected[0]
    end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
    return changelog[match.end():end]


def patch_bug_issue(changelog: str, version: str) -> int:
    entry = changelog_entry(changelog, version)
    fixed_section = re.search(r"^### Fixed[ \t]*\n([\s\S]*?)(?=^#{2,3} |\Z)", entry, re.M)
    if fixed_section is None:
        raise VersionPolicyError(f"Patch {version} requires a ### Fixed changelog section")
    # One canonical bullet identifies the single bug. Supporting details and
    # regression-test bullets are allowed, but no additional bug issues.
    bullets = PATCH_BULLET_RE.findall(fixed_section.group(1))
    all_fixed_bullets = re.findall(r"^[ \t]*-[ \t]+", fixed_section.group(1), re.M)
    refs = {int(number) for number in BUG_REFERENCE_RE.findall(entry)}
    if len(bullets) != 1 or len(all_fixed_bullets) != 1 or len(refs) != 1 or int(bullets[0]) not in refs:
        raise VersionPolicyError(
            f"Patch {version} must contain one '- Fixes #123: description' bullet "
            "and reference no other bug issue in its changelog entry."
        )
    return int(bullets[0])


def is_bugfix_pr(title: str, labels: Sequence[str]) -> bool:
    normalized_labels = {label.casefold().strip() for label in labels}
    return bool(FIX_TITLE_RE.match(title)) or bool(
        normalized_labels & {"bug", "type: bug", "bugfix", "hotfix"}
    )


def validate_policy(
    previous: str,
    proposed: str,
    changelog: str,
    *,
    pr_title: str = "",
    pr_body: str = "",
    pr_labels: Sequence[str] = (),
) -> str:
    """Check release metadata and a PR's fix intent without network calls."""
    kind = release_kind(previous, proposed)
    bugfix = is_bugfix_pr(pr_title, pr_labels)
    if bugfix and kind != "patch":
        raise VersionPolicyError(
            "Bug-fix pull requests must bump VERSION by exactly 0.0.1, "
            "be limited to one bug, and link that bug's GitHub issue."
        )
    if kind == "unchanged":
        return kind
    changelog_entry(changelog, proposed)
    if kind == "patch":
        issue = patch_bug_issue(changelog, proposed)
        if not pr_title:
            raise VersionPolicyError("Patch release requires pull-request tracking metadata")
        # Ignore placeholder examples inside the GitHub PR template's HTML comments.
        visible_pr_body = re.sub(r"<!--[\s\S]*?-->", "", pr_body)
        references = {int(number) for number in BUG_REFERENCE_RE.findall(visible_pr_body)}
        if references != {issue}:
            raise VersionPolicyError(
                f"Patch {proposed} must reference only its tracked bug issue "
                f"#{issue} in the PR body (for example: 'Fixes #{issue}')."
            )
    return kind


def read_pr_event(path: Path) -> tuple[str, str, tuple[str, ...]]:
    payload: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        raise VersionPolicyError("Expected a pull_request event payload")
    title = pr.get("title")
    body = pr.get("body")
    if not isinstance(title, str) or not title.strip():
        raise VersionPolicyError("Pull request title is required")
    labels = pr.get("labels") or []
    if not isinstance(labels, list):
        raise VersionPolicyError("Pull request labels must be a list")
    names = tuple(label["name"] for label in labels
                  if isinstance(label, dict) and isinstance(label.get("name"), str))
    return title, body if isinstance(body, str) else "", names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="SHA of the PR target branch")
    parser.add_argument("--pr-event", type=Path, required=True, help="GitHub pull_request event JSON")
    parser.add_argument("--issue-output", type=Path, help="Optional GitHub Actions output file")
    args = parser.parse_args()
    if not SHA_RE.fullmatch(args.base):
        parser.error("--base must be a Git commit SHA")
    root = Path(__file__).resolve().parent.parent
    try:
        previous = subprocess.check_output(
            ["git", "show", f"{args.base}:VERSION"], cwd=root, text=True
        ).strip()
        current = (root / "VERSION").read_text(encoding="utf-8").strip()
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        title, body, labels = read_pr_event(args.pr_event)
        kind = validate_policy(
            previous, current, changelog,
            pr_title=title, pr_body=body, pr_labels=labels,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Version policy violation: {exc}\n")
    if args.issue_output is not None:
        issue = patch_bug_issue(changelog, current) if kind == "patch" else None
        with args.issue_output.open("a", encoding="utf-8") as output:
            output.write(f"issue={issue if issue is not None else ''}\n")
    print(f"Version policy passed: {previous} -> {current} ({kind})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
