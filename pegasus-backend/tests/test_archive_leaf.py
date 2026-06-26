# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T12:00:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for nested archive tabular leaf extraction."""

from __future__ import annotations

from pathlib import Path

from pegasus.core.config import Settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.archive_leaf import (
    archive_sample_has_tabular_leaf,
    materialize_archive_tabular_leaf,
)


def _build_case12(work: Path, *, data_rows: int = 5) -> tuple[Path, Path]:
    import tarfile
    import zipfile

    values = ["A", "B", "C", "D", "E", "F"]
    for prefix in ("src", "tgt"):
        lines = ["id,value"] + [
            f"{row_id},{values[(row_id - 1) % len(values)]}"
            for row_id in range(1, data_rows + 1)
        ]
        csv_path = work / f"{prefix}.csv"
        csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        zip_path = work / f"inner_{prefix}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(csv_path, arcname=csv_path.name)
        inner_tar = work / f"inner_{prefix}.tar"
        with tarfile.open(inner_tar, "w") as tf:
            tf.add(zip_path, arcname=zip_path.name)
        outer = work / f"case12_{prefix}.tar"
        with tarfile.open(outer, "w") as tf:
            tf.add(inner_tar, arcname=inner_tar.name)
    return work / "case12_src.tar", work / "case12_tgt.tar"


def test_archive_sample_has_tabular_leaf() -> None:
    assert archive_sample_has_tabular_leaf(["inner_src.tar/inner_src.zip/src.csv"])
    assert not archive_sample_has_tabular_leaf(["inner_src.tar/inner_src.zip"])


def test_materialize_case12_tabular_leaf(tmp_path: Path) -> None:
    src, _tgt = _build_case12(tmp_path)
    settings = Settings()
    leaf = materialize_archive_tabular_leaf(src, settings=settings, work_dir=tmp_path / "work")
    assert leaf.name == "src.csv"
    assert "id,value" in leaf.read_text(encoding="utf-8")


def test_validate_archive_tabular_leaf_pair(tmp_path: Path) -> None:
    src, tgt = _build_case12(tmp_path, data_rows=2)
    service = ValidationService(Settings())
    result = service.validate_archive_pair_sync(
        src,
        tgt,
        file_format="tar",
        uid_column="id",
        delimiter=",",
    )
    assert result.pipeline_metadata.get("path") == "archive_tabular_leaf"
    assert result.source_row_count == 2
    assert result.target_row_count == 2
    assert "value" in (result.compared_columns or [])


def test_profile_archive_tabular_leaf_counts(tmp_path: Path) -> None:
    src, _tgt = _build_case12(tmp_path, data_rows=5)
    service = ValidationService(Settings())
    profile = service.profile_archive_adapter(
        None,
        local_path=src,
        object_name="case12_src.tar",
        gcs_uri="gs://bucket/case12_src.tar",
        file_format="tar",
        delimiter=",",
    )
    assert profile.column_count == 2
    assert profile.row_count == 6
    assert profile.has_header is True
    assert profile.archive_entry_count == 1
    assert archive_sample_has_tabular_leaf(profile.archive_entries_sample)


def test_archive_tabular_leaf_persisted_for_mismatch_export(tmp_path: Path) -> None:
    src, tgt = _build_case12(tmp_path, data_rows=5)
    job_dir = tmp_path / "job"
    service = ValidationService(Settings())
    result = service.validate_archive_pair_sync(
        src,
        tgt,
        file_format="tar",
        uid_column="id",
        delimiter=",",
        column_mappings=[],
        artifact_export_parent=job_dir,
    )
    meta = result.pipeline_metadata
    assert meta.get("path") == "archive_tabular_leaf"
    src_leaf = Path(str(meta["source_leaf_local"]))
    tgt_leaf = Path(str(meta["target_leaf_local"]))
    assert src_leaf.is_file()
    assert tgt_leaf.is_file()

    from pegasus.validation.job_worker import _build_mismatch_lookups, _resolve_mismatch_lookup_inputs

    lookup_src, lookup_tgt = _resolve_mismatch_lookup_inputs(src, tgt, result)
    assert lookup_src == src_leaf
    assert lookup_tgt == tgt_leaf
    src_lookup, tgt_lookup = _build_mismatch_lookups(
        lookup_src,
        lookup_tgt,
        identity_columns=["id"],
        compare_columns=["value"],
        delimiter=",",
        has_header=True,
        header_leading_rows=0,
    )
    assert src_lookup["2"]["value"] == "B"
    assert tgt_lookup["2"]["value"] == "B"
