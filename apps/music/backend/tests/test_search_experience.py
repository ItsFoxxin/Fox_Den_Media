from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from foxden_music.enums import AcquisitionState
from foxden_music.models import AcquisitionJob
from foxden_music.request_workflow import (
    RequestResolutionError,
    parse_request_reference,
    resolve_reference,
)
from foxden_music.search_experience import search_music
from foxden_music.web import create_app

RECORDING_ID = "297dfc0d-5fec-7b20-1653-d1857ca4b580"
RELEASE_ID = "f21c2200-85ae-4aaa-94d9-e80079a1e705"
OTHER_RELEASE = "d21c2200-85ae-4aaa-94d9-e80079a1e706"


def release_payload():
    return {
        "id": RELEASE_ID,
        "title": "Den Songs",
        "date": "2024-10-15",
        "artist-credit": [{"name": "Fox Artist"}],
        "media": [{
            "position": 1,
            "tracks": [{
                "position": 1,
                "title": "Night Run",
                "length": 180000,
                "recording": {"id": RECORDING_ID, "title": "Night Run"},
            }],
        }],
    }


class FakeMB:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def search_recordings(self, title, *, artist=None, limit=10):
        assert title == "Night Run"
        assert artist in (None, "Fox Artist")
        return [{
            "id": RECORDING_ID,
            "title": "Night Run",
            "length": 180000,
            "score": 88,
            "artist-credit": [{"name": "Fox Artist"}],
            "releases": [{"id": RELEASE_ID, "title": "Den Songs", "date": "2024-10-15"}],
        }]

    def search_artists(self, name, *, limit=10):
        return [{"id": OTHER_RELEASE, "name": "Fox Artist", "score": 99}]

    def browse_artist_releases(self, artist_id, *, limit=8):
        return [{"id": RELEASE_ID}]

    def lookup_release(self, release_id):
        assert release_id == RELEASE_ID
        return release_payload()

    def lookup_recording(self, recording_id):
        assert recording_id == RECORDING_ID
        return {
            "id": RECORDING_ID,
            "title": "Night Run",
            "artist-credit": [{"name": "Fox Artist"}],
            "releases": [{"id": RELEASE_ID}, {"id": OTHER_RELEASE}],
        }


def _csrf(text):
    token = re.search(r'name="csrf_token" value="([^"]+)"', text)
    assert token
    return token.group(1)


def test_song_search_returns_edition_bound_selection():
    hits = search_music(FakeMB(), mode="TRACK", query="Fox Artist - Night Run")
    assert len(hits) == 1
    hit = hits[0]
    assert hit["artist"] == "Fox Artist"
    assert hit["release"] == "Den Songs"
    assert hit["duration"] == "3:00"
    assert hit["score"] == 88
    assert hit["ambiguous"]
    assert hit["artwork_url"].endswith(f"/release/{RELEASE_ID}/front-250")
    assert hit["reference"] == (
        f"https://musicbrainz.org/recording/{RECORDING_ID}?release={RELEASE_ID}"
    )


def test_artist_search_can_browse_releases():
    artists = search_music(FakeMB(), mode="ARTIST", query="Fox Artist")
    assert artists[0]["kind"] == "artist"
    releases = search_music(FakeMB(), mode="ARTIST", query="", artist_id=OTHER_RELEASE)
    assert releases[0]["reference"] == f"https://musicbrainz.org/release/{RELEASE_ID}"
    assert releases[0]["track_preview"] == ["1.1 · Night Run"]


@pytest.mark.parametrize("value", [
    f"https://musicbrainz.org/recording/{RECORDING_ID}?release=garbage",
    f"https://musicbrainz.org/recording/{RECORDING_ID}?release={RELEASE_ID}&other=x",
    f"https://musicbrainz.org/release/{RELEASE_ID}?release={RELEASE_ID}",
])
def test_exact_edition_parser_rejects_tampering(value):
    with pytest.raises(ValueError):
        parse_request_reference(value)


def test_selected_edition_is_validated_before_resolution(settings):
    exact = parse_request_reference(
        f"https://musicbrainz.org/recording/{RECORDING_ID}?release={RELEASE_ID}"
    )
    result = resolve_reference(exact, settings, FakeMB())
    assert result.confidence == 100
    assert not result.needs_user
    assert result.manifest["request_scope"] == "RECORDING"
    assert result.manifest["release_id"] == RELEASE_ID
    wrong = parse_request_reference(
        f"https://musicbrainz.org/recording/{RECORDING_ID}?release="
        "e21c2200-85ae-4aaa-94d9-e80079a1e707"
    )
    with pytest.raises(RequestResolutionError, match="does not belong"):
        resolve_reference(wrong, settings, FakeMB())


def test_read_only_search_and_csrf_submission(monkeypatch, settings, database):
    # No provider/network calls: the response is rendered from bounded fixtures.
    monkeypatch.setattr("foxden_music.web.MusicBrainzClient", lambda *_a, **_k: FakeMB())
    app = create_app(settings, database)
    with TestClient(app) as client:
        page = client.get("/search?mode=TRACK&q=Night+Run&artist=Fox+Artist")
        assert page.status_code == 200, page.text
        assert "88.0% search score" in page.text
        assert "Compare alternatives" in page.text
        assert "Den Songs" in page.text
        assert f"?release={RELEASE_ID}" in page.text
        assert "coverartarchive.org" in page.text
        with database.session() as session:
            assert session.scalar(select(AcquisitionJob.id)) is None

        rejected = client.post(
            "/acquisitions",
            data={
                "csrf_token": "invalid",
                "request_type": "AUTO",
                "source_urls": f"https://musicbrainz.org/recording/{RECORDING_ID}?release={RELEASE_ID}",
            },
        )
        assert rejected.status_code == 403

        submitted = client.post(
            "/acquisitions",
            data={
                "csrf_token": _csrf(page.text),
                "request_type": "AUTO",
                "preferred_format": "FLAC",
                "source_urls": f"https://musicbrainz.org/recording/{RECORDING_ID}?release={RELEASE_ID}",
            },
            follow_redirects=False,
        )
        assert submitted.status_code == 303
        assert submitted.headers["location"] == "/acquisitions?created=1"

    with database.session() as session:
        jobs = session.scalars(select(AcquisitionJob)).all()
        assert len(jobs) == 1
        assert jobs[0].state == AcquisitionState.REQUESTED.value
        assert jobs[0].source_url.endswith(f"?release={RELEASE_ID}")


def test_bounded_search_rejects_invalid_mode_and_large_input():
    with pytest.raises(ValueError, match="Choose Track"):
        search_music(FakeMB(), mode="PLAYLIST", query="test")
    with pytest.raises(ValueError, match="too long"):
        search_music(FakeMB(), mode="TRACK", query="x" * 161)
    with pytest.raises(ValueError, match="invalid artist"):
        search_music(FakeMB(), mode="ARTIST", query="", artist_id="evil")
