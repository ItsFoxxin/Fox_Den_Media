"""Bounded, path-free operation labels for investigating Music inbox I/O errors.

These labels are maintained in source code, never derived from provider data,
filenames, exception messages or filesystem paths.
"""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

HANDOFF_OPERATIONS = frozenset({
    "request_inbox_mkdir",
    "route_download_inspection",
    "route_download_rename",
    "stage_source_inspection",
    "stage_directory_mkdir",
    "stage_file_move",
    "stage_file_copy",
    "stage_file_chmod",
    "stage_inbox_file",
    "stage_cleanup",
    "staged_artifact_stat",
    "staged_event_stat",
    "restore_inbox_inspection",
    "restore_staged_file_move",
    "restore_staged_cleanup",
})

_ATTRIBUTE = "_foxden_handoff_operation"


def tag_handoff_oserror(error: OSError, operation: str) -> None:
    """Attach a fixed label without replacing the original OSError or traceback."""
    if operation not in HANDOFF_OPERATIONS:
        raise ValueError("Unknown handoff operation label")
    # Keep the innermost location when an outer caller adds fallback context.
    if getattr(error, _ATTRIBUTE, None) is None:
        setattr(error, _ATTRIBUTE, operation)


def handoff_error_context(error: BaseException) -> dict[str, str]:
    """Return only vetted labels, safe to include in structured worker logs."""
    if not isinstance(error, OSError):
        return {}
    operation = getattr(error, _ATTRIBUTE, None)
    return {"handoff_operation": operation} if operation in HANDOFF_OPERATIONS else {}


@contextmanager
def handoff_operation(operation: str) -> Iterator[None]:
    """Tag a filesystem failure at its specific operation; preserve traceback."""
    if operation not in HANDOFF_OPERATIONS:
        raise ValueError("Unknown handoff operation label")
    try:
        yield
    except OSError as exc:
        tag_handoff_oserror(exc, operation)
        raise
