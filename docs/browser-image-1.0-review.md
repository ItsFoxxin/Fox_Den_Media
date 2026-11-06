# Firefox container image — 1.0.0 candidate

Baseline: `dev` `6c7f4b11a7a6978162057922d788fd9a85fb2d78`. Scope: image reference and static regression coverage only, no NAS changes.

## Finding and fix

The prior default `jlesage/firefox:v25.09.2` was unavailable (`manifest unknown`) during the isolated Test57 rehearsal. The user verified that overriding to `v26.09.1` starts the browser. Docker Hub lists the published `v26.09.1` manifest index as:

```text
jlesage/firefox:v26.09.1@sha256:302aa068dcfa46a2d248771c998f67377383554df8940252caef42b99c13eb65
```

The index includes linux/amd64 and linux/arm64 variants. Sources: [Docker Hub tags](https://hub.docker.com/r/jlesage/firefox/tags), [Docker Hub manifest index](https://hub.docker.com/layers/jlesage/firefox/v26.09.1/images/sha256-48f71a3ec91fab6c064acbe9f4fb2191593436ad4bb036634dcc903c549133a9) and [upstream Firefox image documentation](https://github.com/jlesage/docker-firefox). This digest identifies the reviewed registry content rather than accepting a later tag retarget.

## Compatibility / security assessment

- Existing Compose uses upstream-supported `USER_ID`, `GROUP_ID`, `/config`, browser UI port `5800`, and Firefox preference overrides; it retains the existing browser profile, environment values, network, volumes, and resource limits.
- Browser service exposes only port 5800 to the Compose network (no direct host-published port); the ingress still performs Portal administrator authorization.
- Upstream browser is a third-party interactive application with outbound access and a writable volume. It does **not** have the same read-only-root, capability-drop profile as Fox Den first-party services. Do not describe it as equivalently hardened.
- A running, active noVNC WebSocket may outlive Portal session revocation; see `docs/security-0.9.1.md`. This risk is *not* fixed by an image change.
- Running Firefox and downloaded content are untrusted; ensure authorized use, browser profile isolation, no secrets mounted, and import validation.

## Verification and acceptance

- Static regression: `python -m pytest tests/platform/test_browser_image.py -q`
- Compose profile: `docker compose --env-file deploy/examples/full-managed.env.example -f deploy/compose.yaml --profile music --profile media --profile managed --profile browser config --quiet`
- CI: strict monorepo checks and CodeQL; review any reported findings. The digest check is a static source pin, not a vulnerability scan.
- **Pending on an approved disposable environment only:** pull and inspect the immutable digest, prove Firefox UI session, download to inbox, ownership mapping, Portal admin restriction, no direct host listener, session timeout behavior and rollback. Do not run these on Test57 or production from this PR.
- Rollback: revert this isolated PR or set `BROWSER_IMAGE` to a previously verified digest in a *new disposable rehearsal*. The old `v25.09.2` reference is unavailable and is not a usable rollback image.

Status: **Candidate pin, pending CI and actual browser acceptance**; no release or deployment approval.
