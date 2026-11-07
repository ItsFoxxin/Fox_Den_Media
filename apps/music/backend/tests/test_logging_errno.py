"""Worker logging must provide actionable errno without sensitive paths."""
from __future__ import annotations

import json
import logging

from foxden_music.logging_config import JsonFormatter


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
