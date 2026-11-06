# Configuration and secrets

The source of truth is [`scripts/foxden.py`](../scripts/foxden.py), [`deploy/compose.yaml`](../deploy/compose.yaml), and [`deploy/examples/`](../deploy/examples/). This guide explains the fields most administrators need; the examples contain the actual environment templates. Do **not** treat the legacy `deploy/examples/media-source.env.example` or `deploy/legacy/` files as the current monorepo installer.

## File selection and protected inputs

Copy exactly one current mode example to a private file (for example `.env`) and adjust it. The repository-level [`.env.example`](../.env.example) is a reference, not a complete mode-specific starter. The deployment controller parses `NAME=value` (with optional surrounding quotes), validates required mode-specific fields, and passes the selected file to Compose via `--env-file`.

| Setting | Used for | Notes |
| --- | --- | --- |
| `FOXDEN_PUBLIC_ORIGIN` | External URL | Include scheme/host; use HTTPS for remote access |
| `COMPOSE_PROJECT_NAME` | Docker Compose project identity | Optional; **required to be distinct** for a side-by-side rehearsal |
| `FOXDEN_BIND_IP`, `FOXDEN_PORT` | Host ingress listener | Default loopback `127.0.0.1:8080` |
| `FOXDEN_PUID`, `FOXDEN_PGID` | Core container account | Positive numeric IDs; default `10001` |
| `PORTAL_CONFIG_PATH` | Portal SQLite/config | Persistent writable directory |
| `FOXDEN_RUNTIME_DIR` | Rendered private Nginx file | Created by `init`, rewritten during validation |
| `FOXDEN_SECRETS_DIR` | File-mounted credentials | Keep private and backed up |
| `PORTAL_MODULES_JSON` | Exposed modules | Must contain exactly the selected mode's Music/Media IDs |
| `PORTAL_AUTH_MODE` | `local`, `oidc`, `hybrid` | Use local recovery during OIDC testing |
| `PORTAL_COOKIE_SECURE` | HTTPS session cookies | Set `true` for all remotely available HTTPS origins |
| `MUSICBRAINZ_CONTACT` | Music provider requests | Mandatory in Music modes; real administrative contact |
| `QBIT_URL` | External Movies/TV API | Needed for `media`/`full-external`; managed defaults to `http://gluetun:8080` |
| `QBIT_USERNAME`, `QBIT_PUBLIC_URL` | qBittorrent integration | Password in file, never an environment variable |
| `GLUETUN_HEALTH_SMALL_CHECK_TYPE` | Managed health probe | `dns` (default) or `icmp`; **not** `HEALTH_SMALL_CHECK_TYPE` in the app env |
| `WIREGUARD_ADDRESSES`, `WIREGUARD_PUBLIC_KEY`, `WIREGUARD_ENDPOINT_IP`, `WIREGUARD_ENDPOINT_PORT` | Managed VPN | Public metadata in env; **private** key only in secret file |
| `JELLYFIN_URL` | Music-worker library refresh | Optional separate integration; requires API key file if set |
| `JELLYFIN_PUBLIC_URL`, `JELLYFIN_INTERNAL_URL` | Watch & Listen/managed Jellyfin | Browser-facing and Portal-facing endpoints |
| `PORTAL_OIDC_ISSUER`, `PORTAL_OIDC_CLIENT_ID`, `PORTAL_OIDC_REDIRECT_URI`, `PORTAL_OIDC_SCOPES` | Authentik/OIDC | Issuer must be HTTPS; client secret is a file |
| `PORTAL_OIDC_ALLOWED_GROUPS`, `PORTAL_OIDC_ADMIN_GROUPS` | OIDC authorization | Verify memberships; don't auto-promote all users |

The controller also checks resource overrides ending in `_CPUS` or `_MEMORY_LIMIT`; examples such as `FOXDEN_APP_MEMORY_LIMIT=1g` are passed to Compose. Avoid `:latest` image values; pin reviewed tags or, ideally, digests.

