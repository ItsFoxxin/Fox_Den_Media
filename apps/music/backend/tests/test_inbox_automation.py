from __future__ import annotations

import json
import os
import time

import pytest
from pathlib import Path

from sqlalchemy import select

from foxden_music.acquisition import create_acquisition_batch, transition_acquisition
from foxden_music.config import Settings
from foxden_music.database import Database
from foxden_music.enums import AcquisitionProvider, AcquisitionState, JobState, PreferredFormat
from foxden_music import inbox_automation
from foxden_music.inbox_automation import stage_next_waiting_download
from foxden_music.models import AcquisitionArtifact, AcquisitionJob, Job, JobEvent, ReleaseCandidate
from foxden_music.request_workflow import create_request_jobs, parse_request_reference


ALBUM_URL = "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy"


def configured_database(settings: Settings, tmp_path: Path) -> tuple[Settings, Database, Path]:
    inbox = tmp_path / "downloads"
    inbox.mkdir()
    configured = settings.model_copy(
        update={
            "download_inbox_dir": inbox,
            "download_inbox_settle_seconds": 0,
            "download_inbox_min_bytes": 1,
            "download_inbox_auto_import": True,
        }
    )
    database = Database(configured)
    database.initialize()
    return configured, database, inbox


def waiting_acquisition(database: Database) -> str:
    with database.session() as session:
        acquisition = create_acquisition_batch(session, ALBUM_URL)[0]
        transition_acquisition(
            session,
            acquisition,
            AcquisitionState.WAITING_FOR_DOWNLOAD,
            "Server browser opened; watching the download inbox",
        )
        return acquisition.id


