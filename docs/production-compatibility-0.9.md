# Fox Den Media 0.9.0 production compatibility report

Status: **ready for a controlled copied-state rehearsal; not ready for cutover**.

This report maps the sanitized read-only inventory captured from `SRV-NAS-01`
on 2026-11-03 to the unified architecture. It does not claim that application
databases, torrent payloads, native clients, or rollback have been tested.

Evidence artifact SHA-256 values:

- `nas-host-inventory-v2.json`: `f8952646745bc57a332d128f6046189965a8c305b9e8e94334ff37adea46770f`
- `n100-hardware.json`: `cb6a5072baf133b7bf5d43e8c117cc2154e424aeb7a84b4f66587cacc3bbf370`

## Confirmed production baseline

| Existing service | Verified state | 0.9.0 migration treatment |
|---|---|---|
| Jellyfin | `jellyfin/jellyfin:10.11`, digest `aefb67e…`, `1004:100`, `/volume2/jellyfin/config` to `/config`, `/volume2/jellyfin/cache` to `/cache`, `/mnt/@usb/sdc2/Media` to `/media` read-only, healthy on 8096 | Rehearse the exact 10.11 image and container paths against copied config/cache. Do not upgrade or mount live state into a second writer. |
| Fox Den Music | `fox-den-music:2.3.4`, web/worker healthy, `1000005:1000004`, shared config/download/staging paths and writable Music library | Preserve the numeric identity in copied-state rehearsal, discover SQLite structure, run real 2.3.4-to-0.9 compatibility tests, then test rollback against an immutable backup. |
| Fox Den Radio | Liquidsoap `2.4.5`, Icecast `2.4`, Music mounted read-only at `/music/kpop`, port 18080 | Keep external for 1.0.0. The migration must not rename the physical Music path or interrupt radio unless separately approved. |
| Gluetun | `qmcgaw/gluetun:v3.41.1`, digest `1a5bf4b…`, `/dev/net/tun`, running but Docker-unhealthy | Rehearse the exact image/config first. HTTPS egress is confirmed through a VPN IP distinct from the host; kill-switch behavior is not confirmed. |
| qBittorrent | No registered/running container; approximately 8.4 MB appdata survives with one `.torrent` and one `.fastresume` | Treat as recovery, not a normal container migration. Inspect a copy offline and locate payloads before any qBittorrent process is started. |
| Tailscale | Standalone host-network container | Remains external infrastructure; no Compose consolidation in 0.9.0. |

The application filesystem has approximately 145.5 GB free. The external media
filesystem has approximately 3.132 TB free. Repeated capacity records sharing a
filesystem device are one capacity pool and must never be summed.

## Permissions and mount compatibility

Fox Den now supports separate `MUSIC_PUID/MUSIC_PGID`, `MEDIA_PUID/MEDIA_PGID`,
`QBIT_PUID/QBIT_PGID`, and `JELLYFIN_PUID/JELLYFIN_PGID`. The Ugreen rehearsal
template retains Music `1000005:1000004` and Jellyfin `1004:100` independently.

This is not permission to recursively `chown`, `chmod`, or change NAS ACLs. The
rehearsal uses copied state and synthetic payload roots. Production media remains
at its established host path and Jellyfin keeps `/media` inside the container.

## Risk-ranked blockers

### Critical — cutover prohibited

1. The qBittorrent payload path and consistency of its single metadata/resume pair are unknown.
2. Gluetun kill-switch behavior during tunnel loss has not been demonstrated.
3. Jellyfin 10.11 copied-state startup has not verified users, plugins, history, progress, artwork, playback, LDAP/AD providers, or native clients.
4. Music 2.3.4 database and queued state have not been exercised with the consolidated application.
5. No final writer-quiesced, checksum-verified production backup exists.
6. Authentik login and local emergency-administrator recovery have not been exercised against staging configuration.

### High — rehearsal may fail

1. Gluetun's Docker health is failing after hundreds of thousands of checks even though DNS and HTTPS egress work.
2. qBittorrent's previous image/version and numeric identity were not captured because no container survives.
3. Music config is mode `0700`; a mismatched numeric identity will make it inaccessible.
4. `vainfo` failed and Jellyfin has no current GPU mapping, so hardware transcoding is unproven.

### Medium — operational validation required

1. Reverse-proxy, Authentik, Caddy and DNS configuration were intentionally not collected in full.
2. Radio and Music share one physical library; atomic publish behavior must remain compatible with Liquidsoap's read-only view.
3. Image digests were unavailable for locally built Music and Radio images and must be preserved/exported before cutover.

## Exact next read-only checks

Run these only under a separately authorized NAS inventory session. They do not
start or stop containers and do not print environment variables or secret files.

```bash
# Locate qBittorrent resume data and possible payload roots without reading file contents.
find /volume2/docker/torrent-vpn/appdata/qbittorrent -xdev -type f \
  \( -name '*.torrent' -o -name '*.fastresume' -o -name 'qBittorrent.conf' -o -name 'torrents.db' \) \
  -printf '%m %u:%g %s %p\n'

# Record ownership and capacity once per filesystem.
stat -c '%d %a %u:%g %n' \
  /volume2/docker/torrent-vpn/appdata/qbittorrent \
  /volume2/docker/fox-den-music/Fox-Den-Music/data/config \
  /volume2/jellyfin/config /mnt/@usb/sdc2/Media
df -B1 /volume2/docker /mnt/@usb/sdc2/Media

# Record compose source labels and image identities without container environments.
docker ps -a --no-trunc --format \
  '{{.Names}}\t{{.Image}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}'
docker image inspect fox-den-music:2.3.4 fox-den-liquidsoap:2.4.5 fox-den-icecast:2.4 \
  --format '{{.RepoTags}} {{.Id}} {{json .RepoDigests}}'
```

After copying qBittorrent and application state into an isolated rehearsal tree:

```bash
python scripts/migration.py qbit-discovery \
  --config-root /rehearsal/copied/qbittorrent \
  --output /rehearsal/private-reports/qbit-state.json
python scripts/migration.py sqlite-discovery \
  --state-root /rehearsal/copied/music/config \
  --output /rehearsal/private-reports/music-sqlite.json
python scripts/migration.py sqlite-discovery \
  --state-root /rehearsal/copied/jellyfin/config \
  --output /rehearsal/private-reports/jellyfin-sqlite.json
```

These reports prove offline structure only. They cannot satisfy the application,
VPN, playback, native-client, or rollback gates by themselves.
