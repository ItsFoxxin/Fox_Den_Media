# Troubleshooting

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Begin with **read-only observations** and an **isolated test environment**. Obtain production change approval before starting/stopping services or changing live credentials.

## Safe first checks

~~~bash
docker compose version
python scripts/foxden.py validate music --env .env
docker compose --env-file .env -f deploy/compose.yaml --profile music ps
docker compose --env-file .env -f deploy/compose.yaml --profile music logs --tail=100
~~~

Replace `music` with your chosen mode and matching profiles. `validate` rewrites a private rendered Nginx configuration even though it does not start containers. Review logs before sharing: they may include private URLs, paths or identifiers.

| Symptom | First area to check |
| --- | --- |
| `init` fails | Portal dependencies and Ed25519 key generation |
| `validate` rejects a mount | Absolute directory paths, overlap, UID/GID and ACLs |
| Login redirects loop | HTTPS origin, cookie settings, proxy headers, IdP redirect |
| Music/Movies unavailable | Selected Compose profile, health, Portal permissions |
| Browser link absent | `--browser`, Music profile, frontend reachability |
| Gluetun unhealthy | DNS/HTTPS health probe, tunnel and firewall; do not bypass VPN |
| Jellyfin missing content | Read-only library mount, container user, Jellyfin schema |
| Restore fails | Writer state, SHA-256 manifest, empty-target rollback |

Consult [full troubleshooting table](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/troubleshooting.md), [VPN troubleshooting](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/gluetun-validation.md), and [recovery](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/recovery.md). Stop a change if VPN isolation, state ownership or rollback evidence is uncertain.