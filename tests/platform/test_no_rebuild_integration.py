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


# F-01: exercise the actual report-writing entrypoint (not a synthesized receipt).
# All Docker/network work is replaced by an isolated mock, never live R4.
def _run_receipt_writer(tmp_path, monkeypatch, *, fail=False, prior=False):
    import json
    import sys
    from scripts import no_rebuild_integration as integration

    lock = {
        "images": {name: {
            "ref": f"registry.invalid/{name}@sha256:{'a' * 64}",
        } for name in ("portal", "music", "media", "nginx")}
    }
    source = "b" * 40
    lock_path = tmp_path / "release-lock.json"
    lock_path.write_text(json.dumps(lock) + "\n", encoding="utf-8")
    report = tmp_path / "result" / "integration.json"
    if prior:
        report.parent.mkdir()
        report.write_text('{"previous":"immutable"}\n', encoding="utf-8")

    def simulate_pulled_integration(actual_lock, port):
        assert actual_lock == lock
        assert port == 18080
        if fail:
            raise RuntimeError("synthetic disposable pulled-image smoke failure")

    monkeypatch.setattr(integration, "exercise", simulate_pulled_integration)
    monkeypatch.setattr(integration, "RUNTIME", tmp_path / "isolated-runtime")
    monkeypatch.setattr(sys, "argv", [
        "no_rebuild_integration.py", "--lock", str(lock_path),
        "--report", str(report), "--source-sha", source,
        "--r4-run-id", "246",
    ])
    return integration, lock, lock_path, report, source


def _strict_json_document(path):
    import json

    def reject_duplicate(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Nonfinite JSON: " + value)

    # json.loads rejects any trailing JSON data (including literal backslash-n).
    return json.loads(path.read_bytes().decode("utf-8"),
                      object_pairs_hook=reject_duplicate,
                      parse_constant=reject_constant)


def test_actual_writer_emits_strict_r4_receipt(tmp_path, monkeypatch):
    import hashlib
    from scripts import r4_release_ready as consumer

    integration, lock, lock_path, report, source = _run_receipt_writer(
        tmp_path, monkeypatch)
    assert integration.main() == 0
    actual = _strict_json_document(report)
    assert report.read_bytes().endswith(b"\n")
    assert actual["lock_sha256"] == hashlib.sha256(lock_path.read_bytes()).hexdigest()
    assert actual["source_sha"] == source
    assert actual["r4_run_id"] == 246
    assert actual["images"] == {name: entry["ref"] for name, entry in lock["images"].items()}
    consumer.verify_integration(actual, lock, source, 246)
    assert actual["decision"] == "pass"
    assert actual["mode"] == "pulled-digest-no-build"


def test_actual_writer_never_reports_failed_integration(tmp_path, monkeypatch):
    integration, _, _, report, _ = _run_receipt_writer(
        tmp_path, monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="synthetic disposable"):
        integration.main()
    assert not report.exists()


def test_actual_writer_refuses_overwrite(tmp_path, monkeypatch):
    integration, _, _, report, _ = _run_receipt_writer(
        tmp_path, monkeypatch, prior=True)
    original = report.read_bytes()
    with pytest.raises(SystemExit):
        integration.main()
    assert report.read_bytes() == original
