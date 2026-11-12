# Movies & TV

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Movies/TV supports a persistent request workflow, qBittorrent association, metadata/FFprobe validation, checksum controls and reviewed imports into the media library.

## Request lifecycle

A request can progress from *waiting for user* to *acquiring*, *downloading*, *validating*, *needs review*, *importing* and *complete*. Successful download alone is **not** permission for unreviewed publication.

The implementation has explicit path containment, safe file handling, no-overwrite and source hash protections. Correct host filesystems, path ownership and administrator roles remain essential.

## Download integration

- `media` or `full-external`: a separately configured external qBittorrent server.
- `full-managed`: qBittorrent inside Gluetun's VPN namespace, requiring staging verification.

Use [request lifecycle](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/requests.md), [downloader isolation](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/torrent-vpn.md), [file safety controls](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md) and [paths and credentials](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md) for operational details.