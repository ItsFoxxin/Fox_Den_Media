from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
THEMES = (
    ROOT / "apps/portal/src/foxden_portal/static/denkit.css",
    ROOT / "apps/music/backend/src/foxden_music/static/denkit.css",
    ROOT / "apps/media/app/static/denkit.css",
)
TOKENS = {
    "den-midnight": "#0b1423",
    "den-slate": "#25384b",
    "den-mint": "#97e7ca",
    "den-coral": "#f68d91",
    "den-amber": "#f5ad66",
    "den-cream": "#f7f5e9",
    "den-raised": "#142335",
    "den-border": "#36495d",
    "den-muted": "#afc0d1",
    "den-critical": "#ef5261",
}


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_every_application_exposes_canonical_denkit_tokens() -> None:
    for theme in THEMES:
        css = theme.read_text(encoding="utf-8").lower()
        for name, value in TOKENS.items():
            assert re.search(rf"--{name}\s*:\s*{value}\b", css), f"{theme}: {name}"
        assert ":focus-visible" in css
        assert "prefers-reduced-motion" in css


def test_primary_text_and_bright_controls_meet_wcag_aa() -> None:
    pairs = (
        (TOKENS["den-cream"], TOKENS["den-midnight"]),
        (TOKENS["den-cream"], TOKENS["den-raised"]),
        (TOKENS["den-muted"], TOKENS["den-midnight"]),
        (TOKENS["den-midnight"], TOKENS["den-coral"]),
        (TOKENS["den-midnight"], TOKENS["den-mint"]),
        (TOKENS["den-midnight"], TOKENS["den-amber"]),
        (TOKENS["den-critical"], TOKENS["den-midnight"]),
    )
    for foreground, background in pairs:
        assert _contrast(foreground, background) >= 4.5, (foreground, background)


def test_denkit_layers_are_loaded_after_existing_component_styles() -> None:
    portal = (ROOT / "apps/portal/src/foxden_portal/templates/base.html").read_text(encoding="utf-8")
    music = (ROOT / "apps/music/backend/src/foxden_music/templates/base.html").read_text(encoding="utf-8")
    media = (ROOT / "apps/media/app/static/index.html").read_text(encoding="utf-8")
    media_app = (ROOT / "apps/media/app/main.py").read_text(encoding="utf-8")
    assert portal.index("portal.css") < portal.index("denkit.css")
    assert music.index("workspace.css") < music.index("denkit.css")
    assert media.index("style.css") < media.index("denkit.css")
    assert 'href="../assets/denkit.css"' in media_app


def test_jellyfin_theme_is_isolated_and_mascot_is_packaged() -> None:
    css = (ROOT / "apps/portal/src/foxden_portal/static/jellyfin-midnight.css").read_text(encoding="utf-8").lower()
    mascot = ROOT / "apps/portal/src/foxden_portal/static/fox-den-mascot.png"
    for name, value in TOKENS.items():
        assert re.search(rf"--{name}\s*:\s*{value}\b", css), name
    assert "@import url('/foxden-theme.css')" in css
    assert "prefers-reduced-motion" in css
    assert mascot.is_file() and mascot.stat().st_size > 100_000


def test_media_navigation_uses_explicit_renderer_dispatch() -> None:
    script = (ROOT / "apps/media/app/static/app.js").read_text(encoding="utf-8")
    assert "switch(tab)" in script
    assert "}[tab])()" not in script
