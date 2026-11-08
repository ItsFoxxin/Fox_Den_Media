"""Synthetic negative authorizations: no GitHub issue or GHCR mutation."""
import pytest
from scripts.verify_candidate_approval import CandidateApprovalError, validate_approval

SHA = "a" * 40
REPO = "ItsFoxxin/Fox_Den_Media"
ISSUE = {"number": 18, "state": "open"}

def owner(word="GO", sha=SHA, ident=1, who="ItsFoxxin", association="OWNER"):
    return {"id": ident, "created_at": f"2026-11-08T12:00:{ident:02d}Z",
            "user": {"login": who}, "author_association": association,
            "body": f"GHCR-CANDIDATE-{word} {sha}"}

def test_exact_owner_go_and_revocation():
    validate_approval(ISSUE, [owner()], REPO, 18, SHA)
    with pytest.raises(CandidateApprovalError):
        validate_approval(ISSUE, [owner(), owner("REVOKE", ident=2)], REPO, 18, SHA)
    validate_approval(ISSUE, [owner(), owner("REVOKE", ident=2),
                              owner(ident=3)], REPO, 18, SHA)

@pytest.mark.parametrize("issue, comments,sha", [
    ({"number":18,"state":"closed"}, [owner()], SHA),
    ({"number":19,"state":"open"}, [owner()], SHA),
    ({"number":18,"state":"open","pull_request":{}}, [owner()], SHA),
    (ISSUE, [], SHA),
    (ISSUE, [owner(who="attacker")], SHA),
    (ISSUE, [owner(association="COLLABORATOR")], SHA),
    (ISSUE, [owner(sha="b"*40)], SHA),
    (ISSUE, [owner()], "not-a-sha"),
    (ISSUE, [dict(owner(), body=f"GHCR-CANDIDATE-GO {SHA} extra")], SHA),
    (ISSUE, [dict(owner(), created_at="yesterday")], SHA),
    (ISSUE, [owner("REVOKE")], SHA),
])
def test_owner_approval_fails_closed(issue, comments, sha):
    with pytest.raises(CandidateApprovalError):
        validate_approval(issue, comments, REPO, 18, sha)
