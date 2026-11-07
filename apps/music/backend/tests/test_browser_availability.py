"""RB-04: bounded browser reachability without proxies or redirects."""
from __future__ import annotations

import pytest
from foxden_music import web


@pytest.mark.parametrize("status,expected", [
    (200, True), (204, True), (302, True),
    (401, False), (403, False), (503, False),
])
def test_browser_http_probe_status_is_bounded_and_redirect_free(monkeypatch, status, expected):
    observed = []
    class FakeConnection:
        def __init__(self, host, port, timeout):
            observed.append(("connect", host, port, timeout))
        def request(self, method, path):
            observed.append(("request", method, path))
        def getresponse(self):
            return type("Response", (), {"status": status})()
        def close(self):
            observed.append(("close",))
    monkeypatch.setattr(web, "HTTPConnection", FakeConnection)
    assert web._browser_server_ready() is expected
    assert observed == [
        ("connect", "download-browser", 5800, 0.5),
        ("request", "HEAD", "/"),
        ("close",),
    ]


def test_browser_http_probe_fails_closed_on_connection_error(monkeypatch):
    closed = []
    class Unreachable:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("download-browser", 5800, 0.5)
        def request(self, method, path):
            raise OSError("Firefox is stopped")
        def close(self):
            closed.append(True)
    monkeypatch.setattr(web, "HTTPConnection", Unreachable)
    assert web._browser_server_ready() is False
    assert closed


def test_browser_http_probe_fails_closed_on_malformed_http(monkeypatch):
    from http.client import BadStatusLine
    closed = []
    class Malformed:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("download-browser", 5800, 0.5)
        def request(self, method, path):
            raise BadStatusLine("invalid HTTP response")
        def close(self):
            closed.append(True)
    monkeypatch.setattr(web, "HTTPConnection", Malformed)
    assert web._browser_server_ready() is False
    assert closed
