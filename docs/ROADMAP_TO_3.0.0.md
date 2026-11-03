# Fox Den Media — Roadmap to 3.0.0

**Status:** Proposed product roadmap<br>
**Last updated:** 2026-11-03<br>
**Current validated development candidate:** `0.7.0`, `Music_Downloader` PR #6 (`760dd7c`); hosted CI passed, but no production migration has been performed.<br>
**Target canonical repository:** `ItsFoxxin/FoxDen_Media` (currently developed in the `ItsFoxxin/Music_Downloader` lineage).<br>
**Roadmap owner:** Fox Den
**Rule:** A release milestone is not a deployment authorization. Production data access, migration, and cutover require separate explicit approval.

## Vision

Build one modular, self-hosted Fox Den media ecosystem that works consistently across the web, Android phones, and Samsung Galaxy Watch / Wear OS. Keep Jellyfin as the authoritative media backend, Fox Den Media as the orchestration and experience layer, Authentik/AD as compatible identity infrastructure, and the Midnight design system as the shared visual language.

**Generations:**

- **1.0 — The Platform:** A safe, usable, supported unified production media stack.
- **2.0 — The Mobile Experience:** Native Android Watch & Listen with first-party playback.
- **3.0 — The Wearable Ecosystem:** A dedicated Wear OS companion with rich playback controls.

These are **product milestones**, not a mandate to introduce breaking changes. Follow Semantic Versioning for actual package/API compatibility. Retain `/api/watch/v1` as long as it remains compatible; application major version does **not** require an API major version.

## Release overview

| Target | Codename | Primary deliverable | Gate |
|---|---|---|---|
| 0.7.0 | Watch & Listen foundation | Jellyfin-backed web browsing, user-scoped auth, `/api/watch/v1`; Jellyfin playback handoff | Existing hosted CI passed; stacked PRs remain drafts |
| **0.8.0** | Migration rehearsal | Read-only NAS inventory tooling, consistent backups, isolated restore and verification | Credible evidence and no unsafe live writes |
| **0.9.0** | Release candidate | Approved PR consolidation, security/configuration freeze, complete deployment runbooks | Production-like tests and tested rollback; release candidate tag |
| **1.0.0** | The Platform | Production Fox Den Media with Music, Movies/TV, Portal, Watch & Listen, qBittorrent/Gluetun and configured Jellyfin | Explicitly approved cutover, real-client verification, stabilization |
| 1.1.0 | Refine the experience | Performance, accessibility, telemetry, backups, design consistency, quality-of-life improvements | Backward compatibility and operational stability |
| 1.2.0 | Client-ready API | Mobile-focused authentication and device/session endpoints; playback contract groundwork | Versioned contract tests, token revocation, user isolation |
| **2.0.0** | The Mobile Experience | Usable native Android Watch & Listen app with first-party audio/video playback | Tested Media3 playback, secure sign-in, progress sync, background audio |
| 2.1.0 | Mobile polish | Queues, playlists, library UX, optional offline downloads after feasibility/security review | Device, storage, entitlement and interruption tests |
| 2.2.0 | Cross-device foundation | Device list, playback-target selection/remote control groundwork and Wear OS companion contracts | Replay-safe commands and consistent device state |
| **3.0.0** | The Wearable Ecosystem | Dedicated Fox Den Wear OS companion app for Galaxy Watch | Paired-phone controls, queue/artwork, reliable sync and battery testing |

Release points between major milestones are **planning placeholders** and may be combined, split, or reordered following test evidence. Avoid release-number inflation just to signify a new frontend; a major version is warranted by product positioning or incompatible change, and should be documented.

---

## Phase A — Reliable production platform (0.8.0 → 1.0.0)

### 0.8.0 — Production migration rehearsal

**Implementation scope**

