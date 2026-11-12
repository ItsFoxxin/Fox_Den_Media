# Features and Components

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

| Module | Role | When available |
| --- | --- | --- |
| Nginx + Portal | Shared entry point, local login and optional Authentik OIDC, module access | Always |
| Music web + worker | Requests, MusicBrainz metadata search, intake, review and library handoff | `music` |
| Movies & TV | Requests, torrent association, validation and approved imports | `media` |
| Firefox server browser | Admin-only contained browser, optional Downloader Home | `browser` with Music |
| qBittorrent + Gluetun | Downloader sharing a VPN network namespace | `managed` |
| Jellyfin | Optional official server with separate native-client identity | `jellyfin` |
| Watch & Listen | Per-user Jellyfin browsing, search and playback handoff | Configured Jellyfin account |

## Important limits

A browser HTTP health check does not prove a usable noVNC session. A healthy Gluetun container does not prove kill-switch behavior during tunnel loss. CI checks do not prove real NAS access or data compatibility. Production acceptance remains separate.

Read [Movies & TV requests](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/requests.md), [music search](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/music-search.md), [Watch & Listen](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/watch-listen.md), and [validation history](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/validation.md).

Next: [[Deployment Modes|Deployment-Modes]].