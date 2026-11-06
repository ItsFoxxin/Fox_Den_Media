from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("module_name,relative", (
    ("integration_stack_security_test", "scripts/integration_stack.py"),
    ("smoke_portal_ingress_security_test", "scripts/smoke_portal_ingress.py"),
))
def test_disposable_stack_secrets_are_created_privately(tmp_path: Path, module_name: str, relative: str) -> None:
    module = _load(module_name, relative)
    target = tmp_path / "secret"
    module.write_private_text(target, "synthetic-secret")
    assert target.read_text(encoding="utf-8") == "synthetic-secret"
    if os.name != "nt":
        assert target.stat().st_mode & 0o077 == 0


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "O_NOFOLLOW"),
                    reason="O_NOFOLLOW symlink protection is POSIX-specific")
def test_private_writer_refuses_symlink_target(tmp_path: Path) -> None:
    module = _load("integration_stack_symlink_test", "scripts/integration_stack.py")
    destination = tmp_path / "destination"
    destination.write_text("preserve", encoding="utf-8")
    link = tmp_path / "secret"
    link.symlink_to(destination)
    with pytest.raises(OSError):
        module.write_private_text(link, "replacement")
    assert destination.read_text(encoding="utf-8") == "preserve"
