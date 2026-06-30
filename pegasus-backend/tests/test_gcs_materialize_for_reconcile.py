# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""GCS delimited validation materializes objects locally before reconciliation."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import (
    GcsDelimitedAdapter,
    materialize_gcs_delimited_pair,
)
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import GcsStreamSession, clear_gcs_stream_sessions


@contextmanager
def _patch_local_gcs_stream(src: Path, tgt: Path):
    def _resolve_path(ref: GcsObjectRef) -> Path:
        return src if ref.object_name.endswith("source.csv") else tgt

    def _local_download(self, dest: Path, *, chunk_size: int = 8 * 1024 * 1024) -> None:
        path = _resolve_path(self._ref)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())

    @contextmanager
    def _local_stream(self, **kwargs):
        with open(_resolve_path(self._ref), "rb") as handle:
            yield handle

    def _local_prefix(self, *, max_bytes: int) -> bytes:
        path = _resolve_path(self._ref)
        with open(path, "rb") as handle:
            return handle.read(max_bytes)

    with patch.object(GcsStreamSession, "download_to_path", _local_download):
        with patch.object(GcsStreamSession, "open_binary", _local_stream):
            with patch.object(GcsStreamSession, "read_prefix", _local_prefix):
                yield


def test_materialize_gcs_delimited_pair_uses_local_file_adapters() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    target_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="target.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)
    target = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=tgt.stat().st_size)

    clear_gcs_stream_sessions()
    try:
        with tempfile.TemporaryDirectory() as td, _patch_local_gcs_stream(src, tgt):
            out_source, out_target = materialize_gcs_delimited_pair(
                source,
                target,
                work_dir=Path(td),
            )
            assert isinstance(out_source, FileDelimitedAdapter)
            assert isinstance(out_target, FileDelimitedAdapter)
            assert out_source.path.is_file()
            assert out_target.path.is_file()
            assert out_source.get_size_bytes() == src.stat().st_size
            assert out_target.get_size_bytes() == tgt.stat().st_size
    finally:
        clear_gcs_stream_sessions()


def test_validation_service_materializes_gcs_before_reconcile() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    target_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="target.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)
    target = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=tgt.stat().st_size)

    get_settings.cache_clear()
    service = ValidationService(get_settings())

    clear_gcs_stream_sessions()
    try:
        with _patch_local_gcs_stream(src, tgt):
            result = service._validate_delimited_adapters_sync(  # noqa: SLF001
                source,
                target,
                "id",
                "||",
                source_label="gs://demo-bucket/source.csv",
                target_label="gs://demo-bucket/target.csv",
            )
    finally:
        clear_gcs_stream_sessions()

    assert result.source_row_count == 10_000
    assert (result.pipeline_metadata or {}).get("path") in {
        "spill",
        "spill_arrow_ipc",
        "spill_native_multichar_drilldown",
    }