## Storage map

| Mode | Host path variables | Container usage |
| --- | --- | --- |
| All | `PORTAL_CONFIG_PATH`, `FOXDEN_RUNTIME_DIR`, `FOXDEN_SECRETS_DIR` | Portal state, generated proxy config, private files |
| Music | `MUSIC_CONFIG_PATH`, `MUSIC_STAGING_PATH`, `MUSIC_DOWNLOAD_PATH`, `MUSIC_LIBRARY_PATH` | Config/SQLite, staging, inbox, worker library |
| Movies/TV | `MEDIA_CONFIG_PATH`, `TORRENT_DATA_PATH`, `MEDIA_LIBRARY_PATH` | Config/SQLite, **read-only** downloader payload in Media, writable final library |
| Managed | `QBIT_CONFIG_PATH`, `GLUETUN_CONFIG_PATH` | qBittorrent application/resume state, VPN state |
| Optional browser | `BROWSER_CONFIG_PATH`, shared `MUSIC_DOWNLOAD_PATH` | Firefox config and Music download inbox |
| Optional Jellyfin | `JELLYFIN_CONFIG_PATH`, `JELLYFIN_CACHE_PATH`, `JELLYFIN_MEDIA_PATH` | Persisted config/cache, **read-only** media; container root `JELLYFIN_MEDIA_CONTAINER_PATH` |

`validate` enforces absolute, existing directories with access and rejects overlapping writable role paths; Jellyfin's read-only media root can intentionally encompass separate music/video library roots. The actual container UID/GID (optionally `MUSIC_*`, `MEDIA_*`, `QBIT_*`, `JELLYFIN_*`) must have host filesystem/ACL access; passing host-user `os.access` checks alone does **not** guarantee runtime writes.

Choose *new* paths for experiments. Do not point `QBIT_CONFIG_PATH`, `JELLYFIN_CONFIG_PATH`, Portal state or Music SQLite at an active application's writable tree. Protect large media and torrents with separate storage backups; the migration script's small-state archive intentionally excludes library payloads.

## Secret files

`init --env FILE [--create-paths]` initializes core secret material, generates Portal's Ed25519 signing keypair, and creates optional empty placeholders. It does not overwrite populated existing secret files.

| File under `FOXDEN_SECRETS_DIR` | Consumer |
| --- | --- |
| `portal-secret`, `portal-bootstrap`, `ingress-auth` | Portal encryption/session/bootstrap and Nginx-to-Portal auth |
| `identity-private.pem`, `identity-public.json` | Portal signing / module verification (public JSON is not confidential) |
| `music-csrf` | Music form protection |
| `media-app-token`, `qbit-password` | Movies/TV integration |
| `jellyfin-api-key` | Only Music worker when `JELLYFIN_URL` set |
| `wireguard-private-key` | Only Gluetun managed mode |
| `oidc-client-secret` | Portal Authentik mode |

Keep private files at mode `0600`, set directory traversal permissions appropriately for mapped container UIDs, keep them out of Git/logs and include them in *encrypted, access-controlled* backups. A secret-file placeholder is **not** a functioning provider credential. Avoid creating secrets with `echo` in shell history; use a secret manager or restricted editor. Rotating `portal-secret` breaks existing encrypted Jellyfin links until users reconnect; changing signing key material requires a coordinated public-key rollout.

## Safe preflight

```bash
python scripts/foxden.py init --env .env --create-paths
python scripts/foxden.py validate full-external --env .env
python scripts/foxden.py deploy full-external --env .env
```

The last line is a **dry run**. `validate` checks selected-mode prerequisites and renders runtime proxy configuration; it does not verify live VPN egress, host firewall, Authentik connectivity, storage quotas or application migrations. Do not paste the fully expanded Compose output into tickets or PRs.

Further reading: [installation](deployment.md), [security](security.md), [permissions](permissions.md), [Gluetun verification](gluetun-validation.md).
