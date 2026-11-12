"""Offline tests for fail-closed post-merge R3 GitHub status verification."""
import pytest
from scripts.verify_publisher_checks import RequiredChecksError, REQUIRED, verify_checks

SHA = "a" * 40
EXPECTED_APPS = {
    "Monorepo strict gate": 15368,
    "CodeQL (python)": 15368,
    "CodeQL (javascript-typescript)": 15368,
    "CodeQL": 57789,
}

def sample():
    return {
        "total_count": len(REQUIRED),
        "check_runs": [
            {"id": i + 1, "name": name, "head_sha": SHA,
             "status": "completed", "conclusion": "success",
             "app": {"id": EXPECTED_APPS.get(name, 15368)}}
            for i, name in enumerate(sorted(REQUIRED))
        ],
    }

def test_require_exact_successful_post_merge_checks():
    verify_checks(sample(), SHA)

@pytest.mark.parametrize("change", ["missing", "failed", "skipped", "pending",
                                     "wrong-sha", "truncated", "stale-green"])
def test_fail_closed_on_bad_required_results(change):
    data = sample()
    if change == "missing":
        data["check_runs"].pop()
    elif change == "failed":
        data["check_runs"][0]["conclusion"] = "failure"
    elif change == "skipped":
        data["check_runs"][0]["conclusion"] = "skipped"
    elif change == "pending":
        data["check_runs"][0]["status"] = "in_progress"
        data["check_runs"][0]["conclusion"] = None
    elif change == "wrong-sha":
        data["check_runs"][0]["head_sha"] = "f" * 40
    elif change == "truncated":
        data["total_count"] += 1
    else:
        data["check_runs"].append({
            "id": 999, "name": data["check_runs"][0]["name"],
            "head_sha": SHA, "status": "completed", "conclusion": "failure",
            "app": {"id": EXPECTED_APPS[data["check_runs"][0]["name"]]},
        })
        data["total_count"] += 1
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)

def test_reject_invalid_sha_and_empty_api():
    with pytest.raises(RequiredChecksError):
        verify_checks(sample(), "not a SHA")
    with pytest.raises(RequiredChecksError):
        verify_checks({}, SHA)


def test_all_four_protected_main_ruleset_contexts_and_apps():
    assert set(REQUIRED) == set(EXPECTED_APPS)
    assert len(sample()["check_runs"]) == 4
    verify_checks(sample(), SHA)


@pytest.mark.parametrize("name", sorted(EXPECTED_APPS))
def test_wrong_check_publisher_or_missing_app_must_be_rejected(name):
    data = sample()
    target = next(run for run in data["check_runs"] if run["name"] == name)
    target["app"] = {"id": 99999}
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)
    target.pop("app")
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)


def test_aggregate_codeql_is_required_even_with_both_languages_green():
    data = sample()
    data["check_runs"] = [run for run in data["check_runs"] if run["name"] != "CodeQL"]
    data["total_count"] = len(data["check_runs"])
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)


@pytest.mark.parametrize("bad_status", [
    ("completed", "failure"), ("completed", "skipped"),
    ("in_progress", None), ("queued", None),
])
def test_newer_check_overrides_stale_success_even_from_untrusted_app(bad_status):
    data = sample()
    previous = next(run for run in data["check_runs"]
                    if run["name"] == "Monorepo strict gate")
    data["check_runs"].append({
        **previous, "id": 999, "status": bad_status[0],
        "conclusion": bad_status[1], "app": {"id": 99999},
    })
    data["total_count"] = len(data["check_runs"])
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)


@pytest.mark.parametrize("malformed", ["missing-count", "invalid-count", "count-lower", "count-higher"])
def test_full_pagination_or_check_count_inconsistency_is_fatal(malformed):
    data = sample()
    if malformed == "missing-count":
        del data["total_count"]
    elif malformed == "invalid-count":
        data["total_count"] = True
    elif malformed == "count-lower":
        data["total_count"] -= 1
    else:
        data["total_count"] += 1
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)


def test_both_r3_check_gates_use_full_pagination_and_independent_validator():
    from pathlib import Path
    import yaml

    workflow = yaml.safe_load(Path(".github/workflows/ghcr-candidates.yml").read_text())
    scripts = [
        step["run"]
        for job in ("authorize", "publish")
        for step in workflow["jobs"][job]["steps"]
        if "run" in step and "scripts/verify_publisher_checks.py" in step["run"]
    ]
    assert len(scripts) == 2
    for script in scripts:
        assert "gh api --paginate --slurp" in script
        assert "filter=all" in script
        assert "scripts/verify_publisher_checks.py" in script
