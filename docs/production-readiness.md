# 0.9.0 production readiness

## Implemented

- Fox Den Midnight Portal, Music, Movies/TV and optional Jellyfin Web.
- User-scoped Watch & Listen with encrypted Jellyfin tokens and safe playback handoff.
- Modular Music, Media, Jellyfin, full-external and full-managed Compose modes;
  optional browser, Jellyfin and reviewed N100 hardware override.
- Administrator-only acquisition/contained-browser routes and general-user media isolation.
- Sanitized read-only Docker/path/capacity/permissions/device inventory.
- Writer-quiesced state archives with per-file and archive SHA-256 verification.
- Empty-target isolated restore, non-production rehearsal layout, and rollback fixture.
- Provenance-bearing evidence and fail-closed machine/human readiness reports.
- Complete migration, cutover, recovery, repository transition and 1.0 checklists.
- Offline qBittorrent resume-pair discovery and immutable SQLite structure discovery.
- Per-service numeric identities and a Ugreen copied-state rehearsal template.

## Proved by sanitized NAS inventory

- Ugreen amd64 host, Docker 29.6.2, filesystem capacity and the recorded container topology;
- exact Music 2.3.4, Jellyfin 10.11, Radio and Gluetun 3.41.1 mounts and identities;
- Gluetun tunnel routing, DNS and HTTPS egress through a public IP distinct from the host;
- one surviving qBittorrent metadata/resume pair but no registered container or process;
- Intel `/dev/dri` ownership and FFmpeg VA-API/QSV advertisement, but not a working transcode.

## Proved by source and disposable CI

- configuration/profile selection and Compose rendering with optional modules;
- Portal local/OIDC protocol fixtures, roles and Ed25519 module identities;
- Music single-recording/album, metadata, duplicate and real-audio regression suites;
- Movies/TV request/import, path and duplicate controls;
- Watch & Listen authorization, browsing, search, artwork and outage boundaries;
- official Jellyfin container startup with synthetic/disposable state;
- qBittorrent/Gluetun network-namespace and synthetic VPN fail-closed fixture;
- backup manifest, corruption rejection, isolated restore and rollback round trips.

## Pending operational validation

- copied production database/config restore and application compatibility;
- real Authentik OIDC and local emergency recovery;
- qBittorrent pair consistency, payload path, resume/seeding and staging VPN behavior;
- Gluetun kill-switch behavior and explanation/remediation of the ICMP health failures;
- real Jellyfin users, plugins/auth providers, libraries, history, artwork and clients;
- browser/mobile/TV playback, subtitles, seeking and optional N100 hardware transcode;
- final writer stop, consistent backup, routing switch and rollback rehearsal.

## Current decision

**BLOCKED for production cutover.** This branch is a copied-state rehearsal candidate.
CI cannot provide NAS evidence or operator approval, and the tooling intentionally
refuses to convert missing operational evidence into `CUTOVER_READY`.