def test_settled_download_is_attached_and_queued_automatically(
    settings: Settings, tmp_path: Path
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    acquisition_id = waiting_acquisition(database)
    downloaded = inbox / "album.zip"
    downloaded.write_bytes(b"completed-download")

    job_id = stage_next_waiting_download(database, configured)

    assert job_id is not None
    assert not downloaded.exists()
    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        job = session.get(Job, job_id)
        artifact = session.scalar(
            select(AcquisitionArtifact).where(
                AcquisitionArtifact.acquisition_job_id == acquisition_id
            )
        )
        assert acquisition is not None
        assert acquisition.state == AcquisitionState.IMPORT_STARTED.value
        assert acquisition.associated_import_job_id == job_id
        assert job is not None
        assert job.state == JobState.QUEUED.value
        assert job.source_reference == "inbox:album.zip"
        assert artifact is not None
        assert artifact.received_via == "SERVER_INBOX_AUTO"


def test_download_older_than_watched_request_is_not_claimed(
    settings: Settings, tmp_path: Path
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    old_file = inbox / "old-album.zip"
    old_file.write_bytes(b"old-download")
    old_time = time.time() - 120
    os.utime(old_file, (old_time, old_time))
    acquisition_id = waiting_acquisition(database)

    assert stage_next_waiting_download(database, configured) is None
    assert old_file.exists()
    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        assert acquisition is not None
        assert acquisition.state == AcquisitionState.WAITING_FOR_DOWNLOAD.value


def test_browser_download_is_routed_through_request_private_directory(
    settings: Settings, tmp_path: Path
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    with database.session() as session:
        acquisition = create_request_jobs(
            session,
            [parse_request_reference("Fox Artist - Night Run")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        transition_acquisition(session, acquisition, AcquisitionState.RESOLVING, "Resolving")
        transition_acquisition(
            session, acquisition, AcquisitionState.WAITING_FOR_USER, "Resolved"
        )
        transition_acquisition(session, acquisition, AcquisitionState.ACQUIRING, "Contained browser opened")
        acquisition_id = acquisition.id
    downloaded = inbox / "album.zip"
    downloaded.write_bytes(b"completed-download")

    job_id = stage_next_waiting_download(database, configured)

    assert job_id is not None
    assert not downloaded.exists()
    assert (inbox / acquisition_id).is_dir()
    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        job = session.get(Job, job_id)
        assert acquisition is not None
        assert acquisition.state == AcquisitionState.VALIDATING.value
        assert job is not None
        assert job.source_reference == f"request:{acquisition_id}:album.zip"


RELEASE_ID = "f21c2200-85ae-4aaa-94d9-e80079a1e705"


def waiting_manifest_request(database: Database) -> str:
    """Create an acquiring browser request with resolved MusicBrainz edition."""
    with database.session() as session:
        acquisition = create_request_jobs(
            session,
            [parse_request_reference("Fox Artist - Night Run")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        acquisition.manifest_json = json.dumps(
            {
                "release_id": RELEASE_ID,
                "artist": "Fox Artist",
                "album_edition": {
                    "title": "Den Songs",
                    "date": "2024-10-15",
                    "country": "US",
                    "status": "Official",
                },
                "expected_tracks": [
                    {"title": "Night Run", "recording_id": "297dfc0d-5fec-7b20-1653-d1857ca4b580"},
                ],
                "musicbrainz_payload": {
                    "id": RELEASE_ID,
                    "title": "Den Songs",
                    "media": [{"tracks": [{"title": "Night Run"}]}],
                },
            }
        )
        acquisition.confidence = 98.0
        transition_acquisition(session, acquisition, AcquisitionState.RESOLVING, "Resolving")
        transition_acquisition(session, acquisition, AcquisitionState.WAITING_FOR_USER, "Resolved")
        transition_acquisition(session, acquisition, AcquisitionState.ACQUIRING, "Browser opened")
        return acquisition.id


def test_browser_handoff_with_musicbrainz_release_preserves_inbox_reference_and_is_idempotent(
    settings: Settings, tmp_path: Path
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    acquisition_id = waiting_manifest_request(database)
    file = inbox / "album.zip"
    file.write_bytes(b"finished-browser-download")

    job_id = stage_next_waiting_download(database, configured)

    assert job_id
    assert not file.exists()
    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        job = session.get(Job, job_id)
        release = session.scalar(select(ReleaseCandidate).where(ReleaseCandidate.job_id == job_id))
        artifact = session.scalar(
            select(AcquisitionArtifact).where(AcquisitionArtifact.acquisition_job_id == acquisition_id)
        )
        event = session.scalar(select(JobEvent).where(JobEvent.job_id == job_id))
        assert acquisition is not None
        assert acquisition.associated_import_job_id == job_id
        assert acquisition.state == AcquisitionState.VALIDATING.value
        assert job is not None
        assert job.source_reference == f"request:{acquisition_id}:album.zip"
        assert job.selected_release_id == RELEASE_ID
        assert job.match_confidence == 98.0
        assert release is not None and release.selected
        assert release.musicbrainz_release_id == RELEASE_ID
        assert release.track_count == 1
        assert artifact is not None and artifact.received_via == "SERVER_INBOX_AUTO"
        assert artifact.import_job_id == job_id
        assert event is not None
        assert json.loads(event.data_json or "{}")["inbox_file"] == "album.zip"

    assert stage_next_waiting_download(database, configured) is None
    with database.session() as session:
        assert len(session.scalars(select(Job)).all()) == 1
        assert len(session.scalars(select(ReleaseCandidate)).all()) == 1
        assert len(session.scalars(select(AcquisitionArtifact)).all()) == 1


def test_manifest_handoff_transaction_rollback_restores_file_then_retry_succeeds(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    acquisition_id = waiting_manifest_request(database)
    original = b"unique-browser-payload"
    (inbox / "album.zip").write_bytes(original)
    with monkeypatch.context() as patch:
        def reject_event(*args, **kwargs):
            raise RuntimeError("synthetic event insert failure")
        patch.setattr(inbox_automation, "add_event", reject_event)
        with pytest.raises(RuntimeError, match="synthetic event insert failure"):
            stage_next_waiting_download(database, configured)

    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        assert acquisition is not None
        assert acquisition.state == AcquisitionState.ACQUIRING.value
        assert acquisition.associated_import_job_id is None
        assert session.scalars(select(Job)).all() == []
        assert session.scalars(select(ReleaseCandidate)).all() == []
        assert session.scalars(select(AcquisitionArtifact)).all() == []

    recovered = list((inbox / acquisition_id).glob("recovered-*-album.zip"))
    assert len(recovered) == 1
    assert recovered[0].read_bytes() == original
    assert list(configured.jobs_dir.iterdir()) == []

    retry_id = stage_next_waiting_download(database, configured)
    assert retry_id is not None
    assert not recovered[0].exists()
    assert stage_next_waiting_download(database, configured) is None
    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        assert acquisition is not None and acquisition.associated_import_job_id == retry_id
        assert acquisition.state == AcquisitionState.VALIDATING.value
        assert len(session.scalars(select(Job)).all()) == 1
        assert len(session.scalars(select(ReleaseCandidate)).all()) == 1


def test_restore_oserror_does_not_hide_original_transaction_error(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    acquisition_id = waiting_manifest_request(database)
    (inbox / "album.zip").write_bytes(b"download-to-recover")
    def reject_event(*args, **kwargs):
        raise RuntimeError("synthetic database handoff failure")
    def reject_restore(*args, **kwargs):
        raise OSError(13, "synthetic restore permission failure")
    monkeypatch.setattr(inbox_automation, "add_event", reject_event)
    monkeypatch.setattr(inbox_automation, "_restore_staged_file", reject_restore)
    with pytest.raises(RuntimeError, match="synthetic database handoff failure"):
        stage_next_waiting_download(database, configured)

    with database.session() as session:
        acquisition = session.get(AcquisitionJob, acquisition_id)
        assert acquisition is not None
        assert acquisition.state == AcquisitionState.ACQUIRING.value
        assert acquisition.associated_import_job_id is None
        assert session.scalars(select(Job)).all() == []
        assert session.scalars(select(ReleaseCandidate)).all() == []
    staged = list(configured.jobs_dir.glob("*/incoming/source.zip"))
    assert len(staged) == 1
    assert staged[0].read_bytes() == b"download-to-recover"


def test_stage_oserror_before_database_write_leaves_acquisition_retryable(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured, database, inbox = configured_database(settings, tmp_path)
    acquisition_id = waiting_manifest_request(database)
    (inbox / "album.zip").write_bytes(b"retry-once-permissions-fixed")
    real_stage = inbox_automation.stage_inbox_file

    def reject_stage(*args, **kwargs):
        raise OSError(13, "synthetic unavailable download directory")

    with monkeypatch.context() as patch:
        patch.setattr(inbox_automation, "stage_inbox_file", reject_stage)
        with pytest.raises(OSError, match="synthetic unavailable"):
            stage_next_waiting_download(database, configured)
    assert (inbox / acquisition_id / "album.zip").read_bytes() == b"retry-once-permissions-fixed"
    with database.session() as session:
        assert session.get(AcquisitionJob, acquisition_id).associated_import_job_id is None
        assert session.scalars(select(Job)).all() == []

    assert stage_next_waiting_download(database, configured) is not None