1. Preserve current branch lineage and stacked PRs; complete code review and analyze dependency changes.
2. Provide read-only NAS inventory scripts for Docker containers, image digests, networks, volumes, mounts, permissions, GPU devices, proxy dependencies, and free capacity. Redact secrets.
3. Implement database-consistent backup/restore procedures for Portal, Music, Movies/TV, Jellyfin, qBittorrent and Gluetun. Copy-on-rehearsal only; preserve old data.
4. Build disposable staging with copied or synthetic state; enforce never sharing writable databases or qBittorrent appdata between old and new processes.
5. Test Music single-song and complete-album workflows, Movie/TV imports, queue/resume/seeding, VPN kill-switch and DNS egress, Jellyfin paths/users/plugins/watch history and optional Intel N100 Quick Sync/VA-API transcoding.
6. Test Authentik Portal OIDC in a safe environment, including local emergency administration; preserve the separate Jellyfin user-authentication boundary.
7. Generate machine-readable evidence including checksums, version/commit, pass/fail, source of evidence and required human sign-off. Missing operational evidence fails closed.

**Exit criteria:** Rehearsal tooling is reproducible, safe against production data, covered by CI, and produces an honest outstanding-blocker report. No real NAS cutover is authorized by passing CI.

### 0.9.0 — Production release candidate

**Implementation scope**

- Review and land the approved stacked monorepo PRs in correct dependency order after strict CI and history checks.
- Freeze product scope; allow only release-blocking security, correctness, migration or reliability fixes.
- Rehearse final deployment on a production-like target with the actual planned Compose modes, host paths, reverse-proxy hostname, TLS, secrets and Jellyfin plugin versions.
- Validate rollback for database upgrade incompatibility, Jellyfin client failure, qBittorrent resume breakage, VPN failure, SSO outage and storage permissions.
- Document the final repository rename procedure, release assets, migration impact, ownership, support, configuration schema, and `1.0.0-rc.1` criteria.

**Exit criteria:** All blockers resolved or explicitly accepted as non-critical, live-environment evidence recorded, and explicit cutover request ready for human approval. A clean release candidate is not yet 1.0.0.

### 1.0.0 — The Platform

**Must be true:**

- Unified deployment is running on the NAS with approved Music, Movies/TV, Portal and optional modules including Gluetun-routed qBittorrent and Jellyfin (managed or validated external).
- Music library, imports, playback handoff, torrent resume/seeding, user identities and existing Jellyfin state are intact.
- Jellyfin authentication/AD plugin state is preserved; Portal Authentik OIDC works if enabled, without assuming Portal login creates a Jellyfin session.
- Watch & Listen browses authorized movies, episodes, artists, albums, songs and playlists; **secure “Play in Jellyfin” handoff is acceptable for 1.0.0**.
- Existing native Jellyfin apps still function; mobile playback and hardware transcoding tested where enabled.
- VPN kill-switch, Caddy/TLS, database persistence, secrets, restore and rollback have operational validation.
- Document a defined stabilization period and measured service health after cutover; tag `1.0.0` only after acceptance.

**Not required for 1.0.0:** Custom in-browser Fox Den streaming player, native Android APK, dedicated Wear OS APK, offline downloads, universal seamless Jellyfin SSO.

---

## Phase B — Stable server and mobile readiness (1.1.0 → 1.2.0)

### 1.1.0 — Refine the experience

- Fix issues observed after cutover; improve accessibility, mobile browser responsiveness, error messages, caching and library performance.
- Consolidate Midnight theme tokens and approved fox mascot assets across media applications and Jellyfin Web, without changing Jellyfin's core image.
- Improve health and diagnostics, upgrade/backup runbooks and failure alerts without expanding administrative access to general users.
- Evaluate a first-party **web playback** proof of concept only after per-user stream delivery, transcode negotiation, seeking, history/progress and token-security design pass review. Optional if it would delay stability.

### 1.2.0 — Client-ready API

- Establish mobile-safe user sign-in (e.g. OIDC Authorization Code + PKCE or an appropriately secured device flow) independent of browser-only Portal session cookies. Native tokens must be scoped, audience-bound, expiring and revocable; store Android credentials using the Android Keystore.
- Expand `/api/watch/v1` with backward-compatible routes for user library, artwork, entitled streaming, watch/listen progress, device/session inventory and explicit playback capabilities.
- Define a protocol for seek/play/stop/progress, device-bound sessions, expired tokens, network interruption and server-initiated revocation.
- Ensure all endpoints enforce the connected user's Jellyfin library permissions and cannot use a shared administrator token. Keep Portal acquisition administration separate.
- Publish an OpenAPI/schema contract and fake-server/mobile-fixture tests.

