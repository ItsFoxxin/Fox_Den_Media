# Changelog

## 0.9.4 - 2026-11-07

### Fixed

- Fixes #37: Suppress Music's server-browser actions when Firefox is disabled, unavailable or unauthorized and block watched-download handoff before state mutation when browser is unavailable.

### Validation

- Add bounded internal HTTP readiness checks, Portal admin and unauthorized regression tests, disabled/available/unavailable scenarios, and explicit Compose/controller browser-profile behavior.
- Real pinned Firefox/noVNC tests and copied-state NAS acceptance remain pending. No production deployment or cutover is authorized.


## 0.9.3 - 2026-11-06

### Fixed

- Fixes #27: Make the Music Downloader Home button target Firefox's configured `BROWSER_HOME_URL`, with strict HTTPS validation, explicit noVNC connection and keyboard-state feedback, and a manual address-bar fallback.

### Validation

- Added HTTP/configuration and mocked noVNC keyboard-navigation regressions.
- Actual pinned Firefox image acceptance in a new isolated NAS deployment is still required; no production deployment or cutover is authorized.

## 0.9.2 - 2026-11-06

### Fixed

- Keep the selected inbox file separate from the SQLAlchemy MusicBrainz release candidate during automatic browser-download handoff. The persisted import reference and job event now retain the original relative filename when a resolved release manifest is present.
- Preserve the original database/transaction exception if staging-file recovery independently raises an `OSError`; log the recovery error separately so a stranded staged file can be inspected instead of losing the first failure traceback.
- Add regression tests for populated release manifests, transaction rollback, byte-preserving file recovery, repeated worker polling, successful retry, failed restoration, and initial staging permission failure.
- Prevent repeated recoveries from accumulating filename prefixes or exceeding the filesystem's filename-byte limit. Include safe numeric filesystem error codes in worker JSON logs without emitting sensitive paths.

### Release boundary

- This is a **candidate patch milestone**, not a deployed or approved 1.0.0 release. It changes no database schema and requires passing the existing strict CI and CodeQL gates plus copied-state acceptance, with the subsequent NAS `OSError` independently diagnosed from its errno/traceback.
- No NAS state, Test57, Test51, production deployment, protected branch, or upstream Music Search UX PR was changed.

## 0.9.1 - 2026-11-04

- Updated Portal authentication to Authlib 1.9.4 and added OIDC/JWT security regressions.
- Added Portal dependency auditing, Bandit, CodeQL, and expanded full-history secret scanning.
- Bound Movies/TV staging validation and import to no-follow file descriptors on Linux.
- Strengthened standalone cookie CSRF checks and restricted host-path status details to administrators.
- Added adversarial authentication and staging race tests plus a release security assessment.

## 0.9.0 - 2026-11-03

### Added

- NAS-evidence-driven compatibility controls for the Ugreen N100 deployment,
  including independent Music, Media, qBittorrent and Jellyfin numeric identities.
- Fail-closed inventory completeness checks so Docker metadata cannot be mistaken
  for a complete application-storage inventory.
- Offline qBittorrent `.torrent`/`.fastresume` pair discovery with bencode
  validation, checksums and stored path/category/tag reporting.
- Immutable, read-only SQLite structure discovery for copied Music and Jellyfin
  state; application schema compatibility still requires isolated execution.
- A production compatibility report, risk-ranked blocker register, exact
  read-only follow-up checks and a Ugreen copied-state rehearsal template.

### Preserved boundaries

- Jellyfin 10.11 and Gluetun 3.41.1 are pinned for the first copied-state
  rehearsal; upgrades remain separate compatibility decisions.
- No NAS service, production state, VPN setting, route, identity provider or
  repository protection was changed.

## 0.8.0 - 2026-11-03

### Added

- Sanitized, read-only Docker/NAS inventory for containers, images and digests,
  Compose projects, ports, networks, volumes, mounts, UID/GID, permissions,
  capacity, health metadata, restart policy, proxy dependencies, and GPU maps.
