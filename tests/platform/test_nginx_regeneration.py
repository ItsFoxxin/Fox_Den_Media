"""Regeneration security and bind-mount inode regression coverage."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import foxden


def fixture_values(tmp_path: Path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "ingress-auth").write_text("synthetic-" + ("x" * 48))
    return {
        "FOXDEN_SECRETS_DIR": str(secrets),
        "FOXDEN_RUNTIME_DIR": str(tmp_path / "runtime"),
        "FOXDEN_PUID": str(os.getuid()),
        "FOXDEN_PGID": str(os.getgid()),
    }


def test_render_is_private_owned_and_preserves_inode_if_unchanged(tmp_path):
    values = fixture_values(tmp_path)
    target = foxden.render_gateway(values)
    first = target.stat()
    assert first.st_uid == os.getuid() and first.st_gid == os.getgid()
    assert first.st_mode & 0o777 == 0o600
    assert foxden.render_gateway(values) == target
    assert target.stat().st_ino == first.st_ino
    assert not list(target.parent.glob(".nginx.conf.*"))


def test_changed_content_is_atomic_and_replaces_inode(tmp_path):
    values = fixture_values(tmp_path)
    target = foxden.render_gateway(values)
    original = target.read_text()
    first_inode = target.stat().st_ino
    (Path(values["FOXDEN_SECRETS_DIR"]) / "ingress-auth").write_text("changed-" + ("y" * 48))
    foxden.render_gateway(values)
    assert target.read_text() != original
    assert target.stat().st_ino != first_inode
    assert target.stat().st_mode & 0o777 == 0o600


def test_failure_before_replace_preserves_previous_config(tmp_path, monkeypatch):
    values = fixture_values(tmp_path)
    target = foxden.render_gateway(values)
    before = target.read_bytes()
    (Path(values["FOXDEN_SECRETS_DIR"]) / "ingress-auth").write_text("changed-" + ("z" * 48))
    def denied(*args, **kwargs):
        raise PermissionError("synthetic permission denied")
    monkeypatch.setattr(foxden.os, "fchown", denied)
    with pytest.raises(foxden.ConfigError, match="ownership"):
        foxden.render_gateway(values)
    assert target.read_bytes() == before
    assert not list(target.parent.glob(".nginx.conf.*"))


def test_refuses_symlinked_nginx_config(tmp_path):
    values = fixture_values(tmp_path)
    runtime = Path(values["FOXDEN_RUNTIME_DIR"])
    runtime.mkdir()
    destination = tmp_path / "important"
    destination.write_text("keep")
    (runtime / "nginx.conf").symlink_to(destination)
    with pytest.raises(foxden.ConfigError, match="symlink"):
        foxden.render_gateway(values)
    assert destination.read_text() == "keep"


def test_compose_dry_run_has_no_implicit_execution(tmp_path):
    args = foxden.compose_command("music", tmp_path / ".env", browser=False, action="up")
    assert args[-2:] == ["up", "-d"]
    assert "--force-recreate" not in args


@pytest.mark.parametrize("command", [
    ["validate", "music"],
    ["deploy", "music"],
    ["stop", "music"],
])
def test_preflight_and_dry_runs_never_render(tmp_path, monkeypatch, command):
    values = fixture_values(tmp_path)
    monkeypatch.setattr(foxden, "load_env", lambda path: values)
    monkeypatch.setattr(foxden, "validate", lambda *args, **kw: None)
    monkeypatch.setattr(foxden, "render_gateway", lambda *args, **kw: pytest.fail("Unexpected config write"))
    monkeypatch.setattr(foxden.subprocess, "run", lambda *args, **kw: type("Result", (), {"returncode": 0})())
    monkeypatch.setattr(sys, "argv", ["foxden", *command, "--env", str(tmp_path / "fake.env")])
    assert foxden.main() == 0
    assert not Path(values["FOXDEN_RUNTIME_DIR"]).exists()


def test_authorized_deploy_recreates_only_ingress_after_success(tmp_path, monkeypatch):
    values = fixture_values(tmp_path)
    calls = []
    monkeypatch.setattr(foxden, "load_env", lambda path: values)
    monkeypatch.setattr(foxden, "validate", lambda *args, **kw: None)
    monkeypatch.setattr(foxden, "render_gateway", lambda *args, **kw: tmp_path / "runtime" / "nginx.conf")
    def fake_run(command, **kw):
        calls.append(command)
        return type("Result", (), {"returncode": 0})()
    monkeypatch.setattr(foxden.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["foxden", "deploy", "music", "--env", str(tmp_path / ".env"), "--execute"])
    assert foxden.main() == 0
    assert len(calls) == 2
    assert calls[0][-2:] == ["up", "-d"]
    assert calls[1][-5:] == ["up", "-d", "--no-deps", "--force-recreate", "ingress"]
    assert calls[1].count("ingress") == 1


def test_failed_deploy_does_not_recreate_ingress(tmp_path, monkeypatch):
    values = fixture_values(tmp_path)
    calls = []
    monkeypatch.setattr(foxden, "load_env", lambda path: values)
    monkeypatch.setattr(foxden, "validate", lambda *args, **kw: None)
    monkeypatch.setattr(foxden, "render_gateway", lambda *args, **kw: tmp_path / "runtime" / "nginx.conf")
    def fake_run(command, **kw):
        calls.append(command)
        return type("Result", (), {"returncode": 1})()
    monkeypatch.setattr(foxden.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["foxden", "deploy", "music", "--env", str(tmp_path / ".env"), "--execute"])
    assert foxden.main() == 1
    assert len(calls) == 1


def test_config_error_never_executes_compose(tmp_path, monkeypatch, capsys):
    """A failed validation/render must never fall through to a Docker action."""
    values = fixture_values(tmp_path)
    calls = []
    monkeypatch.setattr(foxden, "load_env", lambda path: values)
    monkeypatch.setattr(foxden, "validate", lambda *args, **kw: None)
    monkeypatch.setattr(
        foxden,
        "render_gateway",
        lambda *args, **kw: (_ for _ in ()).throw(foxden.ConfigError("synthetic render failure")),
    )
    monkeypatch.setattr(foxden.subprocess, "run", lambda *args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(
        sys, "argv", ["foxden", "deploy", "music", "--env", str(tmp_path / ".env"), "--execute"]
    )

    assert foxden.main() == 2
    assert calls == []
    assert "synthetic render failure" in capsys.readouterr().err


def test_optional_owner_check_runs_before_secret_bearing_render(tmp_path, monkeypatch):
    values = fixture_values(tmp_path)
    calls = []
    monkeypatch.setattr(foxden, "load_env", lambda path: values)
    monkeypatch.setattr(foxden, "validate", lambda *args, **kw: None)
    monkeypatch.setattr(foxden, "inspect_secret_owners", lambda *args, **kw: calls.append("inspect"))
    monkeypatch.setattr(foxden, "render_gateway", lambda *args, **kw: calls.append("render") or tmp_path / "nginx.conf")
    monkeypatch.setattr(
        foxden.subprocess, "run", lambda *args, **kw: type("Result", (), {"returncode": 0})()
    )
    monkeypatch.setattr(
        sys, "argv",
        ["foxden", "config", "music", "--env", str(tmp_path / ".env"), "--check-service-owners"],
    )

    assert foxden.main() == 0
    assert calls == ["inspect", "render"]
