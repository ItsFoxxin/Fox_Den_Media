from __future__ import annotations

import logging
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .acquisition import transition_acquisition
from .config import Settings
from .database import Database
from .enums import AcquisitionProvider, AcquisitionState, JobKind, JobState, SourceType
from .intake import IntakeError, cleanup_staged_job, list_download_inbox, stage_inbox_file
from .handoff_diagnostics import handoff_operation
from .models import AcquisitionArtifact, AcquisitionJob, Job, ReleaseCandidate, utcnow
from .state import add_event


logger = logging.getLogger(__name__)

# Each failed handoff is eligible for retry. Never prepend another recovery
# prefix to an already recovered filename: repeated failures otherwise cause
# ENAMETOOLONG on filesystems with 255-byte name limits.
_RECOVERY_PREFIXES = re.compile(r"^(?:recovered-[0-9a-f]{8}-)+")
_RECOVERY_FILENAME_MAX_BYTES = 255


def _recovery_name(display_name: str) -> str:
    """Return a bounded, extension-preserving unique recovery filename."""
    original = _RECOVERY_PREFIXES.sub("", display_name)
    if not original:
        original = "download"
    prefix = f"recovered-{uuid.uuid4().hex[:8]}-"
    allowance = _RECOVERY_FILENAME_MAX_BYTES - len(prefix.encode("utf-8"))
    if len(original.encode("utf-8")) > allowance:
        suffix = Path(original).suffix
        stem = original[:-len(suffix)] if suffix else original
        stem_allowance = max(1, allowance - len(suffix.encode("utf-8")))
        stem = stem.encode("utf-8")[:stem_allowance].decode("utf-8", errors="ignore")
        original = (stem or "download") + suffix
    return prefix + original


