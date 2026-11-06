"""Read-only MusicBrainz discovery for the Music request picker.

Search hits are *suggestions*, not approved acquisition manifests. Selection
returns an exact MusicBrainz reference to the existing queue/resolver.
"""
from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from .musicbrainz import AlbumHints, MusicBrainzClient, MusicBrainzNotFoundError
from .request_workflow import _artist_credit, _score, _split_artist_title


RESULT_LIMIT = 8
MAX_QUERY_LENGTH = 160
MAX_ARTIST_LENGTH = 160


def _mbid(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _duration(value: object) -> str | None:
    try:
        milliseconds = int(value)
    except (ValueError, TypeError):
        return None
    if milliseconds <= 0:
        return None
    minutes, seconds = divmod(milliseconds // 1000, 60)
    return f"{minutes}:{seconds:02d}"


def _artwork_url(release_id: str | None) -> str | None:
    # Never use an externally supplied URL. Only construct the documented
    # Cover Art Archive endpoint from a validated MusicBrainz identifier.
    return f"https://coverartarchive.org/release/{release_id}/front-250" if release_id else None


def _track_preview(release: Mapping[str, Any], limit: int = 7) -> list[str]:
    preview: list[str] = []
    for disc_index, medium in enumerate(release.get("media") or [], 1):
        if not isinstance(medium, Mapping):
            continue
        try:
            disc = int(medium.get("position") or disc_index)
        except (ValueError, TypeError):
            disc = disc_index
        for track_index, track in enumerate(medium.get("tracks") or [], 1):
            if not isinstance(track, Mapping):
                continue
            number = track.get("position") or track_index
            recording = track.get("recording") or {}
            if not isinstance(recording, Mapping):
                recording = {}
            title = str(track.get("title") or recording.get("title") or "Untitled")
            preview.append(f"{disc}.{number} · {title}")
            if len(preview) == limit:
                return preview
    return preview


def _release_hit(release: Mapping[str, Any], *, score: float | None, ambiguous: bool) -> dict[str, Any] | None:
    release_id = _mbid(release.get("id"))
    if not release_id:
        return None
    return {
        "kind": "release",
        "id": release_id,
        "title": str(release.get("title") or "Untitled release")[:500],
        "artist": _artist_credit(release.get("artist-credit")) or "Unknown artist",
        "release": None,
        "date": str(release.get("date") or "")[:30],
        "disambiguation": str(release.get("disambiguation") or "")[:200],
        "duration": None,
        "track_preview": _track_preview(release),
        "track_count": sum(
            len(m.get("tracks") or []) for m in release.get("media") or [] if isinstance(m, Mapping)
        ),
        "score": score,
        "ambiguous": ambiguous,
        "artwork_url": _artwork_url(release_id),
        "reference": f"https://musicbrainz.org/release/{release_id}",
    }


def search_music(
    mb: MusicBrainzClient,
    *,
    mode: str,
    query: str,
    artist: str = "",
    artist_id: str = "",
) -> list[dict[str, Any]]:
    """Return bounded, safe metadata choices; no queue or downloader side effects."""
    mode = mode.strip().upper()
    query = query.strip()
    artist = artist.strip()
    artist_id = artist_id.strip()
    if mode not in {"TRACK", "ALBUM", "ARTIST"}:
        raise ValueError("Choose Track, Album or Artist")
    if len(query) > MAX_QUERY_LENGTH or len(artist) > MAX_ARTIST_LENGTH:
        raise ValueError("Search terms are too long (maximum 160 characters each)")
    if artist_id and (mode != "ARTIST" or not _mbid(artist_id)):
        raise ValueError("An invalid artist selection was supplied")
    if not query and not artist_id:
        raise ValueError("Enter a song, album or artist to search")

    if mode == "ARTIST" and not artist_id:
        hits: list[dict[str, Any]] = []
        for row in mb.search_artists(query, limit=RESULT_LIMIT):
            artist_mbid = _mbid(row.get("id"))
            if not artist_mbid:
                continue
            hits.append({
                "kind": "artist",
                "id": artist_mbid,
                "title": str(row.get("name") or "Unknown artist")[:500],
                "artist": "",
                "release": None,
                "date": "",
                "disambiguation": str(row.get("disambiguation") or "")[:200],
                "duration": None,
                "track_preview": [],
                "track_count": 0,
                "score": _score(row.get("score")),
                "ambiguous": len(hits) > 0 or _score(row.get("score")) < 96,
                "artwork_url": None,
                "reference": None,
            })
        return hits

    if mode == "ARTIST":
        hits = []
        seen: set[str] = set()
        for row in mb.browse_artist_releases(artist_id, limit=RESULT_LIMIT):
            release_id = _mbid(row.get("id"))
            if not release_id or release_id in seen:
                continue
            seen.add(release_id)
            try:
                full = mb.lookup_release(release_id)
            except MusicBrainzNotFoundError:
                continue
            hit = _release_hit(full, score=None, ambiguous=True)
            if hit:
                hits.append(hit)
        return hits

    # "Artist - Title" is a convenience, not a requirement. Artist is optional.
    if not artist:
        pair = _split_artist_title(query)
        if pair:
            artist, query = pair

    if mode == "ALBUM":
        from .musicbrainz import AlbumHints
        matches = mb.search_releases(
            AlbumHints(album=query, album_artist=artist or None), limit=RESULT_LIMIT
        )
        hits = []
        for i, match in enumerate(matches):
            other = matches[i + 1].score if i + 1 < len(matches) else None
            close = other is not None and match.score - other < 8
            hit = _release_hit(
                match.payload,
                score=round(match.score, 1),
                ambiguous=match.score < 96 or close or bool(match.disambiguation),
            )
            if hit:
                hits.append(hit)
        return hits

    rows = mb.search_recordings(query, artist=artist or None, limit=RESULT_LIMIT)
    hits = []
    seen_recordings: set[str] = set()
    for row in rows:
        record_id = _mbid(row.get("id"))
        if not record_id or record_id in seen_recordings:
            continue
        seen_recordings.add(record_id)
        releases = [
            release for release in row.get("releases") or []
            if isinstance(release, Mapping) and _mbid(release.get("id"))
        ]
        # Show up to two edition choices per recording. The resolver validates
        # the selected recording/release pairing before any acquisition.
        options = releases[:2] or [None]
        source_score = _score(row.get("score"))
        for release in options:
            release_id = _mbid(release.get("id")) if release else None
            reference = f"https://musicbrainz.org/recording/{record_id}"
            if release_id:
                reference += f"?release={release_id}"
            hits.append({
                "kind": "recording",
                "id": record_id,
                "title": str(row.get("title") or "Untitled recording")[:500],
                "artist": _artist_credit(row.get("artist-credit")) or artist or "Unknown artist",
                "release": str(release.get("title") or "")[:500] if release else "Release not identified",
                "date": str(release.get("date") or "")[:30] if release else "",
                "disambiguation": str(row.get("disambiguation") or "")[:200],
                "duration": _duration(row.get("length")),
                "track_preview": [],
                "track_count": 1,
                "score": source_score,
                "ambiguous": source_score < 96 or len(releases) != 1 or len(rows) > 1,
                "artwork_url": _artwork_url(release_id),
                "reference": reference,
            })
            if len(hits) >= RESULT_LIMIT:
                return hits
    return hits
