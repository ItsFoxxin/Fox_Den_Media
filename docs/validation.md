# Validation evidence

## Production migration rehearsal 0.8.0 - 2026-11-03

- Disposable tests cover secret-redacted Docker inventory, content-free path
  inventory, writer-stop enforcement, per-file backup manifests, corruption
  rejection, empty-target restore, rollback, isolated rehearsal paths, N100
  discovery boundaries, evidence provenance and fail-closed readiness.
- The 0.8.0 feature branch must pass the existing hosted Music, Portal,
  Movies/TV, Watch & Listen, Jellyfin, Compose, dependency audit, VPN fixture,
  container integration and strict-gate jobs before review.
- NAS layout, real application state, Authentik, torrents, VPN connectivity,
  Jellyfin clients/playback and hardware transcoding remain pending operational
  evidence. No mock or CI result is recorded as proof of those boundaries.

## Watch & Listen 0.7.0 - 2026-11-03

- Portal unit and integration tests include encrypted per-user Jellyfin token
  persistence, v1-to-v2 database migration, user-scoped browsing/search,
  artwork validation, credential failures, CSRF, and outage isolation.
- Adapter endpoints were checked against the official Jellyfin 12.4 OpenAPI
  document. Hosted CI and real production-like Jellyfin account validation are
  separate release gates.

## Fox Den Midnight and optional Jellyfin 0.6.0 - 2026-11-01

- Portal suite: **46 passed** locally on Windows, including local authentication,
  role-gated ingress sessions, non-admin dashboard isolation, configuration
  redaction, and the real Movies/TV contract.
- Platform, ingress, migration, and DenKit slice: **33 passed** locally.
- Music suite: **253 passed, 2 skipped** locally; the real-audio case could not
  run without FFmpeg and one hard-link test was denied by Windows permissions.
  Both remain required Linux CI checks and were not weakened or marked passing.
- Release metadata and Python compilation passed locally.
- A disposable Opera walkthrough covered first-run administrator creation,
  authenticated navigation, offline module states, the Jellyfin entry card, and
  mascot/theme asset loading. The sanitized result is in
  `docs/foxden-midnight-portal-desktop.png`.
- Docker is unavailable locally. The official Jellyfin image health check,
  running Nginx/Jellyfin WebSocket proxy, image builds, and full/reduced Compose
  runtime remain hosted-CI checks for this branch.
- No NAS paths, production databases, live Jellyfin configuration, media files,
  VPN credentials, or external identity providers were accessed.

## Guided Movie/TV browser 0.4.0 - 2026-10-15

- Media suite: **40 passed, 1 skipped** locally on Windows. The skip requires
  symlink privileges unavailable to this account.
- Tests cover authenticated handoff access, HTML escaping, request lookup,
  HTTPS-only discovery-home configuration, and all request/import behavior from
  0.3.0.
- Python compilation and all three media JavaScript files passed syntax checks.
- Docker is unavailable locally; Compose, gateway routing, image builds, and the
  running handoff page remain CI checks for this commit.

## Request workflow 0.3.0 - 2026-10-15

- Media workflow suite: **36 passed, 1 skipped** on Windows. The skipped case
  requires local symlink privileges. Tests include a real FFmpeg-generated movie
  moving from a name request through torrent attachment, automatic validation,
  and review readiness.
- Bundled music regression suite: **214 passed, 2 skipped** on Windows. Both
  skips require local symlink privileges.
- Dependency integrity (`pip check`), Python compilation, JavaScript syntax, and
  release metadata checks passed for version 0.3.0.
- Request tests also verify that magnet tracker parameters do not appear in the
  request or activity APIs and that unsupported URL schemes are rejected.
- Docker is unavailable in this local environment. Compose topology, image
  builds, and running-container smoke tests remain GitHub CI checks for this
  commit. Live qBittorrent, VPN, NAS mounts, and seeding behavior remain
  deployment checks.

## Bundled VPN update - 2026-10-14

