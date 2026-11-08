"""Offline tests for fail-closed post-merge R3 GitHub status verification."""
import pytest
from scripts.verify_publisher_checks import RequiredChecksError, REQUIRED, verify_checks

SHA = "a" * 40

def sample():
    return {
        "total_count": len(REQUIRED),
        "check_runs": [
            {"id": i + 1, "name": name, "head_sha": SHA,
             "status": "completed", "conclusion": "success"}
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
        })
        data["total_count"] += 1
    with pytest.raises(RequiredChecksError):
        verify_checks(data, SHA)

def test_reject_invalid_sha_and_empty_api():
    with pytest.raises(RequiredChecksError):
        verify_checks(sample(), "not a SHA")
    with pytest.raises(RequiredChecksError):
        verify_checks({}, SHA)
