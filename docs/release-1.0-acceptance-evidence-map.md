# Fox Den Media 1.0.0 — operational acceptance evidence map and operator handoff

> **PREFLIGHT ONLY — NO-GO / NOT TESTED IN A NEW ISOLATED NAS REHEARSAL.**
> This is an evidence collection contract, not a command to deploy. Do not run any host,
> NAS, Test51, Test57, production, backup, copy, restore, tunnel-failure or publishing
> operation on the authority of this document. All example commands below are **for a
> separately authorized operator** after isolation and rollback prerequisites are met.

## 1. Source and decision boundary

| Item | Verified current integration state (2026-11-12 UTC) |
| --- | --- |
| Repository / target | [`ItsFoxxin/Fox_Den_Media`](https://github.com/ItsFoxxin/Fox_Den_Media), integration branch `dev`; PR #90 remains a separate, documentation-only branch |
| **Current candidate, NOT an accepted source freeze** | [`460cd50749903e00b3066e30715e8fd411cc12ec`](https://github.com/ItsFoxxin/Fox_Den_Media/commit/460cd50749903e00b3066e30715e8fd411cc12ec), root `VERSION=0.9.9`; an **unaccepted operational candidate**, not a 1.0.0 tested deployment |
| **Future actual rehearsal freeze — PENDING** | `EXACT_OWNER_APPROVED_TEST_SHA`, matching `VERSION`, Compose profiles, architecture, exact upstream and locally built test image identities, configuration ID, source/target state snapshot and approval ID: **NOT SET**. Operator must freeze and re-review at A1/A2, regardless of the observed 0.9.9 candidate |
| Historical source represented by the original PR #90 | [`9d770faa5427551f76dac504c9e069887d52aba9`](https://github.com/ItsFoxxin/Fox_Den_Media/commit/9d770faa5427551f76dac504c9e069887d52aba9), `0.9.6`; **superseded as a current-code inventory**, retained only for provenance. Historical CI is not portable to a 0.9.9 rehearsal |
| Protected/stable source | `main` was still `0.9.1` at verification; no approved 1.0.0 source promotion |
| Master register | [Issue #18](https://github.com/ItsFoxxin/Fox_Den_Media/issues/18) — **OPEN**; 1.0.0 **NO-GO**. Historical prose within this register is not proof of its latest source version |
| **Integrated release source (R1–R5, NOT dispatched)** | R1/R2 metadata, immutable lock foundation [PR #79](https://github.com/ItsFoxxin/Fox_Den_Media/pull/79); R3 candidate publisher/R4 signed v2 consumer [PR #81](https://github.com/ItsFoxxin/Fox_Den_Media/pull/81); independent A/C security producer [PR #84](https://github.com/ItsFoxxin/Fox_Den_Media/pull/84), B verifier [PR #93](https://github.com/ItsFoxxin/Fox_Den_Media/pull/93) and finite-decimal fix [PR #95](https://github.com/ItsFoxxin/Fox_Den_Media/pull/95); R5 manual publication gate [PR #80](https://github.com/ItsFoxxin/Fox_Den_Media/pull/80). **All named source PRs merged to `dev`**, not permission to run their workflows. R6 production remains an independent approval boundary |
| Current candidate hosted CI | [Monorepo](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/43310773853), [CodeQL](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/43310774108), [advisory Trivy](https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/43310773890) succeeded for observed `460cd507...` source; **PASS IN CI only**. Advisory Trivy builds and scans actual first-party container images on CI runners, but these results are **not authenticated R3-published OCI manifest-digest evidence**, do **not** establish independent signed R4 release-security acceptance, and are **not** isolated NAS runtime PASS or owner acceptance |
| Historical NAS | Test51/Test57 used **older** code and images; their evidence is context only. Never attach their mount paths, credentials, project names, volumes or container instances to the new test. No new exact-SHA copied-state acceptance has been established |
| Distinct security blockers | [#76 unresolved actual HIGH/CRITICAL image-CVE disposition](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76); [#83 authentic R4 digest-security producer and A/B/C real-provenance acceptance](https://github.com/ItsFoxxin/Fox_Den_Media/issues/83); [F-03 reusable owner GO and partial-publication authorization](ghcr-publisher.md); [F-04 independent monotonic lifecycle continuity](release-publication-r5.md). Source implementations do not resolve actual release-security authorization |
| Operator references | [Earlier detailed NAS checklist](nas-current-dev-acceptance.md), [release checklist](release-1.0-checklist.md), [readiness](production-readiness.md), [compatibility](production-compatibility-0.9.md), [migration](production-migration-rehearsal.md), [recovery](recovery.md) |

**Observed candidate ≠ authorized test freeze ≠ OWNER ACCEPTED.** A0 can inventory the current host and candidate deployment topology without freezing an executable rehearsal commit. For any later copied-state run, obtain a new explicit source/image/config/rollback approval and retain the exact commit in each result. If `dev` advances, do not silently relabel previous evidence as current.

### Evidence state machine (not interchangeable)

| State | Meaning | Who can establish it |
| --- | --- | --- |
| **NOT TESTED** | No qualifying evidence for this source/environment. It is the default for every new isolated NAS case below. Older Test51/Test57 anecdotes do not change it. | Initial preflight record |
| **PASS IN CI** | A test of a specified synthetic/static behavior ran and passed at its stated SHA; attach a job URL. No real state, tunnel, browser, credentials or clients are implied. | Recorded, inspectable CI job |
| **PASS IN ISOLATED NAS** | Actual expected and negative behavior proved in an **approved new disposable** copied-state environment at a frozen SHA, with redacted artifacts, verified rollback and operator identity. | Authorized runtime operator and reviewer |
| **OWNER ACCEPTED** | The owner separately reviews PASS/FAIL/BLOCKED evidence, limitations, source/image identities and risk decisions and explicitly signs off on the named gate. | Repository owner, not automation |

A case may have **PASS IN CI** and **NOT TESTED** runtime simultaneously. Neither
`PASS IN ISOLATED NAS` nor `OWNER ACCEPTED` is recorded by this document. Any
missing, mismatched, inconclusive or unreviewed result remains **BLOCKED / NO-GO**
rather than silently passing. A suspected vulnerability belongs in the private
[security reporting process](../SECURITY.md), not public artifacts.

## 2. Operator authorization, inventory and evidence contract

### Initial A0 — read-only host inventory (separate approval; no deployment)

**Purpose:** learn the actual host/storage, existing writers, snapshot and
recovery capabilities, without altering the NAS. A0 is an inventory visit,
**not** permission to create a test environment. The operator first obtains
the owner's explicit authorization identifying host, read-only account,
permitted inspection scope, operator, collection window and confidential
report destination. No access has been granted or exercised by this PR.

**A0 procedure when authorized** (review the source and CLI on an approved
operator workstation; inspect only metadata needed for planning):

1. Record source candidate SHA, `VERSION`, UTC time, NAS OS/architecture,
   Docker/Compose versions, active project/container names, images/digests,
   stopped/running states, service relationships and health as observations
   only. Inspect no raw container environment or secrets.
2. Record **sanitized** mount/volume *identities* and RO/RW modes, unique
   filesystem IDs, capacity/free space, ACL and numeric UID/GID requirements,
   `/dev/dri` availability if relevant, and all current writers (including
   SQLite databases, worker inbox/staging, Jellyfin and torrent appdata).
   Identify cross-project or shared paths **privately**, never in public PRs.
3. Inventory available backup/snapshot locations, external dependencies and
   reverse-proxy / Authentik / VPN / client boundaries **without** logging in
   as clients or probing credentials. Verify old Test51/Test57/production
   objects are labelled **EXCLUDED / NEVER REUSE**.
4. Where approved, run the existing
   [sanitized host inventory](production-migration-rehearsal.md) with its
   private `--output` pointing to an operator-controlled, preexisting
   confidential report location **outside all NAS application/state mounts**.
   The report-file write is not a volume/service modification; if no safe
   private output location exists, record `BLOCKED` and do not substitute
   an operational path.
5. Privately review and hash the redacted report, compare candidate profiles,
   expected mount owners and available disk to the real host, flag missing
   sources/writers, and propose — **do not create** — unique future
   rehearsal project, empty copy roots, backup destinations and port ranges.

**A0 prohibitions:** no new/start/stop/restart/recreate containers; no
`docker compose up`, `pull`, `build`, `down`, `exec` into live
services, image download or update; no create/attach/delete volumes,
directories or bind mounts in NAS state; no changing ACLs/UID/GID,
environment, firewall, routing, VPN, Authentik, Jellyfin, qBittorrent,
databases or media; no service quiescence, credentials, test accounts,
production traffic injection or Test51/Test57 replacement. Avoid commands
that expand the full private Compose environment into logs. **STOP** if
read-only scope cannot be maintained.

**A0 artifacts:** `A01-inventory.json` (private, timestamped, SHA-bound to
the observed candidate), redacted mount/port/writer matrix, exclusions,
snapshot/storage capability, permission observations, unresolved questions
and operator + owner record. A0 can be **PASS as inventory completeness**
without any application case reaching **PASS IN ISOLATED NAS**. A0
authorization/collection is **PENDING / NOT PERFORMED**.

### Later approvals — separate, not inherited from A0

1. **A1 / copied state:** independently approve each required live-writer
   quiescence, consistent database/appdata backup, SHA-256 verification,
   large-media/torrent snapshots and copying data to new empty isolated roots.
   A0 grants no stop, backup, snapshot or copying authority.
2. **A2 / isolated startup:** separately authorize an explicitly frozen source
   SHA, reviewed image digests, a **NEW uniquely named** Compose project,
   non-overlapping test-only mounts/ports/credentials, isolated client access,
   operator window and out-of-band recovery. Do not reuse Test51, Test57,
   legacy managed stack or production objects.
3. **A3 / disruptive rehearsal:** separately authorize synthetic download/import,
   scoped permission failures, temporary test-identity manipulation, actual
   controlled VPN tunnel interruption, qBittorrent recovery and test-only
   rollback/failure injection. Include an onsite/out-of-band recovery owner.
4. **A4 / acceptance:** owner independently reviews each PASS/FAIL/BLOCKED,
   exact frozen source/image identities, private artifacts and residual risks.
   Source promotion, GHCR publication, tag/GitHub Release and production NAS
   cutover all require **later independent authorizations**; A4 grants none.

**Isolation STOP rules:** Unknown/shared writable mount, preexisting Compose project/container/port,
active unaccounted writer, insufficient or unverified backup, any unplanned production
network connection, lost test credentials, unauthorized role access, VPN leak,
lost/duplicated bytes, secrets in logs, irrecoverable DB/plugin state or no out-of-band
recovery → **stop test writers, isolate ingress, preserve failed evidence and invoke the
approved rollback; do not continue to later cases.** No `down -v`, prune, recursive
`chmod/chown`, shared-path cleanup, bypassing the VPN firewall or reusing old images
against newly migrated databases.

**Private evidence record for EACH case** (e.g. `private-reports/acceptance/<case-id>.json`):
`case_id`; UTC start/end; approved source SHA/version; operator/reviewer; authorization
reference; project name, unique host ports, profile and sanitized mount map; image
digests and architecture; anonymized copied-state fixture ID and pre/post SHA-256;
expected, observed and negative-path behavior; CI URL/SHA where relevant; explicit
`runtime_status=NOT_TESTED|PASS|FAIL|BLOCKED`; artifacts with SHA-256 and restricted
storage references; state mutation/bytes-at-risk; rollback trigger, action and outcome;
open issue and owner acceptance reference. Keep an **immutable** evidence index
binding each case artifact checksum to the same reviewed source and environment.

**PASS artifact** must show time-correlated affirmative **and fail-closed** observations,
pre/post media/DB/hash checks where relevant, and the intact original source. **FAIL
artifact** must record observed divergence, minimal redacted error/status, retained
bytes/DB state and recovery actions; a missing artifact or inability to run is
**BLOCKED**, not PASS. Public PR/Issue content may contain only sanitized statuses,
numeric UIDs/GIDs where approved, synthetic IDs, safe checksums and restricted-artifact
references: never raw envs, credentials, cookies, real paths, filenames, tokens,
VPN peer configuration, private logs, media or user/history data.

The already committed [evidence schema example](../deploy/examples/migration-evidence.example.json)
and `python scripts/migration.py readiness` produce machine/human readiness outputs.
They do not manufacture human acceptance. The only valid successful machine decision is
`CUTOVER_READY` after its required evidence and approvals; otherwise `BLOCKED`.

## 3. Source-SHA-bound operational acceptance matrix

Every **Real state** cell currently reads **NOT TESTED** for the new rehearsal. A
"CI" entry means available automated/static precedent (not necessarily an individual
test result from the three exact-base jobs); correlate a passing check URL and
test name before elevating a case to `PASS IN CI`. Procedures are proposed,
**not executed**. An A0–A3 authorization code is a prerequisite, never a grant.

| Case / issue | Prerequisite and operator procedure **after authorization** | Required PASS / explicit FAIL condition | Existing synthetic implementation evidence | Real evidence artifact **still required — NOT TESTED** | Preserved-state risk / rollback boundary; approval |
| --- | --- | --- | --- | --- | --- |
| **A01: A0-only read-only inventory / later isolation** · #18 | **A0 approval only:** record exact observed 0.9.9 candidate SHA and host/container/image/volume/mount/UID/ACL/writer/backup-capacity metadata, privately exclude Test51/Test57/production; **do not** create/start/stop any container, download image, create volume, copy state, modify service or run credentials. **A2 only later:** examine the separately approved unique isolated project/ports and no shared write mounts | A0 PASS means complete, traceable, nonmutating inventory and explicit excluded paths, **NOT application runtime PASS**; FAIL/BLOCK on unknown writer, missing access scope or unsafe data exposure | Sanitizing inventory fixtures and Compose profile validation exist in CI | **NOT TESTED A0:** `A01-inventory.json`, SHA/version, privately redacted mount/port/writer/inventory hash, operator scope/approval, explicit exclusions and missing facts | **A0 read-only; minimal metadata exposure**. Stop inspection if it risks mutating the host; A1 backup/copy and A2 test startup require distinct approvals. [Inventory](nas-inventory-checklist.md) |
| **A02: consistent backup** · #18 | A1/A3: enumerate every Portal/Music/Media/Jellyfin/qBittorrent writer, SQLite WAL/SHM, secrets/config/plugins/browser appdata; quiesce only authorized state; separately snapshot large media/torrent payloads; archive and verify SHA-256 | Consistent small-state archive + external and per-file hashes + protected large-data snapshot; FAIL if a writer persists or a file/hash is missing | Backup-plan, manifest and corruption-rejection fixtures | `A02-writer-stop.json`, `A02-backup-verify.json`, immutable archive and media snapshot manifest/checksums | **High**: live state and user history. Quiesce/backup only under **A1/A3**, no in-place restoration; follow [migration rehearsal](production-migration-rehearsal.md) |
| **A03: empty-target restore** · #18 | A1/A3: restore verified archive into a different *empty* test-only root; compare checksums, permissions, SQLite integrity, user counts, payload mounts; boot compatible copies only afterward | Byte/state match and no original writes; FAIL on nonempty destination, missing WAL/data, schema mismatch or corrupt hash | Empty-root, no-overwrite and rollback fixture tests | `A03-restore.json` + before/after SHA-256 and test-only startup proof | **High**: database overwrite/history. Stop test writers and restore **only another empty copy** under **A3**; see [recovery](recovery.md) |
| **B01: secret ownership RB-01** · #18 / merged [#20](https://github.com/ItsFoxxin/Fox_Den_Media/pull/20) | A2/A3: audit actual numeric UID:GID/ACLs, test-only private secret bind reads, explicit opt-in `init --apply-permissions` and `--check-service-owners` | Portal/Music/Media/Jellyfin reads work at scoped 0600 owner-only mode; no secret rotated, world-readable or shared media ownership changed | CI covers opt-in scoped creation/ownership and validation | `B01-owner-audit.json`, secret **hash only**, numeric stat before/after and service status | **High**: secret loss or shared ACL mutation. Provision *only approved test leaves*; revert metadata from snapshot, not global chown. **A3** |
| **B02: ingress regeneration RB-02** · #18 / merged [#21](https://github.com/ItsFoxxin/Fox_Den_Media/pull/21) | A2/A3: compare file mode/UID/inode/hash; run nonmutating validate/dry-run, then authorized render; repeat unchanged render, test injected failure on sacrificial copy; recreate **only test ingress** on changed bind | 0600 numeric ingress ownership, unchanged inode when unchanged, old file preserved on failure, refreshed bind and `nginx -t`/routes healthy; FAIL on config disclosure or stale inode | Atomic render, failure, dry-run and inode synthetic tests | `B02-nginx.json`, redacted metadata/inode comparison, syntax and HTTP status matrix | **High**: config secrets/route outage. Restore prior test-only config atomically; stop routing on failure. **A3**; see [NGINX runbook](nginx-regeneration-1.0.md) |
| **C01: pinned Firefox** · #18 RB-03 / merged [#19](https://github.com/ItsFoxxin/Fox_Den_Media/pull/19) | A2: resolve and run exactly `jlesage/firefox:v26.09.1@sha256:302aa068dcfa46a2d248771c998f67377383554df8940252caef42b99c13eb65` on NAS architecture; check no direct host port, no secrets mounted; authenticated admin desktop/mobile noVNC | Real browser UI, working input/download inbox and authorization with exact digest; FAIL on tag-only substitution, blank viewer or bypass | Image/profile/network static regression | `C01-browser-image.json` with inspected digest, architecture, route/port screenshot/status and synthetic file checksum | **Medium/high**: persistent browser profile and downloaded bytes. Preserve test profile; disable optional browser or revert only test browser digest under **A2**; see [image review](browser-image-1.0-review.md) |
| **C02: Downloader Home** · [#27](https://github.com/ItsFoxxin/Fox_Den_Media/issues/27), merged [#24](https://github.com/ItsFoxxin/Fox_Den_Media/pull/24) | A2: with *actual pinned image*, set `BROWSER_HOME_URL` to a safe HTTPS page distinct from `MUSIC_REQUEST_PROVIDER_URL`; navigate away, click Home; repeat disconnected, view-only and mobile/desktop | Existing RFB session navigates to browser Home, not metadata provider; error is truthful and manual address-bar fallback works; FAIL on false success, new session or lost download | Unit/HTTP + mocked noVNC keyboard/home fixture | `C02-home.json`, sanitized URL/status screenshots and session-continuity timestamps | **Medium**: user downloads/profile. Do not clear session/downloads; revert test-only URL/browser config. **A2**; see [Home test](browser-home-0.9.2.md) |
| **C03: RB-04 optional browser** · [#37](https://github.com/ItsFoxxin/Fox_Den_Media/issues/37), merged [#41](https://github.com/ItsFoxxin/Fox_Den_Media/pull/41) | A2/A3: test profile off, enabled/healthy, enabled/stopped/restarted, admin/non-admin/anonymous; direct GET and watched-download POST; preserve manual downloader, name search and upload/import | No action when disabled/unreachable/unauthorized; guarded request fails **before acquisition state changes**; admin works when healthy; manual fallback always remains. FAIL if dead action or state transition | Compose/HEAD readiness, HTTP 409/403/role and watched-download negative fixtures | `C03-browser-states.json` plus before/after acquisition IDs and safe UI/status matrix | **High**: unintended worker state. Stop test browser only; clear `REMOTE_BROWSER_URL`/profile for isolated fallback, no live container restart. **A2/A3**; see [RB-04](browser-availability-0.9.5.md) |
| **D01: Music worker inbox OSError** · [#23](https://github.com/ItsFoxxin/Fox_Den_Media/issues/23), merged [#22](https://github.com/ItsFoxxin/Fox_Den_Media/pull/22) and [#28](https://github.com/ItsFoxxin/Fox_Den_Media/pull/28) | A0: request read-only redacted historical errno/frames *if available*; A2/A3: one synthetic request → MusicBrainz choice → browser inbox → staging/approval → import; double poll, test injected `EXDEV`/`EACCES` and recovery; capture allowlisted operation | Exactly one final import, valid Job/ReleaseCandidate/event, source bytes retained on failure and safe retry/DB rollback; FAIL on duplicate/loss. Historical real OSError **root cause unknown**, do **not** infer `ENAMETOOLONG` | Fixed `InboxFile` vs ORM collision, retry/rollback + numeric `exception_errno`/`handoff_operation` structured logging; EXDEV/EACCES fixture coverage | `D01-handoff.json`, redacted UTC/exception class/numeric errno/allowlisted operation, file-location classification, before/after hash + DB row/event counts; if reproduced, separate root-cause regression required to close #23 | **Critical**: orphaned/duplicated media. Never delete staging/inbox to retry; isolate writer, retain both copies and restore test DB only from pretest archive. **A0** read-only, **A2/A3** repro. See [diagnostics](music-inbox-oserror-diagnostics.md) |
| **E01: Authentik OIDC role/session** · [#57](https://github.com/ItsFoxxin/Fox_Den_Media/issues/57), merged [#59](https://github.com/ItsFoxxin/Fox_Den_Media/pull/59) | A2/A3: approved test IdP/groups; two live browser sessions, fresh verified login after promotion/demotion/allowlist removal, missing groups, Portal disable, IdP outage and local emergency login | Verified claims atomically update linked role and revoke prior sessions on fresh login/denial; admin routes fail after demotion; local accounts unaffected. **Do not claim immediate detection of upstream group/account changes without a new login**; FAIL on stale admin after verified change or lockout | Portal role/session/claims, denied group, account isolation and invalid token regressions | `E01-oidc.json`, anonymized pre/post role/session IDs, 401/403 matrix, IdP-version + claim-shape and cookie-TTL timing | **Critical**: privilege retention/emergency access. Revert only test copy; rollback to older code reopens stale-role risk—restrict OIDC/browser admin until fixed. **A2/A3**; see [OIDC scope](oidc-role-synchronization-1.0.md) |
| **E02: active noVNC authorization RA-06** · [#62](https://github.com/ItsFoxxin/Fox_Den_Media/issues/62), merged [#39](https://github.com/ItsFoxxin/Fox_Den_Media/pull/39) | A2/A3: open actual admin WebSocket; while traffic flows revoke via logout, expiry, Portal disable, stored role downgrade, linked OIDC revocation and simulated DB error; test Origin/unknown upgrade, subprotocol, mobile; hold past max lifetime | Live socket forcibly closes after reauthorization failure (15-second check cadence, allow bounded scheduling latency) and no socket lasts over 1 hour; unauthenticated/mismatched origin fails. FAIL if upgraded channel persists through invalid live Portal authorization | Portal-owned relay, periodic recheck, lifetime and WebSocket protocol regression | `E02-websocket.json`, UTC handshake/revoke/last-frame/disconnect timings, protocol/negative HTTP outcomes and no direct-port proof | **Critical**: active shared-browser access. Disable isolated browser/ingress on failure, preserve logs; never assume NGINX idle timeout equals revocation. **A2/A3**; see [RA-06](browser-session-security-1.0.md) |
| **E03: Portal/Media/proxy integration** · #18 | A2: admin/user/anonymous direct + ingress; Portal hybrid emergency login, spoofed headers, Movies/TV requests, safe approval/import, HTTPS/TLS/cookies, public/protected routes, Jellyfin token separation and restart | Correct admin boundary, local emergency recovery, no unapproved import, intact state and no direct module-port bypass; FAIL on role escalation, exposed token, corrupted request or incompatible proxy | Portal identity/assertion, Movies/TV request/import and NGINX mock regression | `E03-auth-media.json`, safe status/role matrix, media fixture hashes, copied DB counts, TLS/WebSocket headers (redacted) | **Critical**: auth and file writes. Stop test workers, preserve source payload and restore old test DB on failure. **A2/A3** for fault injection; [security overview](security.md) |
| **F01: managed Gluetun fail-closed** · #18 | A2/A3: approved *test* WireGuard, reviewed digest/firewall/namespace, Gluetun-only start and real DNS/HTTPS egress; attach synthetic probe/qBittorrent only when healthy; deliberately fail only isolated tunnel with onsite recovery | VPN IP differs from host, DNS/HTTPS healthy; IPv4/IPv6/direct/LAN/tracker/peer egress prohibited during failure, returns **only over VPN** after recovery; FAIL on **any leak**, bypass or unapproved peer contact | Compose namespace, no-independent-egress and synthetic kill-switch fixture | `F01-vpn.json`, redacted DNS/HTTPS time/IP, namespace/firewall and tunnel-fault timeline, probe/packet summary | **Critical**: leak/remote loss. Stop qBittorrent *before* Gluetun; recover local test tunnel, never disable firewall or disturb existing NAS `torrent-vpn`. **A2/A3**; [VPN guide](gluetun-validation.md) |
| **F02: qBittorrent resume pairs** · #18 | A1/A2/A3: offline inspect copied `.torrent`/`.fastresume` and payload hashes, map save path to test-only `/downloads`; after healthy VPN verify Web API, queue/resume path and port-forward consumer if enabled; no live peers without separate approval | Complete pair, unchanged source/payload, mapping and seed/resume expectations correctly reflected, qBittorrent shares Gluetun namespace; FAIL on unapproved recheck/move/rewrite or open egress | Bencode/discovery, path and synthetic namespace/API fixtures | `F02-qbit.json`, redacted pair/count/path classification, payload SHA-256 before/after, API/forwarded-port statuses | **High**: state corruption/data loss. Stop isolated qBittorrent, restore appdata and payload from untouched snapshot; leave old state unchanged. **A1/A2/A3**; [resume runbook](qbittorrent-recovery.md) |
| **G01: Jellyfin users/history** · #18 | A1/A2: start first with compatible reviewed Jellyfin version, copied config/plugins/auth users/media **same in-container paths**, independent cache; validate restart, library, watch progress, artwork, subtitles, search, user permission and per-user Watch & Listen tokens | Users/history/library counts consistent; playback/continue watching, client access and token isolation persist; FAIL on database/plugin migration mismatch, cross-account access or history loss | Synthetic official Jellyfin startup, user-scoped browse/search/token and migration fixture | `G01-jellyfin.json`, redacted count/role/client playback matrix, version/digest, restart history and checksum | **Critical**: irrecoverable migration/history. Stop test Jellyfin and restore *untouched pre-upgrade* copy; do not run older Jellyfin on upgraded DB. **A1/A2/A3**; [Jellyfin migration](jellyfin-migration.md) |
| **G02: Intel N100 transcoding (if selected)** · #18 | A0 inventory; A2/A3: confirm render/video numeric device groups, reviewed opt-in hardware override and actual media transcode on copied state while observing VA-API/QSV and resource usage | Working stream backed by *observed* hardware decoder/encoder usage, acceptable playback/seek; FAIL on `/dev/dri` existence or FFmpeg advertised support alone. If hardware disabled, owner explicitly signs off `NOT APPLICABLE` with software-playback evidence | Device/identity discovery only; no real transcode proof | `G02-n100.json`, sanitized session/log and GPU/CPU usage with source, digest, device/group IDs | **Medium**: device mapping/performance. Drop override or stop test-only stream; no host driver changes. **A2/A3**; [N100 validation](n100-hardware-validation.md) |
| **G03: clients and outage recovery** · #18 | A2: on approved desktop/mobile/TV clients test Portal, Music, Jellyfin direct play/seek/subtitles, Firefox mobile, logout and restart; simulate test-only Jellyfin/IdP/module outage | Authorized clients work, expected error/recovery and no token/admin leak; history and queued state persist after restart; FAIL on silent loss or unprotected fallback | HTTP/security/outage fixtures, not native real devices | `G03-clients.json`, redacted platform/version, fixture/media-session matrix, timestamps | **Medium/high**: user privacy/client state. Disable test route, restore copied DB if needed; no production client pointing at test secrets. **A2/A3** |
| **H01: full rollback rehearsal** · #18 | A3: inject a test-only failure after successful backups, stop all new writers, preserve failing deployment, validate immutable archive/snapshot, restore to **third empty root**, run prior compatible images/config, test identity, media, seeding over VPN and Jellyfin history | No mixed-version writes, restored bytes/hashes/user counts and prior stack functions; record measured RTO/RPO. FAIL if unable to restore, keys or history lost or VPN bypass | Synthetic `rollback-rehearsal` empty-target fixture only | `H01-rollback.json`, restore hash diff, image IDs, operation timeline, measured RTO/RPO and signed reviewer | **Critical**: prior data. Stop new writers first; never use in-place overwrite, `down -v` or old image on new DB. **A3**, [recovery order](recovery.md) |
| **H02: readiness and owner acceptance** · #18 | After authorized A0–A3 cases: source-bound private evidence, actual CI checks, #23 cause/disposition and separate security gates **#76**, **#83**, **F-03**, **F-04**; obtain independent operator/owner review and current owner-approved test freeze; use readiness schema on real evidence only | Every required case has actual reviewable real PASS or a properly authorized, explicit disposition; no unknown FAIL/BLOCKED, source/image mismatch or unapproved severe finding; **NO-GO** otherwise | Synthetic readiness/schema/fail-closed tests only. Merged R1–R5 source is **not** R3 images, R4 signed live review, R5 publication or A4 acceptance | **NOT TESTED:** `H02-readiness.json` and human report plus explicit source SHA, image/config hashes, separate recorded signoffs and real operator run references | **Release critical**: avoid false readiness and reused GO. No source/publish/deploy by report generation. **A4** and later separately scoped source-promotion, security, publication, production approvals |

**Implementation reconciliation:** PRs [#19](https://github.com/ItsFoxxin/Fox_Den_Media/pull/19),
[#20](https://github.com/ItsFoxxin/Fox_Den_Media/pull/20),
[#21](https://github.com/ItsFoxxin/Fox_Den_Media/pull/21),
[#22](https://github.com/ItsFoxxin/Fox_Den_Media/pull/22),
[#24](https://github.com/ItsFoxxin/Fox_Den_Media/pull/24),
[#28](https://github.com/ItsFoxxin/Fox_Den_Media/pull/28),
[#39](https://github.com/ItsFoxxin/Fox_Den_Media/pull/39),
[#41](https://github.com/ItsFoxxin/Fox_Den_Media/pull/41), and
[#59](https://github.com/ItsFoxxin/Fox_Den_Media/pull/59) are merged on
`dev` as of the source snapshot. Their existence and synthetic regression
coverage do **not** close their corresponding runtime acceptance Issues.
The five explicit open follow-ups are [#23](https://github.com/ItsFoxxin/Fox_Den_Media/issues/23),
[#27](https://github.com/ItsFoxxin/Fox_Den_Media/issues/27),
[#37](https://github.com/ItsFoxxin/Fox_Den_Media/issues/37),
[#57](https://github.com/ItsFoxxin/Fox_Den_Media/issues/57) and
[#62](https://github.com/ItsFoxxin/Fox_Den_Media/issues/62).
For #23 the actual historical `OSError` errno/operation/root cause are
**unknown**; only redacted diagnostic instrumentation is merged.

## 4. Authorized operator order of operations (NOT a run log)

Follow the **detailed** [NAS current-dev acceptance](nas-current-dev-acceptance.md)
for scoped commands, and confirm each command matches the **future owner-approved exact test source** before execution. That earlier checklist predates the current 0.9.9 integration and can contain stale "draft/not merged" status for #37/#57/#62; the current merged-source facts here supersede only those historical status labels, **not** its safety rules.

1. **Read-only A0:** request owner-scoped access to inspect current host and observed candidate metadata **without starting/stopping containers, pulling images, creating volumes, touching credentials, mounting or copying data, changing services or using Test51/Test57 objects**. Write sanitized inventory only to approved private operator report location, then propose (not create) isolation requirements.
2. **Authorize A1/A2:** document mutually exclusive writable roots, test-only
   identities/ports and immutable backup target. Confirm an onsite operator has
   out-of-band access; source snapshot and copied state must never be co-writers.
3. **Backups before startup:** quiesce relevant approved writers, include SQLite
   WAL/SHM and qBittorrent resume pair, capture separate large payload snapshots,
   verify per-file/archive SHA-256 and prove an empty-target restore.
4. **Start minimum isolated services:** check numeric secret owners and targeted
   ingress regeneration. Add browser only with its reviewed immutable digest.
   Record `nginx -t`/HTTPS/cookie/status/role proof before application imports.
5. **Exercise security and application gates:** Home #27, browser availability #37,
   Music import/recovery #23, OIDC #57, live WebSocket #62; then Movies/TV,
   user-scoped Jellyfin/client, optional actual N100 transcode.
6. **Stage managed VPN separately:** require a real authorized test WireGuard
   tunnel and fail-closed proof before starting qBittorrent on copied appdata.
   Do not use a placeholder endpoint or an existing production tunnel as proof.
7. **Prove recovery:** stop all test writers; restore only to a *third empty* root
   with prior compatible images. Capture checksums and RTO/RPO.
8. **Review:** make the source-bound machine/human report; privately review all
   discrepancies and obtain independent owner acceptance. Do not publish raw
   evidence, mutate release checklist checkboxes or close issues without review.

The following source-supported commands are **examples only**, not instructions
to execute in this Worker session. Replace placeholders with an **approved**
private environment and *current source*; each mutating command requires the
noted A-level approval. Keep output private.

```sh
# Source-only/offline preflight in a separate frozen checkout; no NAS required
git rev-parse HEAD
cat VERSION
python scripts/check_release.py

# After A0 approval only: read-only host observation (private output file ONLY
# outside all NAS state/application mounts; no create/start/stop/pull/volume actions)
python scripts/migration.py host-inventory --env APPROVED_PRIVATE_ENV \
  --expected-mode full-managed --output APPROVED_OPERATOR_PRIVATE_REPORT/host-inventory.json

# After A1/A3: backup planning is read-only; --execute writes, requires stopped writers
python scripts/migration.py backup --env APPROVED_PRIVATE_ENV \
  --destination APPROVED_BACKUP_ROOT
python scripts/migration.py backup --env APPROVED_PRIVATE_ENV \
  --destination APPROVED_BACKUP_ROOT --source-commit EXACT_APPROVED_SHA \
  --writers-stopped --execute
python scripts/migration.py verify APPROVED_BACKUP_ARCHIVE

# After A1/A3: restore into a separately approved EMPTY isolated root only
python scripts/migration.py restore-rehearsal APPROVED_BACKUP_ARCHIVE \
  --destination EMPTY_ISOLATED_RESTORE --report PRIVATE_REPORT/restore.json --execute

# After A3: rollback always into another EMPTY isolated root
python scripts/migration.py rollback-rehearsal APPROVED_BACKUP_ARCHIVE \
  --destination EMPTY_ISOLATED_ROLLBACK --report PRIVATE_REPORT/rollback.json --execute

# After completed, reviewed runtime evidence and A4
python scripts/migration.py readiness --env APPROVED_PRIVATE_ENV \
  --mode full-managed --source-version EXACT_APPROVED_VERSION \
  --source-commit EXACT_APPROVED_SHA --evidence PRIVATE_EVIDENCE_JSON \
  --output PRIVATE_REPORT/readiness.json --human-output PRIVATE_REPORT/readiness.md
```

All approval-gated commands above must be reviewed against the actual
source CLI and paths. Some flags only parse when the real confidential
environment is supplied; deliberate placeholders are expected to fail closed.
An `--execute` flag must never be inferred from a successful dry-run.

## 5. Release-security boundaries and dependencies (distinct from NAS acceptance)

**Present implementation, no live execution:** [R1/R2 #79](https://github.com/ItsFoxxin/Fox_Den_Media/pull/79),
[R3/R4 v2 consumer #81](https://github.com/ItsFoxxin/Fox_Den_Media/pull/81),
[A/C producer #84](https://github.com/ItsFoxxin/Fox_Den_Media/pull/84),
[B verifier #93](https://github.com/ItsFoxxin/Fox_Den_Media/pull/93),
[finite-decimal fix #95](https://github.com/ItsFoxxin/Fox_Den_Media/pull/95)
and [R5 publication gate #80](https://github.com/ItsFoxxin/Fox_Den_Media/pull/80)
are **merged source** at current `dev` `0.9.9`. The
[artifact-first acceptance policy](release-1.0-checklist.md) is in `dev`
through merged #63. This does **not** establish R3 OCI candidate publication,
an attested real A/B/C review, a valid signed R4 result, an R5 tag/Release,
an actual production deployment or an owner-approved test baseline.

**Four security prerequisites MUST remain independent of this operational map:**

- **[#76 — image CVEs](https://github.com/ItsFoxxin/Fox_Den_Media/issues/76):**
  real locked-image HIGH/CRITICAL finding inventory and individually verified
  fixed/not-affected dispositions; neither advisory Trivy workflow success
  nor an A0/NAS check proves image security.
- **[#83 — trusted evidence producer](https://github.com/ItsFoxxin/Fox_Den_Media/issues/83):**
  producer/independent verifier source is merged but real exact-digest
  provenance, owner-controlled protected-environment/signer/trust settings,
  authorized R3 → A collection → independent B human review → C finalization,
  signed R4 acceptance and live owner-lifecycle proof remain unaccepted.
- **[F-03 — reusable authorization/partial retry](ghcr-publisher.md)** and
  [R5 publication GO reuse](release-publication-r5.md): existing source-/SHA-
  scoped GO is **not guaranteed one-shot**. Partial candidate publication
  or a stopped publication attempt may leave an authorization reusable.
  Revoke/disable and independently review a scoped recovery plan; do
  not silently re-dispatch or claim automatic single-use safeguards.
- **[F-04 — lifecycle continuity](release-publication-r5.md):**
  checking current GitHub variables, owner-signed lifecycle freshness,
  expiry and revocation does **not** prove independently anchored monotonic
  history against a coordinated rollback of owner-managed state. A separately
  reviewed continuity anchor/mitigation is pending; no security waiver.

These are **NOT a reason to block A0 read-only inventory** when A0 itself is
separately approved; they **do** block any assertion of completed release
security, protected release publications or final 1.0.0 GO. Do not
fold them into #23/#27/#37/#57/#62 runtime case closure, clear them
through synthetic CI, weaken the controls or mark them accepted by this PR.

**Pre-promotion operational GO:** A0 metadata alone is insufficient.
When owner authorizes A1–A3, freeze the **actual** reviewed SHA/image/config,
complete consistent copied-state backup/empty restore, real VPN fail-closed,
Auth/OIDC/live WebSocket, browser, Jellyfin/user history, client and rollback
checks with redacted artifact hashes. Resolve or explicitly disposition #23
and retain #76/#83/F-03/F-04 as independent release-security NO-GO until
their own evidence/decisions. Obtain signed owner acceptance **before**
separately approved `dev` → `main` source promotion.

**Post-promotion sequence (not authorized):** only after separate source GO
and successful promotion to an immutable `main` release source should
R3 create GHCR candidates; R4 consumes independently authenticated and
dispositioned A/B/C evidence and finalizes the signed locked manifest;
R5 separately verifies it at publication. **No final first-party R3/R4
digests are prerequisite for A0 or pre-source copied-state testing.**
An entirely new, independent R6/NAS production GO must identify exact
release-lock digest, target, operator, maintenance window, fresh final
backup and rollback owner. See [release checklist](release-1.0-checklist.md),
[R3/R4 producer](ghcr-digest-security-producer.md),
[R3/R4 verifier](ghcr-publisher.md),
[R5 publication](release-publication-r5.md), and
[production/publication boundary](production-publication-boundary.md).

**Next authorization owner:** repository owner through Coordinator; **next
execution owner:** expressly assigned NAS operator only after A0–A3 approvals.
The documentation Worker has not accessed any NAS, test project, credential,
VPN tunnel, state copy, browser session or production service.

**Current integration result (2026-11-12): `0.9.9` unaccepted candidate;
1.0.0 NO-GO. A0 inventory: NOT PERFORMED. All new isolated NAS runtime
cases: NOT TESTED. Owner acceptance: NOT GRANTED. No live R3/R4/R5 release
publication or production operation is claimed.**
