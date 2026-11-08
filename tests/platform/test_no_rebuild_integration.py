"""R4 release Compose transform must never fall back to local builds."""
import copy
import pytest
from scripts.no_rebuild_integration import render_no_build

def test_render_selects_exact_music_digest_and_removes_build():
    images = {name: {"ref": f"example.invalid/{name}@sha256:{'a'*64}"}
              for name in ("portal", "music", "media", "nginx")}
    cfg = {"services": {
        name: {"image": "local:latest", "build": {"context": "."}}
        for name in ("volume-init", "ingress", "portal", "music", "music-worker", "media")
    }}
    result = render_no_build(copy.deepcopy(cfg), images)
    assert not any("build" in service for service in result["services"].values())
    assert result["services"]["music"]["image"] == result["services"]["music-worker"]["image"]
    assert result["services"]["ingress"]["image"] == images["nginx"]["ref"]

def test_reject_unexpected_compose_services():
    images = {key: {"ref": key} for key in ("portal", "music", "media", "nginx")}
    with pytest.raises(ValueError, match="Unexpected"):
        render_no_build({"services": {"portal": {}}}, images)

def test_reject_missing_pinned_upstream():
    cfg = {"services": {service: {} for service in (
        "volume-init", "ingress", "portal", "music", "music-worker", "media")}}
    with pytest.raises(ValueError, match="Required image absent"):
        render_no_build(cfg, {"portal": {"ref": "abc"}})
