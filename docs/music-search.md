# MusicBrainz name search and result selection

This feature provides a **metadata-only discovery flow** in Fox Den Music:
open **Search** in the sidebar (or **Search MusicBrainz** on **Add music**),
choose **Song / track**, **Album / release** or **Artist**, and search by name.
The artist filter is optional. Use `Artist - Song` in the title field as a shortcut.

## Choosing a result

* Results show MusicBrainz search scores where available; **88% is not an
  88% probability of correct identification**. Similar recordings, covers,
  live versions and different release editions may share names.
* Album cards show cover art when the Cover Art Archive has it, release date,
  artist, edition notes, track count and a short track-list preview.
* Track cards show artist, recording, duration, and attached release edition.
  An explicit selection generates a canonical recording URL containing a single
  validated release selector, e.g. `/recording/<id>?release=<id>`.
* Artist cards lead to a bounded release browse. Artist selection **does not**
  request the artist's entire catalog.
* Users can choose a preferred audio format when requesting a selected result.
  Search itself is read-only: **no acquisition directories or jobs are
  created until a CSRF-protected Request button is submitted.**

## Trust boundaries

The server validates MusicBrainz IDs. The resolver independently checks that
the selected release belongs to the recording and that the release contains
the selected recording exactly once. A result that fails validation cannot
advance as a verified exact edition. Results never provide audio files.

Selection still uses the existing `/acquisitions` endpoint, durable
request queue, resolver, manual provider handoff, staged artifact validation,
and review/atomic import workflow. No new downloader, scraper, bypass,
auto-approval, or deployment hooks are introduced.

MusicBrainz requests use the existing identified User-Agent,
`MUSICBRAINZ_CONTACT`, cached lookups, bounded result counts, and shared
process rate limiter. See the [MusicBrainz API rules](https://musicbrainz.org/doc/MusicBrainz_API).
Cover art uses a validated release UUID with
[Cover Art Archive](https://musicbrainz.org/doc/Cover_Art_Archive/API);
missing art should not block requesting an album.

Search errors distinguish invalid terms, unavailable MusicBrainz service,
empty results and missing contact settings. The existing manual bulk request
form remains available and unchanged in behavior.

## Optional Spotify metadata

Spotify URLs remain accepted by the pre-existing request workflow, but
Spotify API credentials are **not required** for name searches.
No Spotify scraping or credential bypass is introduced.
For optional Spotify metadata integration, first verify the app's access
mode, current endpoint entitlements, quota limits and the
[Spotify developer documentation](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).
Spotify's July 2026 Development Mode update shares the API quota among
developer account Client IDs. Do not assume that a working client ID grants
access to every endpoint.

## Validation and rollout

Tests:
`pytest -q apps/music/backend/tests/test_search_experience.py` (run from a
Python environment with `apps/music/backend` installed in editable mode),
plus the existing Music backend test suite. CI must verify this feature
against the monorepo strict gate and CodeQL.

This branch is **not** a release or deployment. Test57 at `6c7f4b1`
and all NAS/production deployments remain untouched. PR review and explicit
deployment approval are required before any promotion.
