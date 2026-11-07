"""Worker logging must provide actionable errno without sensitive paths."""
from __future__ import annotations

import json
import logging

from foxden_music.logging_config import JsonFormatter
from foxden_music.handoff_diagnostics import handoff_operation, handoff_error_context


def test_json_error_exposes_only_numeric_errno_not_sensitive_path() -> None:
    handler = JsonFormatter()
    private_path = "/private/artist/tracks/secret.zip"
    try:
        raise OSError(36, "File name too long", private_path)
    except OSError:
        import sys
        exception_info = sys.exc_info()
    record = logging.LogRecord(
        name="foxden_music.worker",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Automatic server-download handoff failed",
        args=(),
        exc_info=exception_info,
    )
    payload = json.loads(handler.format(record))
    assert payload["exception_type"] == "OSError"
    assert payload["exception_errno"] == 36
    assert private_path not in json.dumps(payload)


def test_non_os_error_preserves_type_without_errno() -> None:
    try:
        raise AttributeError("a private title must stay hidden")
    except AttributeError:
        import sys
        exception_info = sys.exc_info()
    record = logging.LogRecord(
        name="foxden_music.worker",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Automatic server-download handoff failed",
        args=(),
        exc_info=exception_info,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["exception_type"] == "AttributeError"
    assert "exception_errno" not in payload
    assert "a private title" not in json.dumps(payload)


def _formatted_oserror(exc: OSError) -> dict:
    record = logging.LogRecord(
        name="foxden_music.worker",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Automatic server-download handoff failed",
        args=(),
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return json.loads(JsonFormatter().format(record))


def test_named_handoff_operation_is_exposed_without_path_or_message() -> None:
    private_path = "/private/music/secret-artist/album.zip"
    try:
        with handoff_operation("stage_file_move"):
            raise OSError(18, "Cross-device link", private_path)
    except OSError as error:
        payload = _formatted_oserror(error)
    else:
        raise AssertionError("Expected simulated OSError")
    assert payload["handoff_operation"] == "stage_file_move"
    assert payload["exception_errno"] == 18
    assert payload["exception_type"] == "OSError"
    assert private_path not in json.dumps(payload)
    assert "Cross-device link" not in json.dumps(payload)


def test_nested_handoff_context_preserves_innermost_label_and_error() -> None:
    error = OSError(13, "private path denied")
    try:
        with handoff_operation("stage_inbox_file"):
            with handoff_operation("stage_file_copy"):
                raise error
    except OSError as observed:
        assert observed is error
        assert handoff_error_context(observed) == {
            "handoff_operation": "stage_file_copy"
        }
    else:
        raise AssertionError("Expected simulated OSError")


def test_unknown_operation_cannot_inject_untrusted_log_data() -> None:
    private_path = "/private/artist/secret.zip"
    for label in (private_path, "stage_file_move\nprivate=secret", ""):
        try:
            with handoff_operation(label):
                raise OSError(13, private_path)
        except ValueError as error:
            assert str(error) == "Unknown handoff operation label"
        else:
            raise AssertionError("Unknown operation label was accepted")
    plain = OSError(13, private_path)
    assert "handoff_operation" not in _formatted_oserror(plain)
