# Fox Den Media 1.0 — Authentik OIDC administrator-role synchronization (#57)

Status: **draft fix; release blocker open until reviewed CI and new isolated runtime acceptance**.
Baseline: `dev` at `7c944988d737f42a0d1bc724bb7748a065ae3bc9`. This work does not merge/deploy, alter NAS state, or modify browser PR #39 / availability PR #41.

## Threat and before/after behavior

Prior implementation updated `external_identities.claims_json` but kept the old `users.role` on a linked provider/subject. Every Portal request reads the *current locally stored* role and active flag, so a stale persisted admin role remained privileged even across new OIDC logins.

This patch:
- Resolves the identity only by verified OIDC issuer/provider plus stable subject, **never** by email or username.
- Atomically updates an active linked external user's persisted role to the role derived from the latest validated OIDC claims. On any role change, removes **all earlier Portal sessions** for that user. The new successful callback creates a fresh session at the synchronized role.
- If the validated subject is denied by `PORTAL_OIDC_ALLOWED_GROUPS`, downgrades any previously linked admin role to `user` and invalidates prior sessions, without creating a new session.
- Treats absent or non-list `groups` claims as no groups: fail closed for admin privileges, and for a configured allowlist, deny the login.
- Rejects a locally disabled Portal account; never changes unrelated local-account roles or login paths. The hybrid local emergency administrator remains usable during an IdP outage.
- Does not trust unverified claims: token verification/signature/state/nonce/audience/expiry still happens before allowed-group decisions.

## Upstream change-detection limitation — separate release decision

**This is authentication-time synchronization, not continuous Authentik synchronization.**
Removing a group or disabling an Authentik account does not itself inform Portal. A previously issued Portal cookie can remain valid until its local expiry/revocation if no new **verified** OIDC login occurs. An Authentik outage blocks a *new* OIDC login but deliberately does not rewrite roles or invalidate already-issued Portal sessions.

Possible follow-on designs, requiring independent security review and compatible Authentik support:
1. A validated back-channel logout / authenticated event hook keyed by issuer + sub, with replay protection, idempotent session deletion, and carefully verified event semantics. Do not claim Authentik provides it without runtime/version confirmation.
2. Short bounded OIDC Portal sessions (operator may configure `PORTAL_SESSION_SECONDS`; current default 28800 seconds) and explicit reauthentication before sensitive operations. This only *bounds*, rather than instantly detects, changes.
3. A rate-limited authenticated IdP membership polling/refresh design with trusted current group data, timeout and fail-closed rules. Never use stale cached ID-token claims as a substitute for a fresh upstream check.

Even a correctly synchronized Portal DB cannot terminate *already-upgraded* noVNC sessions by itself; draft PR #39 addresses active WebSocket reauthorization separately.

## New **approved disposable** deployment acceptance

- [ ] Record exact tested commit, `VERSION`, Authentik version/provider settings, ingress/browser/Music image digests, and a backup/restore point. **Never use Test57, Test51, production or existing NAS services**.
- [ ] Confirm Authentik emits `groups` in signed ID-token claims with expected exact strings and that `PORTAL_OIDC_ALLOWED_GROUPS` and `PORTAL_OIDC_ADMIN_GROUPS` match.
- [ ] In two independent browsers with distinct sessions, start with a normal user, grant Authentik admin-group membership, perform a *fresh* OIDC authentication, confirm admin access and prior session revocation.
- [ ] Remove admin-group membership, complete a fresh verified OIDC login, confirm `users.role=user`, prior session invalidation, admin routes 403 and ingress-admin authorization 403; normal user access remains.
- [ ] Remove allowed-group membership or omit `groups`; confirm callback 401 and previously linked Portal sessions are revoked, admin role downgraded. Restore group and retest.
- [ ] Disable the **Portal** external account and confirm existing cookie denied immediately and OIDC callback rejected. Disable the **Authentik** account separately and document whether the IdP blocks new tokens; measure the prior cookie's remaining lifetime and note that this patch has no upstream notification.
- [ ] Simulate provider outage and invalid token; no new OIDC session, no untrusted role mutation. Existing local emergency administrator must still sign in (hybrid mode).
- [ ] Verify access through Portal, NGINX ingress-admin endpoint, Music/Movies/Jellyfin integrations, and optional Firefox/noVNC in disposable context, including direct exposure and cached/upgraded connection limitations (PR #39 separate).
- [ ] Run full CI, dependency/security scans and CodeQL on exact PR head; store redacted proof. A CI pass alone is not NAS acceptance.

## Rollback

No schema migration. On an **authorized new disposable** environment, take a consistent Portal SQLite backup and retain the tested image/commit before the change. To roll back, stop the disposable stack, restore its previously reviewed image/commit (and database backup if necessary), then re-run login/ingress checks. Old behavior **reintroduces stale OIDC privileges**: restrict or disable external admin/browser access until mitigation is restored. Preserve the independent local emergency administrator and its credentials. No main/dev merge or production change without explicit release approval.

## Branch/version coordination

The draft is based on `VERSION=0.9.3` and proposes the one-bug patch `0.9.4` for #57. Draft PR #41 independently also proposes `0.9.4` for #37. After either is merged, the other must be rebased to the then-current `dev`, assigned the **next** sequential patch version and given a matching single-bug changelog entry. Do not merge colliding release versions.
