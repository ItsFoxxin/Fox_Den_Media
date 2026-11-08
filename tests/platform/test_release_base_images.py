"""Offline checks for immutable base-image build prerequisites."""
import pytest
from scripts.check_release_base_images import BaseImageError, DOCKERFILES, verify_base_images

DIGEST = "a" * 64

def seed(tmp_path, digest=DIGEST):
    for path in DOCKERFILES:
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"FROM python:3.12.13-slim-bookworm@sha256:{digest}\n")

def test_same_reviewed_digest_for_all_three(tmp_path):
    seed(tmp_path)
    assert verify_base_images(tmp_path) == DIGEST

@pytest.mark.parametrize("bad", [
    "FROM python:3.12.13-slim-bookworm\n",
    "FROM python:3.12.13-slim-bookworm:latest\n",
    "FROM python:latest@sha256:" + "a" * 64 + "\n",
    "FROM python:3.12.13-slim-bookworm@sha256:bad\n",
    "FROM ubuntu:24.04@sha256:" + "a" * 64 + "\n",
    "ARG TAG=python:3.12.13-slim-bookworm\nFROM $TAG\n",
    "FROM python:3.12.13-slim-bookworm@sha256:" + "a" * 64 +
      "\nFROM alpine:3.22\n",
])
def test_mutable_or_unapproved_base_fails(tmp_path, bad):
    seed(tmp_path)
    (tmp_path / DOCKERFILES[0]).write_text(bad)
    with pytest.raises(BaseImageError):
        verify_base_images(tmp_path)

def test_different_digests_fail(tmp_path):
    seed(tmp_path)
    (tmp_path / DOCKERFILES[1]).write_text(
        "FROM python:3.12.13-slim-bookworm@sha256:" + "f" * 64 + "\n")
    with pytest.raises(BaseImageError, match="share"):
        verify_base_images(tmp_path)
