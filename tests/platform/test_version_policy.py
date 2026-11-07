"""Prospective one-bug-per-patch release rules."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_version_policy import (
    VersionPolicyError,
    changelog_entry,
    parse_version,
    patch_bug_issue,
    read_pr_event,
    release_kind,
    validate_policy,
)

CHANGELOG = """# Changelog

## 1.2.4 - 2026-11-07

### Fixed

- Fixes #42: Prevent accidental ingress configuration replacement.

### Tests

- Added regression tests for read-only deployment preflights.

## 1.2.3 - 2026-11-06

### Fixed

- Old release entry intentionally not part of the new policy.
"""


def test_version_parsing_rejects_non_semver():
    assert parse_version("1.2.3") == (1, 2, 3)
    for value in ("v1.2.3", "1.02.3", "1.2", "1.2.3.4", "01.0.0", "-1.2.3"):
        with pytest.raises(VersionPolicyError):
            parse_version(value)


@pytest.mark.parametrize(("old", "new", "kind"), [
    ("0.9.2", "1.0.0", "major"),
    ("1.2.3", "2.0.0", "major"),
    ("1.2.3", "1.3.0", "minor"),
    ("0.9.2", "0.10.0", "minor"),
    ("1.2.3", "1.2.4", "patch"),
    ("1.2.3", "1.2.3", "unchanged"),
])
def test_single_component_increments(old, new, kind):
    assert release_kind(old, new) == kind


@pytest.mark.parametrize(("old", "new"), [
    ("1.2.3", "1.2.5"),
    ("1.2.3", "1.4.0"),
    ("1.2.3", "3.0.0"),
    ("1.2.3", "1.3.1"),
    ("1.2.3", "2.1.0"),
    ("1.2.3", "1.2.2"),
    ("1.2.3", "1.2.0"),
])
def test_skipped_or_combined_bumps_are_rejected(old, new):
    with pytest.raises(VersionPolicyError, match="Invalid version step"):
        release_kind(old, new)


def test_patch_must_link_one_bug_in_pr_and_dated_changelog():
    assert patch_bug_issue(CHANGELOG, "1.2.4") == 42
    assert validate_policy(
        "1.2.3", "1.2.4", CHANGELOG,
        pr_title="fix(ingress): stop overwriting nginx.conf",
        pr_body="Fixes #42",
    ) == "patch"


def test_bugfix_without_patch_is_rejected():
    with pytest.raises(VersionPolicyError, match="Bug-fix pull requests"):
        validate_policy(
            "1.2.3", "1.2.3", CHANGELOG,
            pr_title="fix(ingress): stop overwriting nginx.conf",
            pr_body="Fixes #42",
        )
    with pytest.raises(VersionPolicyError, match="Bug-fix pull requests"):
        validate_policy(
            "1.2.3", "1.3.0", CHANGELOG,
            pr_title="misc cleanup", pr_labels=("bug",),
        )


def test_nonrelease_docs_and_feature_prep_are_allowed():
    assert validate_policy(
        "0.9.2", "0.9.2", CHANGELOG,
        pr_title="docs: describe versioning and issues",
    ) == "unchanged"


def test_release_must_have_dated_changelog_entry():
    with pytest.raises(VersionPolicyError, match="exactly one dated"):
        validate_policy("1.2.3", "1.3.0", CHANGELOG, pr_title="feat: discovery")


def test_patch_wrong_issue_or_many_issues_are_rejected():
    for body in ("", "Fixes #43", "Fixes #42\nCloses #43"):
        with pytest.raises(VersionPolicyError, match="reference only"):
            validate_policy(
                "1.2.3", "1.2.4", CHANGELOG,
                pr_title="fix: ingress", pr_body=body,
            )


def test_pr_template_html_comment_examples_not_counted():
    assert validate_policy(
        "1.2.3", "1.2.4", CHANGELOG,
        pr_title="fix: ingress",
        pr_body="<!-- Fixes #123 -->\nFixes #42",
    ) == "patch"


def test_patch_rejects_multiple_fixed_bullets():
    multi = CHANGELOG.replace(
        "- Fixes #42: Prevent accidental ingress configuration replacement.",
        "- Fixes #42: Prevent accidental ingress configuration replacement.\n"
        "- Also fix an unrelated path traversal bug.",
    )
    with pytest.raises(VersionPolicyError, match="one '- Fixes"):
        patch_bug_issue(multi, "1.2.4")


def test_patch_rejects_two_linked_bug_issues():
    multi = CHANGELOG.replace(
        "- Fixes #42: Prevent accidental ingress configuration replacement.",
        "- Fixes #42: Prevent accidental ingress configuration replacement.\n"
        "Also closes #44.",
    )
    with pytest.raises(VersionPolicyError, match="reference no other"):
        patch_bug_issue(multi, "1.2.4")


def test_patch_ignores_issue_references_in_prior_releases():
    old_ref = CHANGELOG.replace(
        "- Old release entry intentionally not part of the new policy.",
        "- Fixes #999: Historical bug fix.",
    )
    assert patch_bug_issue(old_ref, "1.2.4") == 42


def test_duplicate_changelog_release_heading_is_rejected():
    with pytest.raises(VersionPolicyError, match="exactly one dated"):
        changelog_entry(CHANGELOG + "\n## 1.2.4 - 2026-11-08\n", "1.2.4")


def test_loads_event_metadata_and_labels(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({
        "pull_request": {
            "title": "fix(ingress): safe regeneration",
            "body": "Fixes #42",
            "labels": [{"name": "bug"}, {"name": "area: ingress"}],
        }
    }), encoding="utf-8")
    assert read_pr_event(event) == (
        "fix(ingress): safe regeneration",
        "Fixes #42",
        ("bug", "area: ingress"),
    )
