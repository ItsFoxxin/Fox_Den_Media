"""RB-04: optional Firefox must not be advertised by default."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "deploy/compose.yaml").read_text(encoding="utf-8"))


def test_browser_profile_and_music_link_are_separate_options():
    assert COMPOSE["x-music-environment"]["REMOTE_BROWSER_URL"] == "${REMOTE_BROWSER_URL:-}"
    browser = COMPOSE["services"]["download-browser"]
    assert browser["profiles"] == ["browser"]
    assert "ports" not in browser


def test_browser_direct_compose_examples_are_explicit():
    for filename in ("full-managed.env.example", "ugreen-rehearsal.env.example"):
        text = (ROOT / "deploy/examples" / filename).read_text(encoding="utf-8")
        assert "REMOTE_BROWSER_URL=/server-browser/" in text
