# Deployment Modes

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Fox Den Media always runs **ingress + Portal** and adds applications by explicit selection.

| CLI mode | Compose profiles | Intended service set |
| --- | --- | --- |
| `music` | `music` | Music web and worker |
| `media` | `media` | Movies/TV with external qBittorrent |
| `jellyfin` | `jellyfin` | Official Jellyfin |
| `full-external` | `music`, `media` | Music + Movies/TV, external downloader |
| `full-managed` | `music`, `media`, `managed` | Music + Movies/TV + qBittorrent/Gluetun |

Optional switches: `--browser` needs Music; `--jellyfin` adds Jellyfin; `--jellyfin-hwaccel` adds a reviewed GPU override. Environment variables alone do not select Compose profiles.

For direct Compose with a browser, both `--profile browser` and `REMOTE_BROWSER_URL=/server-browser/` must be present. With `scripts/foxden.py`, the `--browser` flag manages this setting.

**Managed VPN warning:** qBittorrent must remain inside Gluetun's namespace; validate tunnel loss and firewall behavior before real downloader use.

For exact examples, profile flags, required fields and any changed constraints, consult [deployment](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/deployment.md), [configuration](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md) and [VPN isolation](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/torrent-vpn.md).