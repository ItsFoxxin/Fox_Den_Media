# PR #10 CodeQL remediation

This review covers the eleven alerts introduced on the PR #10 merge ref and does not change the
security ruleset. The review was performed on the existing
`feature/legacy-history-completion-rehearsal-1.0.0` branch after the deterministic Music volume
initialization fix.

## Findings

| Alert | Rule and severity | Disposition | Evidence and remediation |
| --- | --- | --- | --- |
| 2 | Clear-text sensitive storage, high | Intentional protected runtime representation; hardened | Nginx must receive the ingress comparison value in its runtime configuration. The renderer now creates a unique mode-0600 temporary file, flushes it, and atomically replaces the target. No value is logged or returned. Recommended GitHub dismissal: `won't fix`, because the clear-text representation is required at the Nginx trust boundary and is protected as a secret file. |
| 3–4 | Clear-text sensitive storage, high | Test-only; hardened | The disposable integration runner generates random, ignored credentials. Secret and rendered-config files are now created with mode 0600 from the first write and reject symlink targets where `O_NOFOLLOW` exists. Recommended dismissal: `used in tests`. |
| 5–6 | Clear-text sensitive storage, high | Test-only; hardened | The ingress smoke test uses synthetic per-run secrets in a private temporary directory and removes the directory in `finally`. Its files now use the same mode-0600, no-follow writer. Recommended dismissal: `used in tests`. |
| 7 | Stack-trace/information exposure, medium | Confirmed and fixed | OIDC startup exceptions previously reached the response after HTML escaping. The response now uses fixed public messages and a regression test proves internal host and credential-like exception details are absent. |
| 8 | Incomplete URL substring sanitization, high | False positive; test improved | This was a test assertion, not a sanitizer. The test now parses anchors and checks the exact configured `href`, which is also closer to the security property being tested. |
| 9 | Incomplete URL substring sanitization, high | False positive; test improved | This was a test assertion over already escaped HTML. The test now parses the body and iframe attributes and compares their exact values to validated configuration. |
| 10 | Overly permissive file, high | False positive, dismissed | `identity-public.json` is an Ed25519 public verification key and contains no signing secret. Independent modules intentionally require read access while only Portal receives the private key. Mode 0644 is the least surprising portable public-key permission. GitHub dismissal: `false positive`. |
| 16 / post-fix 18 | Partial SSRF, critical | Defense-in-depth weakness fixed; residual data-flow alert dismissed | The Jellyfin origin is operator-only environment configuration, but the private request helper previously accepted an arbitrary path. The adapter now validates the configured base URL, permits only the required GET/POST API paths, rejects absolute/scheme-relative/traversal paths, disables redirects and environment proxies, and has focused origin-override tests. CodeQL still tracked the allowlisted item identifier into the URL path, so the post-fix alert was dismissed as `false positive` with those exact controls recorded in GitHub. |
| 17 | Unvalidated dynamic method call, high | Confirmed and fixed | Movies/TV selected a renderer through a computed object property. It now uses an explicit switch over supported tabs with a safe default, with a structural regression test. |

## Existing alerts outside this change

The PR merge ref also reported six older Music alerts: alert 1 (`py/polynomial-redos`) and alerts
11–15 (`py/overly-permissive-file`). They predate the eleven PR #10 findings and are not modified
by this bounded remediation. They must remain visible and be handled under their existing Music
security review; this document does not classify them as resolved.

The other nine requested PR #10 alerts closed automatically on the post-fix CodeQL analysis. No
query, workflow, or scanning rule was disabled.

## Docker initialization race

Commit `8f4e06f1291b62ee6a71c5ef15b1fc1f4caaa712` already resolved the reported clean-volume race.
Both Music consumers mount `music-config` with `volume.nocopy: true` and wait for the one-shot,
network-disabled `volume-init` service. This prevents concurrent Docker image copy-up from creating
the same `cache` directory. The integration Compose regression test asserts the initializer,
dependency ordering, private network posture, and no-copy mounts.
