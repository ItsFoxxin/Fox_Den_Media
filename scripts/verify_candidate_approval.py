"""Require an explicit current owner GO for an exact R3 GHCR candidate source."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

class CandidateApprovalError(ValueError):
    pass

def validate_approval(issue: dict, comments: list, repo: str, issue_number: int, source_sha: str) -> None:
    if type(repo) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise CandidateApprovalError("Invalid repository")
    owner = repo.split("/")[0]
    if type(source_sha) is not str or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise CandidateApprovalError("Invalid source SHA")
    if type(issue_number) is not int or issue_number <= 0:
        raise CandidateApprovalError("Invalid approval issue")
    if (type(issue) is not dict or issue.get("number") != issue_number or
            issue.get("state") != "open" or issue.get("pull_request") is not None):
        raise CandidateApprovalError("Missing, closed or invalid approval issue")
    if type(comments) is not list:
        raise CandidateApprovalError("Missing owner approval comments")
    accepted = {f"GHCR-CANDIDATE-GO {source_sha}", f"GHCR-CANDIDATE-REVOKE {source_sha}"}
    directives = []
    for comment in comments:
        if type(comment) is not dict:
            raise CandidateApprovalError("Invalid comment record")
        user = comment.get("user")
        if (type(user) is not dict or user.get("login") != owner or
                comment.get("author_association") != "OWNER"):
            continue
        body = comment.get("body")
        if type(body) is not str or body.strip() not in accepted:
            continue
        when, ident = comment.get("created_at"), comment.get("id")
        if (type(when) is not str or
                not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", when) or
                type(ident) is not int or ident < 1):
            raise CandidateApprovalError("Invalid owner approval chronology")
        directives.append((when, ident, body.strip()))
    if not directives or max(directives)[2] != f"GHCR-CANDIDATE-GO {source_sha}":
        raise CandidateApprovalError("No current owner GHCR-CANDIDATE-GO on this source")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-json", type=Path, required=True)
    parser.add_argument("--comments-json", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        validate_approval(json.loads(args.issue_json.read_text()),
                          json.loads(args.comments_json.read_text()),
                          args.repository, args.issue_number, args.source_sha)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"R3 authorization denied: {exc}\n")
    print("R3 candidate owner GO verified for exact approved source SHA")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