- Application-aware, writer-quiesced state archives with embedded and external
  per-file SHA-256 manifests, safe-member validation, and verified isolated restore.
- Disposable rehearsal preparation that restores copied state, assigns a unique
  Compose project, uses synthetic media/torrent roots, and leaves network
  credentials deliberately blocked pending separate staging authorization.
- Provenance-bearing migration evidence schema, human-readable readiness report,
  rollback rehearsal report, and a fail-closed `CUTOVER_READY` decision.
- Read-only Intel N100 device/VA-API/QSV discovery that explicitly does not claim
  successful hardware transcoding.
- Product roadmap through 3.0.0 and production cutover/recovery documentation.

### Boundary

- CI and synthetic fixtures cannot satisfy the required NAS, real-client,
  real-playback, VPN, Authentik, or operator-approval gates.
- No production service, repository, routing, identity provider, or data was changed.

## 0.7.0 - 2026-11-03

### Added

- Fox Den Watch & Listen at `/watch/` with real per-user Jellyfin libraries,
  recent video and music, continue watching, search, details, and artwork.
- Versioned `/api/watch/v1` adapter and language-neutral response schema for
  future web and Android clients.
- Encrypted per-user Jellyfin token links in a backward-compatible Portal
  SQLite schema migration; passwords and administrator API keys are not stored.
- Android/Media3 and Wear OS/MediaSession roadmap plus an Authentik, AD, LDAP,
  Jellyfin SSO, native-client, and recovery architecture.
- Machine-readable migration evidence gates that keep cutover closed until
  inventory, consistent backup, isolated restore, playback/client checks, and
  rollback have all been confirmed.

### Boundary

- Browser playback remains a safe handoff to Jellyfin until user-scoped stream
  negotiation and progress reporting are reviewed.
- No Android or Wear OS application, live SSO plugin, production NAS change, or
  deployment is included.

## 0.6.0 - 2026-11-01

### Added

- Optional official Jellyfin 12.4 Compose profile with persistent config/cache,
  read-only media, dedicated-host ingress, WebSockets, resource limits, and an
  explicit Intel `/dev/dri` hardware-acceleration override.
- Maintainable Jellyfin Web Fox Den Midnight theme served by ingress without
  modifying the official image.
- Existing-instance inventory, copied-state rehearsal, cutover, backup, and
  rollback documentation.

### Security

- Music, Movies/TV, and contained-browser ingress now require an administrator
  Portal session; general users receive only their media-server link.
- Jellyfin retains native authentication for client compatibility and is never
  placed in Gluetun's network namespace.
- Portal roles never imply Jellyfin administrator privileges.

### Boundary

- No live Jellyfin state, NAS path, Caddy configuration, Authentik provider, or
  production container was inspected or modified.

## 0.5.0 - 2026-10-30

### Added

- Canonical modular monorepo preserving Music lineage and filtered Media history.
- Validated Music, Movies/TV, full-external, and full-managed deployment modes.
- Environment preflight, secret initialization, dry-run deployment control, and
  non-destructive migration inventory/backup/restore rehearsal tooling.
- Managed qBittorrent/Gluetun topology with qBittorrent sharing only Gluetun's
  network namespace and no independent published ports.

### Security

- Upgraded Pillow to 13.0.0 after the strict release audit identified 37
  advisories in 12.3.0; no vulnerability suppression was added.

## 0.4.1 - 2026-10-27

### Added

- Ed25519-signed, audience-bound internal identities with Portal-only private
  keys, module public-key verification, replay protection, and documented
  zero-downtime key rotation.
- Separate service-scoped Portal activity aggregation with a sanitized
  Movies/TV activity contract; restricted users remain read-only while
  Portal-originated writes require administrator role.
- Real Movies/TV module-summary endpoint implementing Portal contract v1 with
  sanitized health and capabilities. Activity remains withheld until trusted
  Portal-to-module authentication is implemented.
- Cross-component contract tests that validate the real Movies/TV response with
  the Portal's strict contract model.
- Accepted and implemented the review configuration for the existing Nginx
  gateway to become the sole ingress, with Portal as an independent session
  authority and optional-module failure isolation.
