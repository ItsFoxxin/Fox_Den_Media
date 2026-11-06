from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from foxden_music import healthcheck
from foxden_music.healthcheck import HealthcheckError, _require_non_root_runtime


@pytest.mark.parametrize(("uid", "gid"), [(0, 10001), (10001, 0)])
def test_runtime_wrapper_rejects_root_identity(monkeypatch, uid: int, gid: int) -> None:
    monkeypatch.setattr(healthcheck.os, "geteuid", lambda: uid, raising=False)
    monkeypatch.setattr(healthcheck.os, "getegid", lambda: gid, raising=False)
    with pytest.raises(HealthcheckError, match="effective"):
        _require_non_root_runtime()


def test_runtime_wrapper_accepts_non_root_identity(monkeypatch) -> None:
    monkeypatch.setattr(healthcheck.os, "geteuid", lambda: 10001, raising=False)
    monkeypatch.setattr(healthcheck.os, "getegid", lambda: 10001, raising=False)
    _require_non_root_runtime()


@pytest.mark.parametrize("url", [
    "https://example.com/health",
    "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd",
    "http://user:password@127.0.0.1/health",
])
def test_web_healthcheck_rejects_nonlocal_or_credentialed_destinations(monkeypatch, url: str) -> None:
    monkeypatch.setenv("HEALTHCHECK_WEB_URL", url)
    with pytest.raises(HealthcheckError, match="local HTTP URL"):
        healthcheck.check_web()


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def read(self, _limit: int) -> bytes:
        return b"ok"


class _Opener:
    def __init__(self, *, redirect: bool = False):
        self.redirect = redirect
        self.requests: list[str] = []

    def open(self, request: urllib.request.Request, timeout: int):
        assert timeout == 3
        self.requests.append(request.full_url)
        if self.redirect:
            raise urllib.error.HTTPError(
                request.full_url, 302, "Found",
                {"Location": "https://example.invalid/should-not-be-requested"}, io.BytesIO(),
            )
        return _Response()


def test_web_healthcheck_succeeds_locally_without_environment_proxy(
    monkeypatch,
) -> None:
    url = "http://127.0.0.1:8000/health"
    opener = _Opener()
    monkeypatch.setenv("HEALTHCHECK_WEB_URL", url)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.invalid:8080")
    monkeypatch.setattr(healthcheck, "_local_health_opener", lambda: opener)
    healthcheck.check_web()
    assert opener.requests == [url]


def test_web_healthcheck_rejects_external_redirect(
    monkeypatch,
) -> None:
    url = "http://127.0.0.1:8000/redirect"
    opener = _Opener(redirect=True)
    monkeypatch.setenv("HEALTHCHECK_WEB_URL", url)
    monkeypatch.setattr(healthcheck, "_local_health_opener", lambda: opener)
    with pytest.raises(HealthcheckError, match="unavailable"):
        healthcheck.check_web()
    assert opener.requests == [url]


def test_local_health_opener_disables_proxies_and_redirects(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.invalid:8080")
    captured = []
    sentinel = object()
    monkeypatch.setattr(urllib.request, "build_opener",
                        lambda *handlers: captured.extend(handlers) or sentinel)
    assert healthcheck._local_health_opener() is sentinel
    proxy = next(handler for handler in captured if isinstance(handler, urllib.request.ProxyHandler))
    redirect = next(handler for handler in captured
                    if isinstance(handler, healthcheck._NoRedirectHandler))
    assert proxy.proxies == {}
    assert redirect.redirect_request(None, None, 302, "Found", {},
                                     "https://example.invalid/") is None



def test_file_secret_import_removes_file_variable_after_success(monkeypatch, tmp_path) -> None:
    secret = tmp_path / "csrf"
    secret.write_text("x" * 40, encoding="utf-8")
    monkeypatch.delenv("CSRF_SECRET", raising=False)
    monkeypatch.setenv("CSRF_SECRET_FILE", str(secret))

    healthcheck.import_file_secrets()

    assert healthcheck.os.environ["CSRF_SECRET"] == "x" * 40
    assert "CSRF_SECRET_FILE" not in healthcheck.os.environ


def test_explicit_secret_conflict_is_not_silently_overridden(monkeypatch, tmp_path) -> None:
    secret = tmp_path / "csrf"
    secret.write_text("file-value", encoding="utf-8")
    monkeypatch.setenv("CSRF_SECRET", "explicit-value")
    monkeypatch.setenv("CSRF_SECRET_FILE", str(secret))

    healthcheck.import_file_secrets()

    assert healthcheck.os.environ["CSRF_SECRET"] == "explicit-value"
    assert healthcheck.os.environ["CSRF_SECRET_FILE"] == str(secret)
