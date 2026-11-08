# CI container security contract and exception policy

**Release target:** 1.0.0. **Current mode:** advisory; not a release or deployment approval. Tracks #71 and complements #72/#74.

## Ownership and separation of concerns

- PR #72 builds and scans Portal, one shared Music image, and Movies/TV. PR #74 owns trusted PR baseline comparison, comments and labels. This addition reuses those same Trivy reports; it does not introduce a second image scanner or PR reporter.
- CodeQL, Bandit, pip-audit, native Dependency Review, Dependabot and secret-history scanning remain unchanged.
- The single canonical reviewed exception ledger is [security/vulnerability-exceptions.json](../security/vulnerability-exceptions.json), initially EMPTY. Do not add a competing .trivyignore file or broad ignore list.
- No workflow becomes a new required check. An unaccepted vulnerability produces a policy decision of fail, but the Trivy job remains advisory and returns success when the scan and report generation succeeded. Missing/malformed evidence is a real workflow failure.

## Evidence contract v1

Every existing per-image Trivy artifact gains security-contract.json with:

| Field | Meaning |
| --- | --- |
| schema_version, component | Schema version 1 and portal/music/media identity |
| source.commit, source.expected_commit | Scanned source SHA and caller's expected SHA |
| image.reference, image.local_config_id | Scanned image tag and Docker config digest, NOT an OCI manifest digest |
| image.manifest_digest, image.expected_manifest_digest | Exact published digest when available; both null in current CI |
| evidence.files | SHA-256 content hashes for JSON vulnerability report, CycloneDX SBOM, Trivy metadata and exception ledger |
| evidence.scanner_version, vulnerability_db_updated_at | Scanner and vulnerability database metadata |
| evidence.scan_run_url, attestation_references | Traceable links where supplied; NOT authenticated signatures by themselves |
| baseline.verified_by_caller, new, resolved, unchanged | Trusted provenance is caller's responsibility; deltas use Trivy's existing normalized finding keys |
| policy.decision, reasons, critical_high_unaccepted | Policy assessment and full unsuppressed CVE identities |
| policy.approved_exceptions, expired_exceptions | Time-limited exceptions and failures |
| policy.release_eligible | Always false in advisory. Only a future enforced passing contract can be true |

Do not confuse the Docker image config ID with a distributable manifest digest. A future GHCR publisher must independently verify artifact ownership, immutable digest, source ancestry, scanner and SBOM hash, upstream-image coverage, database freshness, and actual attestation signatures. The baseline-verified command-line flag is merely a caller assertion; do not treat a downloaded baseline or flag as GitHub provenance. The trusted PR reporter in #74 has separate protected-dev validation.

## Policy semantics

Unaccepted HIGH or CRITICAL results fail policy regardless of whether Trivy reports a fix. Existing findings in a baseline do not become exceptions simply because they are old. UNKNOWN severity needs review. Real upstream OS/base-image findings must be triaged like application packages.

Every exception needs an exact finding/CVE ID, image component, package ecosystem, name and installed version, responsible owner, approving reviewer, meaningful justification, a specific linked repository issue and an ISO calendar expiry date. The day of expiry is expired (fail closed); an expired ledger entry fails policy even if the finding disappears. Remove obsolete exceptions through normal reviewed source changes. Any image or package-version change requires re-review. Record final release risk acceptance with #18 and #71; no findings have been accepted by the initial empty ledger.

## Advisory versus enforcement

- Advisory: the current GitHub workflow writes policy.decision of pass, review_required or fail. High/critical findings do NOT fail the Trivy job; malformed JSON, wrong source/image, invalid SBOM, bad ledger, or scanner command failure DO fail the job.
- Enforce: a future caller can use --mode enforce, which exits nonzero on high/critical without valid exception; expired exception; unknown severity; absent independently verified baseline assertion; missing exact and expected OCI digest; mismatched expected source SHA; missing database date or DB age exceeding 14 days.
- The future caller MUST separately authenticate protected-dev baseline, GHCR manifests, scanner artifacts and attestations before setting --baseline-verified; this CLI does not contact GitHub and must not be used as a standalone release approval.

Use the same scan bundle for manual advisory verification:

~~~bash
python -m scripts.security_contract --component portal \
  --report reports/portal/vulnerabilities.json \
  --sbom reports/portal/sbom.cdx.json \
  --scanner-metadata reports/portal/trivy-version.json \
  --exceptions security/vulnerability-exceptions.json \
  --source-sha "$GITHUB_SHA" --expected-source-sha "$GITHUB_SHA" \
  --image-ref "foxden-ci-portal:$GITHUB_SHA" --image-id "$IMAGE_CONFIG_ID" \
  --mode advisory --output reports/portal/security-contract.json
~~~

## Negative testing and activation

Tests in tests/platform/test_security_contract.py cover unaccepted high/critical, clean scan, missing scan/DB metadata, invalid CycloneDX, incorrect image digest/config ID, stale source SHA, malformed/expired/duplicate scoped waivers, missing trusted baseline, and synthetic enforcement with an exact digest. These test policy decisions, not live GitHub provenance. Observe new PR-head monorepo strict gate, CodeQL and Trivy runs before merging.

Do not turn advisory into a branch-rule gate until affected images and exact upstream digests have been inventoried, remediation and waivers reviewed, and real trust-path tests passed. No GHCR publishing, releases, main promotion, ruleset changes or NAS deployment is part of this change.

### Dependency Review: issue #70

The current action has fail-on-severity: high and warn-only: true. Its healthy PR evidence and known-vulnerable disposable test are documented in #70, but coverage and baseline alert triage remain prerequisites. The next step is a separate, reviewed workflow-only PR switching warn-only to false, followed by a controlled negative test, then independently approved dev/main required-check registration. Do not silently auto-merge dependencies, change the current action, or assume an advisory check is enforcing the threshold.
