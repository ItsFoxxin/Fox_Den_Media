"""Firefox image integrity and optional browser isolation regression tests."""
from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = "jlesage/firefox:v26.09.1@sha256:302aa068dcfa46a2d248771c998f67377383554df8940252caef42b99c13eb65"


@pytest.mark.parametrize("path", [
    "deploy/compose.yaml",
    "deploy/examples/full-managed.env.example",
    "deploy/examples/ugreen-rehearsal.env.example",
])
def test_browser_image_is_a_frozen_supported_digest(path: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    assert EXPECTED in content
    assert "jlesage/firefox:v25.09.2" not in content


def test_browser_is_optional_and_does_not_publish_a_port() -> None:
    compose = yaml.safe_load((ROOT / "deploy/compose.yaml").read_text(encoding="utf-8"))
    browser = compose["services"]["download-browser"]
    assert browser["profiles"] == ["browser"]
    assert browser["image"] == "${BROWSER_IMAGE:-" + EXPECTED + "}"
    assert browser["expose"] == ["5800"]
    assert "ports" not in browser
    assert browser["security_opt"] == ["no-new-privileges:true"]
    assert browser["networks"] == ["platform", "outbound"]
    assert browser["environment"]["USER_ID"] == "${FOXDEN_PUID:-10001}"
    assert browser["environment"]["GROUP_ID"] == "${FOXDEN_PGID:-10001}"
    assert browser["environment"]["FF_PREF_DOWNLOAD_DIR"] == 'browser.download.dir="/downloads"'
    assert not re.search(r"(?m)^\s*privileged\s*:", str(browser))


def test_browser_mounts_are_only_configuration_and_shared_downloads() -> None:
    browser = yaml.safe_load((ROOT / "deploy/compose.yaml").read_text(encoding="utf-8"))["services"]["download-browser"]
    mounts = {volume["target"]: volume for volume in browser["volumes"]}
    assert set(mounts) == {"/config", "/downloads"}
    assert all(mount["bind"]["create_host_path"] is False for mount in mounts.values())
