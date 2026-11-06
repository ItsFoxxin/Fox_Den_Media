# qBittorrent and Gluetun VPN isolation

**Current source: 0.9.1** [`deploy/compose.yaml`](../deploy/compose.yaml). The managed downloader is enabled only for `full-managed`, which selects `music`, `media` and `managed`. The `media` and `full-external` modes use a separately configured **external** qBittorrent server; neither starts this managed VPN/client. The old two-file `compose.vpn.yaml` instructions are superseded and are **not** present in the current monorepo.

## Safety contract

1. In managed mode, qBittorrent uses `network_mode: service:gluetun`. It has **no independent Docker network** or published port. Its startup depends on Gluetun being healthy.
2. Gluetun owns the WireGuard interface, firewall, `NET_ADMIN` and `/dev/net/tun`; it publishes only the configured qBittorrent Web UI port (default **`127.0.0.1:8081` to container port `8080`**).
3. Only qBittorrent writes `TORRENT_DATA_PATH` in the managed stack; Media sees this root **read-only** and publishes reviewed copies to `MEDIA_LIBRARY_PATH`.
4. **Never** add a second network, turn off the Gluetun firewall, disable the VPN health dependency, open a direct outbound route, expose the Web UI publicly or start real torrent activity before the approved tunnel-loss test.

This topology is verified by Compose/source and a synthetic VPN fixture, **not** by real managed-mode NAS VPN tests. The existing NAS's separate Gluetun DNS-health correction does not establish safe managed-mode deployment. See [Gluetun validation](gluetun-validation.md).

## Configure managed mode

```bash
cp deploy/examples/full-managed.env.example .env
# Replace example host paths, user/group IDs, unique test ports, public origin,
# PORTAL_MODULES_JSON as supplied, MusicBrainz contact and WireGuard public metadata.
python scripts/foxden.py init --env .env --create-paths
```

Fill private `FOXDEN_SECRETS_DIR/wireguard-private-key` and `qbit-password` with **authorized test** values in a secure editor; `init` creates empty placeholders. Validate access to these files by their mapped container users and keep private file permissions at `0600`. The current relevant names are:

| Field | Meaning |
| --- | --- |
| `QBIT_CONFIG_PATH` | Separate writable qBittorrent appdata / resume state |
| `GLUETUN_CONFIG_PATH` | Separate Gluetun application state |
| `TORRENT_DATA_PATH` | Torrent payload root, `/downloads` inside qBittorrent |
| `QBIT_URL` | App-side API, normally default `http://gluetun:8080` |
| `QBIT_BIND_IP`, `QBIT_WEB_PORT` | Host Web UI bind, default loopback port 8081 |
| `QBIT_USERNAME` | qBittorrent Web UI account; password is in `qbit-password` |
| `WIREGUARD_ADDRESSES`, `WIREGUARD_PUBLIC_KEY`, `WIREGUARD_ENDPOINT_IP`, `WIREGUARD_ENDPOINT_PORT` | WireGuard interface/peer metadata |
| `GLUETUN_HEALTH_SMALL_CHECK_TYPE` | Valid values `dns` (default) or `icmp`; mapped to container `HEALTH_SMALL_CHECK_TYPE` |
| `GLUETUN_HEALTH_TARGET_ADDRESSES`, `GLUETUN_HEALTH_ICMP_TARGET_IPS` | Health probe targets |

`WIREGUARD_PRIVATE_KEY_SECRETFILE=/run/secrets/wireguard-private-key`, `FIREWALL=on` and `HEALTH_RESTART_VPN=on` are set by Compose. Gluetun has `DOT=off` and a configured DNS address; verify whether these choices meet the approved network/privacy policy. **No** current `VPN_PORT_FORWARDING` or `WIREGUARD_PRIVATE_KEY_FILE` environment variable is used by the managed Compose interface. Avoid copying legacy `TORRENT_CONFIG_PATH`, `TORRENT_STAGING_PATH` or `QBIT_PASSWORD` settings from older source Compose files.

## Dry run and staging acceptance

```bash
python scripts/foxden.py validate full-managed --env .env
python scripts/foxden.py deploy full-managed --env .env
# After explicit authorization and review only:
python scripts/foxden.py deploy full-managed --env .env --execute
docker compose --env-file .env -f deploy/compose.yaml --profile music --profile media --profile managed ps
```

The last two commands are **mutating** and must run only on an isolated test stack with separately approved credentials and copied/synthetic data. For first login, use the password set by qBittorrent (a fresh LinuxServer instance may emit a temporary administrator password in private container logs); set a permanent password and synchronize the `qbit-password` secret **without exposing it**. Do not weaken qBittorrent CSRF/host-header protections to make the API work.

Acceptance: observe stable tunnel, DNS/HTTPS egress through the expected VPN public IP (different from host egress), correct Gluetun firewall/default-drop, qBittorrent API and client namespace, then **deliberately interrupt only the rehearsal VPN** and prove all client DNS/HTTP/peer egress fails closed. Restore tunnel and verify recovery. Test real port-forward synchronization only with an explicitly supported provider/approved method; a forwarded port displayed by Gluetun does not prove the client uses it.

## Existing NAS migration

Do not repoint managed `QBIT_CONFIG_PATH` or `TORRENT_DATA_PATH` to a running production client. Inventory all torrents, `.torrent`/`.fastresume` pairs, save paths, client image/version and Gluetun peer configuration. Verify backups, copy state into distinct paths, test seeding/resume behavior, and complete a controlled cutover only after approval.

For an unexpected leak or failed health test, stop the rehearsal client and follow [side-by-side migration](side-by-side-migration.md), [qBittorrent recovery](qbittorrent-recovery.md) and [recovery](recovery.md). **Never disable the kill switch for troubleshooting.**

References: [Gluetun network namespace setup](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md), [Gluetun healthcheck](https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/healthcheck.md), [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).