The first 0.2.0 CI run passed metadata, Compose, and Linux tests (34 media;
214 music with two Windows-only skips). Image builds passed, but container startup
exposed unsupported environment-backed secrets in read-only Music services.
Version 0.2.1 replaces those with the existing environment values and retains the
file-backed VPN key. See GitHub Actions for the latest commit's runtime result.

- Release 0.2.0 metadata, Python/JavaScript syntax, and workflow YAML checks passed.
- Local media tests: 30 passed, one Windows symlink case skipped, and three HTTP
  cases deselected after the Windows TestClient run stalled. The full HTTP suite
  must pass in Linux CI; the local partial run is not a full regression pass.
- New container smoke checks require Docker and were not executed locally.

- Main Compose configuration expands to all seven services without profiles.
- Automated topology checks passed for default port 8080 and custom port 8181:
  VPN namespace, healthy-start dependency, consistent Web UI/firewall/hook ports,
  key mount, restricted capabilities, shared downloads, and read-only app staging.
- The legacy two-file launch produces an identical expanded configuration.
- Four intentionally unsafe variants were rejected: host networking, writable
  app staging, optional qBittorrent profile, and mismatched download sources.
- The prior development commit's GitHub Actions run `37380626394` was checked
  and completed successfully. This does not validate the new commit's CI result.

These are configuration checks, not running-container tests. A local Docker daemon
was unavailable. Live NAS/VPN credentials, egress, kill-switch behavior, and actual
qBittorrent authentication remain deployment checks. CI now repeats the topology
checks as well as application tests and image builds.

## Original application verification

Local verification on 2026-10-05, Windows, Python 3.12:

| Check | Result |
| --- | --- |
| New movie/TV tests | **33 passed, 1 skipped** |
| Bundled music regression tests | **214 passed, 2 skipped** |
| JavaScript parser (`node --check`) | Passed |
| App-only Docker Compose configuration | Passed |
| App + VPN extension Compose configuration | Passed |
| Real local Nginx configuration check | Passed with localhost upstream/Windows log-path substitutions |
| Nginx shared-session HTTP test | Anonymous redirect, authenticated music, media API, static routing, logout passed |
| Browser walkthrough | Login, validation report, approved import, library record, checksum audit, music/movie navigation passed |
| Browser console | No warning/error entries observed during the walkthrough |
| Mobile breakpoint | 390px viewport inspected; no document-wide horizontal overflow |

Tests used FFmpeg/FFprobe 9.0.2 with generated short audio/video fixtures. Workflow
tests exercised full decoding, Unicode paths, unchanged source preservation,
SHA-256 copy verification, copy failure cleanup, existing-destination refusal,
post-validation source changes, corrupt media, unsafe paths, excluded executables
and archives, incomplete torrent rejection, qBittorrent path mapping, cookie
reuse/auth retry limits, signed sessions, CSRF header checks, and restart receipts.

Three symlink creation tests were skipped because the Windows account lacked that
privilege. A Linux CI workflow is included so those tests can run where supported.

The browser demonstration used generated media and a **fake** qBittorrent adapter.
The music dashboard was served by the bundled real music web app with an empty
temporary database. No production media, NAS paths, torrent sessions, or VPN state
were changed. The downloader browser container was not started locally.

Compose validation used Docker Compose 5.6.0; it emitted warnings that secret
UID/GID/mode metadata is ignored outside Swarm. Actual secret readability under
the NAS UID/group must be checked during deployment.

No local Docker daemon was available, so local image build/runtime and the Linux
container topology were **not** validated. CI includes Linux tests and image builds;
its live result is separate from the local results recorded here. NAS access,
qBittorrent live behavior, seeding preservation in a real client, actual disk mount
permissions, and VPN/kill-switch behavior still require deployment verification.

Primary integration references:
[qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29),
[Nginx auth subrequests](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html),
[FFmpeg builds](https://ffmpeg.org/download.html).