- Container regression coverage for Portal availability with Music, Movies/TV,
  and the contained browser absent, plus client identity-header stripping.
- Phase 1A Portal foundation with a responsive platform dashboard, isolated
  module status aggregation, and versioned module contracts.
- Portal-owned local authentication, protected first-run administrator setup,
  optional OIDC/hybrid authentication, and mocked Music and Movies/TV adapters.
- Portal threat model, Authentik/Caddy integration plan, mocked demonstration,
  and non-root read-only container validation in layered CI.

### Boundary

- Portal remains isolated from production Compose, real module databases,
  production gateway routing, and NAS state until Phase 1B is reviewed.
- No Music source consolidation or production deployment is included.

## 0.4.0 - 2026-10-15

### Added

- Request-specific guided browser for Movie/TV requests using the existing
  authenticated Firefox/noVNC service.
- One-click request copying, configurable HTTPS discovery home, direct
  qBittorrent access, and return-to-request navigation.
- Authenticated single-request API and browser handoff tests.

### Security

- The browser retains its existing isolated mounts and receives no Movie/TV
  library, torrent-staging, qBittorrent credentials, or application secrets.
- Discovery-home configuration requires HTTPS without embedded credentials.
- Login, CAPTCHA, result selection, and qBittorrent attachment remain visible
  user actions.

## 0.3.0 - 2026-10-15

### Added

- Durable Movie/TV request inbox for names, HTTP(S) metadata links, and magnets.
- Request tracking from qBittorrent acquisition through automatic validation,
  reviewed import, and completion.
- Existing-torrent attachment for title/link requests and dashboard state views.
- Tests for the request lifecycle, private magnet redaction, and unsafe schemes.

### Security

- Magnet and tracker parameters remain server-side and are excluded from request
  and activity API responses.
- HTTP(S) request-link query strings and fragments are discarded before storage.

### Boundary

- Fox Den does not automatically select a torrent from a title in this release.
  Selection remains visible; validation and import safeguards remain unchanged.

## 0.2.1 - 2026-10-14

### Fixed

- Pass the existing CSRF and optional Jellyfin secrets directly from `.env` to
  Music containers. Environment-backed Compose secrets cannot be mounted into
  read-only services; the first container CI run caught this startup failure.
- Keep the WireGuard private key as a file-backed secret scoped to Gluetun.
- Stable CI permits only the two explicitly identified Windows-only test skips
  on Linux; all unexpected skips still fail the release gate.

## 0.2.0 - 2026-10-14

### Added

- Gluetun VPN and qBittorrent start with the main Docker Compose project.
- Central `VERSION` file supplies the authenticated status API and dashboard.
- Automated Compose checks cover VPN routing, health dependency, ports, secrets,
  capabilities, and shared staging mounts.
- Fresh-client login and existing-stack migration instructions.
- Layered CI for development and stable branches, with version consistency,
  test reports, container smoke tests, and stricter pre-merge release checks.

### Changed

- The bundled qBittorrent API is the default connection.
- Web UI port changes also update the client listener, firewall, and forwarding hooks.
- Fresh installs default Proton port forwarding to off until localhost hooks are
  configured. Existing explicit `.env` values remain effective.
- `compose.vpn.yaml` is now an empty compatibility shim.

### Upgrade

Configure VPN peer settings, private key file, and pre-created bind paths before
starting the main Compose file. Stop and back up an old torrent stack before
reusing its appdata. Set the qBittorrent password through its Web UI, then provide
it to Fox Den through `.env`. See [VPN setup](docs/torrent-vpn.md).

Local configuration checks passed; live VPN/NAS behavior is not yet verified.

## 0.1.0 - 2026-10-05

- Initial unified development build with shared login and navigation for Music
  2.3.4 and the movie/TV dashboard.
- qBittorrent controls, read-only staging, FFmpeg validation, reviewed verified
  copies, import receipts, recovery, and library checksum audits.
- Optional VPN Compose extension, environment configuration, and Linux CI.
