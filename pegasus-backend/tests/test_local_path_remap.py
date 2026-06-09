# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T10:46:43Z
# --- END GENERATED FILE METADATA ---

"""Tests for Docker host ↔ container local path translation."""

from __future__ import annotations

from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.local_paths import (
    compute_file_pair_key_for_settings,
    default_browse_path,
    resolve_local_path_on_disk,
    to_container_path,
    to_display_path,
)


def _settings(**overrides: object) -> Settings:
    base = {
        "validation_local_path_host_prefix": "/home/user/Pegasus/test-data",
        "validation_local_path_container_prefix": "/data/pegasus",
        "validation_local_path_default_browse": "/data/pegasus",
    }
    base.update(overrides)
    return Settings(**base)


def test_to_container_path_rewrites_host_prefix() -> None:
    settings = _settings()
    assert to_container_path(
        "/home/user/Pegasus/test-data/source.csv",
        settings,
    ) == "/data/pegasus/source.csv"


def test_to_display_path_rewrites_container_prefix() -> None:
    settings = _settings()
    assert to_display_path("/data/pegasus/target.csv", settings) == (
        "/home/user/Pegasus/test-data/target.csv"
    )


def test_pair_key_matches_host_and_container_aliases() -> None:
    settings = _settings()
    host_src = "/home/user/Pegasus/test-data/a.csv"
    host_tgt = "/home/user/Pegasus/test-data/b.csv"
    ctr_src = "/data/pegasus/a.csv"
    ctr_tgt = "/data/pegasus/b.csv"
    assert compute_file_pair_key_for_settings(host_src, host_tgt, settings) == (
        compute_file_pair_key_for_settings(ctr_src, ctr_tgt, settings)
    )


def test_resolve_falls_back_to_host_path_when_container_mount_missing(tmp_path: Path) -> None:
    host_root = tmp_path / "home" / "user"
    host_root.mkdir(parents=True)
    csv_file = host_root / "file.csv"
    csv_file.write_text("a\n", encoding="utf-8")

    settings = _settings(
        validation_local_path_host_prefix=str(host_root),
        validation_local_path_container_prefix="/data/pegasus",
        validation_local_path_default_browse="",
    )
    resolved = resolve_local_path_on_disk(str(csv_file), settings, must_be_file=True)
    assert resolved == csv_file.resolve()


def test_default_browse_prefers_existing_directory(tmp_path: Path) -> None:
    host_root = tmp_path / "home" / "user"
    host_root.mkdir(parents=True)
    settings = _settings(
        validation_local_path_host_prefix=str(host_root),
        validation_local_path_container_prefix="/data/pegasus",
        validation_local_path_default_browse="/data/pegasus",
    )
    assert default_browse_path(settings) == str(host_root.resolve())


def test_default_browse_uses_container_mount_when_present(tmp_path: Path) -> None:
    mount = tmp_path / "data" / "pegasus"
    mount.mkdir(parents=True)
    settings = _settings(
        validation_local_path_default_browse=str(mount),
        validation_local_path_host_prefix=str(tmp_path / "host"),
        validation_local_path_container_prefix=str(mount),
    )
    assert default_browse_path(settings) == str(mount.resolve())
