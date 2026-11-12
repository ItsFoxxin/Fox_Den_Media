# System Requirements

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

## Baseline

- Linux or compatible NAS host with Docker Engine and **Docker Compose v2** (`docker compose`).
- Docker access, Python 3 and installable dependencies for the Portal/Ed25519 key generation. CI uses Python 3.12.
- Free capacity for images, private configuration, databases, staging, media and backups.
- Planned **numeric** service UIDs/GIDs and verified host filesystem/ACL access.
- Private, distinct persistent directories and a separately tested backup/restore target.

No universal minimum RAM, CPU or disk-size requirement has been production validated. Review [Compose resource defaults](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/deploy/compose.yaml) and size to selected services and media libraries.

## Optional modules

| Module | Additional considerations |
| --- | --- |
| Full-managed downloader | `/dev/net/tun`, WireGuard provider, controlled egress and fail-closed staging test |
| Jellyfin | Dedicated native-client hostname, storage permissions; optional GPU `/dev/dri` and group validation for hardware acceleration |
| Firefox | Optional browser profile with Music, accessible noVNC/WebSocket route and real-browser acceptance |
| Internet-facing use | Independently configured HTTPS reverse proxy, accurate public origin and secure cookies |

**For an existing NAS:** isolated ports, a unique Compose project name and never-shared writable state are required for rehearsal.

See [installation requirements](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md), [storage variables](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md), [hardware validation](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/n100-hardware-validation.md) and [NAS-specific guidance](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ugreen-nas.md).