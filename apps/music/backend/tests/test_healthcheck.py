from __future__ import annotations

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