def _epoch(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _restore_staged_file(
    settings: Settings,
    job_id: str,
    staged_path: Path,
    display_name: str,
) -> None:
    """Return a moved file to the inbox after a database handoff race/failure."""

    if settings.download_inbox_move_files and staged_path.exists() and settings.download_inbox_dir:
        with handoff_operation("restore_inbox_inspection"):
            root = settings.download_inbox_dir.resolve(strict=True)
        destination = root / _recovery_name(display_name)
        with handoff_operation("restore_staged_file_move"):
            shutil.move(str(staged_path), str(destination))
    with handoff_operation("restore_staged_cleanup"):
        cleanup_staged_job(settings, job_id)


def _stat_staged_bytes(path: Path, *, operation: str) -> int:
    with handoff_operation(operation):
        return path.stat().st_size


def stage_next_waiting_download(database: Database, settings: Settings) -> str | None:
    """Attach one settled inbox file to the single acquisition awaiting a download.

    The browser flow intentionally permits only one WAITING_FOR_DOWNLOAD request at
    a time. Files older than that request are ignored so an unrelated inbox item is
    never silently assigned to a new acquisition.
    """

    if not settings.download_inbox_auto_import or settings.download_inbox_dir is None:
        return None

    with database.session() as session:
        waiting = session.scalars(
            select(AcquisitionJob)
            .where(
                AcquisitionJob.state.in_(
                    (AcquisitionState.ACQUIRING.value, AcquisitionState.WAITING_FOR_DOWNLOAD.value)
                ),
                AcquisitionJob.associated_import_job_id.is_(None),
            )
            .order_by(AcquisitionJob.updated_at, AcquisitionJob.created_at)
            .limit(1)
        ).all()
        if not waiting:
            return None
        acquisition = waiting[0]
        acquisition_id = acquisition.id
        download_started_epoch = _epoch(acquisition.updated_at)
        provider = acquisition.provider
        is_music_request = acquisition.query_text is not None

    effective_settings = settings
    request_inbox: Path | None = None
    if provider == AcquisitionProvider.FILESYSTEM_DROP.value or is_music_request:
        request_inbox = settings.download_inbox_dir / acquisition_id
        with handoff_operation("request_inbox_mkdir"):
            request_inbox.mkdir(mode=0o750, parents=True, exist_ok=True)
        effective_settings = settings.model_copy(update={"download_inbox_dir": request_inbox})

    # Firefox writes to the shared /downloads mount. For a v2.5 browser request,
    # route exactly one settled top-level file into that request's private
    # directory before the normal request-scoped watcher and importer see it.
    if (
        is_music_request
        and provider == AcquisitionProvider.MANUAL_BROWSER.value
        and request_inbox is not None
    ):
        top_level_settings = settings.model_copy(
            update={"download_inbox_recursive": False}
        )
        try:
            top_level = [
                item
                for item in list_download_inbox(top_level_settings)
                if item.ready and item.modified_at_epoch >= download_started_epoch - 2
            ]
        except IntakeError:
            logger.exception("Automatic browser download routing failed")
            return None
        if top_level:
            routed = min(
                top_level,
                key=lambda item: (item.modified_at_epoch, item.display_name.lower()),
            )
            with handoff_operation("route_download_inspection"):
                source = (settings.download_inbox_dir / routed.relative_path).resolve(strict=True)
                root = settings.download_inbox_dir.resolve(strict=True)
            if source.parent != root:
                logger.error("Refused to route a browser download outside the inbox root")
                return None
            destination = request_inbox / source.name
            if destination.exists():
                logger.error("Refused to overwrite an existing request download")
                return None
            try:
                with handoff_operation("route_download_rename"):
                    source.rename(destination)
            except OSError:
                logger.exception("Could not isolate the browser download for its request")
                return None

    try:
        candidates = [
            item
            for item in list_download_inbox(effective_settings)
            if item.ready and item.modified_at_epoch >= download_started_epoch - 2
        ]
    except IntakeError:
        logger.exception("Automatic acquisition inbox scan failed")
        return None
    if not candidates:
        return None
    inbox_file = min(candidates, key=lambda item: (item.modified_at_epoch, item.display_name.lower()))

    try:
        with handoff_operation("stage_inbox_file"):
            job_id, staged_path, display_name = stage_inbox_file(inbox_file.relative_path, effective_settings)
    except IntakeError:
        return None

    try:
        with database.session() as session:
            acquisition = session.get(AcquisitionJob, acquisition_id)
            if (
                acquisition is None
                or acquisition.state not in {
                    AcquisitionState.ACQUIRING.value,
                    AcquisitionState.WAITING_FOR_DOWNLOAD.value,
                }
                or acquisition.associated_import_job_id is not None
            ):
                raise RuntimeError("Acquisition changed before the inbox file could be attached")

            job_root = settings.jobs_dir / job_id
            import_job = Job(
                id=job_id,
                kind=JobKind.ALBUM_IMPORT.value,
                source_type=(
                    SourceType.MUSIC_REQUEST.value
                    if acquisition.query_text
                    else SourceType.INCOMING.value
                ),
                state=JobState.QUEUED.value,
                display_name=display_name,
                source_filename=display_name,
                source_relative_path=staged_path.relative_to(job_root).as_posix(),
                source_reference=(
                    f"request:{acquisition.id}:{inbox_file.relative_path}"
                    if acquisition.query_text
                    else f"inbox:{inbox_file.relative_path}"
                ),
            )
            session.add(import_job)
            session.flush()
            if acquisition.manifest_json:
                manifest = json.loads(acquisition.manifest_json)
                release_id = manifest.get("release_id")
                payload = manifest.get("musicbrainz_payload")
                if release_id and isinstance(payload, dict):
                    edition = manifest.get("album_edition") or {}
                    release_candidate = ReleaseCandidate(
                        job_id=job_id,
                        musicbrainz_release_id=str(release_id),
                        title=str(edition.get("title") or acquisition.display_title),
                        artist_credit=str(manifest.get("artist") or acquisition.artist or ""),
                        release_date=edition.get("date"),
                        country=edition.get("country"),
                        status=edition.get("status"),
                        disambiguation=edition.get("disambiguation"),
                        media_summary=None,
                        track_count=len(manifest.get("expected_tracks") or []),
                        source_score=float(acquisition.confidence or 0),
                        score=float(acquisition.confidence or 0),
                        payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        selected=True,
                    )
                    session.add(release_candidate)
                    import_job.selected_release_id = str(release_id)
                    import_job.match_confidence = acquisition.confidence
            now = utcnow()
            acquisition.associated_import_job_id = job_id
            session.add(
                AcquisitionArtifact(
                    acquisition_job_id=acquisition.id,
                    import_job_id=job_id,
                    received_via="SERVER_INBOX_AUTO",
                    state="HANDED_OFF",
                    display_filename=display_name,
                    stored_relative_path=staged_path.relative_to(settings.staging_dir).as_posix(),
                    byte_size=_stat_staged_bytes(staged_path, operation="staged_artifact_stat"),
                    handed_off_at=now,
                )
            )
            if acquisition.query_text:
                transition_acquisition(
                    session,
                    acquisition,
                    AcquisitionState.VALIDATING,
                    "Completed download isolated in request staging; validation queued",
                )
            else:
                transition_acquisition(session, acquisition, AcquisitionState.FILE_RECEIVED, "Completed server download detected and safely staged")
                transition_acquisition(session, acquisition, AcquisitionState.IMPORT_STARTED, "Automatic server-inbox import queued")
            add_event(
                session,
                import_job,
                "Server download automatically matched to its waiting acquisition",
                data={
                    "acquisition_job_id": acquisition.id,
                    "inbox_file": inbox_file.relative_path,
                    "size": _stat_staged_bytes(staged_path, operation="staged_event_stat"),
                },
            )
        return job_id
    except BaseException:
        try:
            _restore_staged_file(effective_settings, job_id, staged_path, display_name)
        except OSError:
            # Do not mask the transaction failure with a second filesystem
            # error. _restore_staged_file leaves staging intact if its move
            # fails, allowing an operator to recover the file safely.
            logger.exception(
                "Could not recover staged download after database handoff failure",
                extra={"job_id": job_id, "acquisition_id": acquisition_id},
            )
        raise
