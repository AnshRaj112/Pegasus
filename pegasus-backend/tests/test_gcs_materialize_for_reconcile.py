# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T05:37:38Z
# --- END GENERATED FILE METADATA ---

"""GCS delimited validation materializes objects locally before reconciliation."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import (
    GcsDelimitedAdapter,
    materialize_gcs_delimited_pair,
)
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import GcsStreamSession, clear_gcs_stream_sessions
from pegasus.validation.readers.native_multichar import native_extension_available


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


@pytest.mark.skipif(not native_extension_available(), reason="pegasus_native not built")
def test_gcs_materialized_workspace_export_has_cell_values() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        pytest.skip("fixture missing")

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
    cols = [c for c in src.read_text(encoding="utf-8").splitlines()[0].split("||") if c != "id"]

    get_settings.cache_clear()
    service = ValidationService(get_settings())

    clear_gcs_stream_sessions()
    try:
        with tempfile.TemporaryDirectory() as job_dir, _patch_local_gcs_stream(src, tgt):
            job_path = Path(job_dir)
            result = service._validate_delimited_adapters_sync(  # noqa: SLF001
                source,
                target,
                "id",
                "||",
                source_label="gs://demo-bucket/source.csv",
                target_label="gs://demo-bucket/target.csv",
                artifact_export_parent=job_path,
            )
            meta = result.pipeline_metadata or {}
            assert meta.get("source_materialized_local")
            assert meta.get("target_materialized_local")

            from pegasus.validation.pipeline.mismatch_export import (
                export_workspace_mismatches_ndjson,
                ndjson_row_detail_lacks_columns,
            )

            workspace = job_path / "reconcile_workspace"
            out_path = job_path / "mismatches.ndjson"
            stats = export_workspace_mismatches_ndjson(
                workspace,
                out_path,
                compare_columns=cols,
            )
            assert stats.total > 0
            assert not ndjson_row_detail_lacks_columns(out_path, cols)
            sample = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
            detail = json.loads(sample["row_detail"]) if sample.get("row_detail") else {}
            if sample["mismatch_type"] == "missing_in_target":
                assert _record_has_values(detail.get("source_record"), cols)
            elif sample["mismatch_type"] == "value_mismatch":
                assert sample.get("source_value") or sample.get("target_value")
    finally:
        clear_gcs_stream_sessions()


def _record_has_values(record: object, cols: list[str]) -> bool:
    if not isinstance(record, dict):
        return False
    return any(col in record and str(record.get(col) or "") not in ("", "__NULL__") for col in cols)