**Gate to Phase C:** Real device authentication, safe streaming, token refresh/revocation, compatibility, and controlled media playback are demonstrably possible before investing in a full Android UI.

---

## Phase C — Native Android (2.0.0 → 2.2.0)

### 2.0.0 — The Mobile Experience

**First-party Android Watch & Listen app** built with Kotlin, Jetpack Compose and AndroidX Media3.

**Minimum release features:**

- User sign-in and logout, device-level token revocation, stable connection to Fox Den API over HTTPS (Tailscale/private access can be a supported mode).
- Browse Watch and Listen: movies, TV/episodes, music artists, albums, songs and authorized playlists; search, recently added and progress.
- Play both audio and video using per-user authorized Jellyfin streams, with codec/capability negotiation and server-side transcoding where required.
- Music background playback through `MediaSessionService`/`MediaLibraryService`, including lock-screen, headset/Bluetooth and system media controls; apply proper audio focus and interruption handling.
- Seek, pause, next/previous, queue baseline, resume positions and consistent watch/listen progress synchronization.
- Fox Den Midnight colors, approved mascot/typography, usable phone layout, loading/expired-session/offline messaging, accessibility and secure storage.
- Galaxy Watch can use **standard Wear OS phone media controls** through Android MediaSession; a custom watch app is not necessary for 2.0.0.

**Release gate:** Install and use on at least one real Android handset and a test phone/emulator matrix; background playback works under screen lock, focus interruptions and reconnect; playback histories converge with Jellyfin; no admin keys or streaming tokens leak to logs/URLs.

**Not required:** Dedicated watch APK, full offline catalog, Android TV app, SOC mobile integration, cross-device casting.

### 2.1.0 — Mobile polish and optional offline

- Improve playlist/queue management, shuffle/repeat, favorites, album navigation, persistent recently played and accessibility.
- Add optional downloads for offline playback only after verifying content rights, encrypted local storage, local access-control and storage-management policies; do not promise blanket offline availability.
- Handle large libraries, metered networks, buffering, failed transcodes, seek accuracy and app/process recovery.

### 2.2.0 — Cross-device playback foundation

- Define device discovery and playback target capabilities, command authorization, sequence/replay protection and session handoff.
- Test phone-to-phone/browser player state coordination when technically supported; separate a remote control from a stream authorization grant.
- Specify the exact Wear OS contract: now-playing state, playback commands, queues, album artwork, phone pairing, disconnect/error handling.
- Prototype paired-phone communication with Wear OS Data Layer only where phone–watch transport is needed; use the existing secure Fox Den API for appropriate network/cloud-state tasks.

**Gate to Phase D:** The Android client has a stable MediaSession, documented phone–watch contracts, and reliable permission-checked commands.

---

## Phase D — Wear OS (3.0.0)

### 3.0.0 — The Wearable Ecosystem

Build a dedicated **Fox Den Wear OS companion** for supported Samsung Galaxy Watch models running Wear OS.

**Required experience:**

- Midnight-themed compact watch UI with approved fox mascot/icon and legible touch targets.
- Display now playing: track, artist, artwork, playback position and output/device context.
- Play/pause, previous/next, volume when supported, and queue navigation.
- Select phone playback or another *authorized, implemented* playback target when available.
- Browse a bounded set of albums/playlists/favorites from the paired phone or compatible Fox Den APIs, subject to display and battery constraints.
- Pair with the Android phone app and reuse its approved identity/session boundary; no embedded administrator secrets, no second independent authentication implementation.
- Safe handling of Bluetooth/wifi disconnects, offline phone, expired sessions, revoked devices and duplicate commands.
- Test watch battery usage, reconnect stability, network use, accessibility and usability on actual Galaxy Watch hardware.

