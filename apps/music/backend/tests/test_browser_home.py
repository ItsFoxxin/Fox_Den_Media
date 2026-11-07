"""Regression coverage for the contained Firefox Home destination.

The Music provider supplies metadata/acquisition handoff, not necessarily the
Firefox startup page. The browser control must use the same BROWSER_HOME_URL as
Compose's FF_OPEN_URL; never leak a MusicBrainz or blank provider URL into it.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from foxden_music.config import Settings
from foxden_music.enums import AcquisitionProvider, PreferredFormat
from foxden_music.models import AcquisitionJob
from foxden_music.request_workflow import create_request_jobs, parse_request_reference
from foxden_music.web import create_app


def test_browser_home_uses_configured_home_not_music_metadata_provider(settings, database):
    configured = settings.model_copy(update={
        "remote_browser_url": "/server-browser/",
        "browser_home_url": "https://spotidownloader.com/",
        "music_request_provider_url": "https://musicbrainz.org/",
    })
    with database.session() as session:
        job = create_request_jobs(
            session,
            [parse_request_reference("Fox Artist - Night Run")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        acquisition_id = job.id
    with TestClient(create_app(configured, database)) as client:
        response = client.get(f"/acquisitions/{acquisition_id}/browser")
        assert response.status_code == 200
        assert 'data-home-url="https://spotidownloader.com/"' in response.text
        assert 'data-home-url="https://musicbrainz.org/"' not in response.text
        assert "Enter" in response.text and "server Firefox address bar" in response.text
        assert response.headers["cache-control"] == "no-store"


def test_browser_home_defaults_to_spotidownloader_when_not_explicit(settings, database):
    configured = settings.model_copy(update={
        "remote_browser_url": "/server-browser/",
        "music_request_provider_url": "https://musicbrainz.org/",
    })
    with database.session() as session:
        job = create_request_jobs(
            session,
            [parse_request_reference("Fox Artist - Night Run")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        acquisition_id = job.id
    with TestClient(create_app(configured, database)) as client:
        response = client.get(f"/acquisitions/{acquisition_id}/browser")
        assert response.status_code == 200
        assert 'data-home-url="https://spotidownloader.com/"' in response.text


@pytest.mark.parametrize("url", [
    "http://spotidownloader.com/",
    "https://user:pass@example.com/",
    "https://example.com:8443/",
    "https://example.com/#fragment",
    "https://example.com/\\n",
    "javascript:alert(1)",
])
def test_rejects_unsafe_browser_home_urls(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, browser_home_url=url)


def test_allows_valid_custom_https_home():
    settings = Settings(_env_file=None, browser_home_url="https://downloads.example.org/home/")
    assert settings.browser_home_url == "https://downloads.example.org/home/"
