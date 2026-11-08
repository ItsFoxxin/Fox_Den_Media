# Music Downloader

> **Release status:** This Wiki describes a development/rehearsal candidate. No production-approved 1.0.0 release has been published. Follow reviewed release refs for future stable installations.

Music provides metadata search, request intake, staging, review/import workflows and an independently running Music worker.

## Typical flow

1. Enter a track, album, artist or `Artist - Song` request.
2. Review MusicBrainz results and select the correct recording/edition; a search score is **not** a probability of correctness.
3. Process a request using available configured sources and the worker's queue/staging flow.
4. Review resulting library changes; respect ownership and output-group permissions.
5. Optionally request a Jellyfin library refresh through a distinct worker API-key integration.

The optional server browser appears only when the browser profile is selected and its internal frontend responds; its availability check does not prove a working Firefox desktop.

## Administration

Keep staging, inbox, library and config paths distinct, with tested numeric ownership. Do not expose administrator acquisition routes to general users. Inspect diagnostics without posting filenames/paths from private libraries.

Read [search behavior](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/music-search.md), [worker handoff history](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/music-inbox-handoff-0.9.2.md), [storage settings](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md) and [Music component docs](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/apps/music/README.md).