**Stretch goals (NOT 3.0.0 blockers):** Direct music playback on the watch, independently streaming from Fox Den, offline watch downloads, advanced casting, watch complications/tiles, and SOC alerts. Each requires a separate feasibility/security/battery study.

**Release gate:** Real watch + phone end-to-end tests succeed, all controls affect only the authorized session, losing connectivity fails safely, and the watch adds genuine value beyond standard controls.

---

## Cross-cutting platform conventions

### Brand and asset governance

- Canonical colors: Midnight `#0B1423`, Raised `#142335`, Slate `#25384B`, Border `#36495D`, Mint `#97E7CA`, Coral `#F68D91`, Amber `#F5AD66`, Cream `#F7F5E9`, Muted `#AFC0D1`, Critical `#EF5261`.
- Use approved mascot render and turning reference; do not invent a new fox identity. Maintain source files/paths/license and versioned exports.
- Default fonts: Monaspace Radon Nerd Font (technical), LXGW WenKai Mono KR (Korean/mono), Noto Sans (general). Platform apps may use native accessible fonts when needed; preserve Fox Den identity.
- Reference `docs/FOXDEN_CANONICAL_REFERENCE.md` when available and keep design tokens synchronized.

### Domain policy

- **`thefoxden.link`**: interactive, user-facing services and appropriate client-facing APIs.
- **`thefoxden.cloud`**: infrastructure and operator/backend cloud services.
- A domain suffix is **not** a security boundary: enforce identity, permissions, TLS and network access separately. Confirm the actual public hostname, reverse-proxy routing and DNS before deployment; never hardcode assumed endpoints into Android or watch binaries.

### Identity, media and SOC boundaries

- Prefer Authentik/OIDC for Portal, with appropriate local recovery. Preserve AD/LDAP user mapping as verified.
- Jellyfin remains its own authority for media entitlements and stream access. A Portal OIDC session does not magically become a Jellyfin session.
- Signed short-lived internal service assertions are not mobile access tokens.
- Android and Wear OS may use shared brand and platform conventions, but **SOC administrative permissions must remain completely separate** from Media playback rights.
- Preserve independent lifecycle for Music, Movies/TV, Watch & Listen, Jellyfin, qBittorrent and Gluetun.

### Quality and release rules

- Required at each phase: automated tests, supported dependency security checks, API compatibility tests, security review, release notes, config migration/rollback documentation, monitoring, and explicit human acceptance.
- A passed GitHub CI run does not prove production storage paths, Authentik/AD behavior, real Jellyfin users, GPU transcoding or VPN egress on the NAS.
- A failing dependency or migration gate blocks publication; do not waive silently.
- Avoid feature creep: future-version ideas go into backlog issues; 1.0.0 remains the stabilization target.

## Workstream dependency map

```text
0.7.0 validated branch (draft)
  └── 0.8.0 migration tooling / staging rehearsal
      └── 0.9.0 release candidate / code freeze
          └── 1.0.0 approved production cutover
              ├── 1.1.0 stable UX + maintenance
              └── 1.2.0 mobile-safe auth + streaming contract
                  └── 2.0.0 Android Watch & Listen + MediaSession
                      ├── 2.1.0 polish / optional offline
                      └── 2.2.0 cross-device remote contract
                          └── 3.0.0 dedicated Galaxy Watch / Wear OS app
```

## Next Codex milestone

**Implement 0.8.0 first**, as defined in the existing production migration rehearsal prompt. In parallel, check this roadmap into the canonical repository (`docs/ROADMAP_TO_3.0.0.md` or an existing roadmap document) without expanding 0.8.0 scope to Android or Wear OS implementation. Create epics/issues for subsequent releases and acceptance criteria; keep all major milestones in planning until their prerequisite gates are completed.

## Selected technical references

- Android Media3 background playback and `MediaSessionService`: https://developer.android.com/media/media3/session/background-playback
- Android Media3 overview: https://developer.android.com/media/media3
- Wear OS Data Layer communication and when to use backend APIs instead: https://developer.android.com/training/wearables/data/overview
- Jellyfin administration, migration and API details: https://jellyfin.org/docs/
