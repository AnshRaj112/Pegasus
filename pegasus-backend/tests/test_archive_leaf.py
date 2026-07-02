# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T06:35:41Z
# --- END GENERATED FILE METADATA ---

"""Tests for nested archive leaf extraction and validation."""

from __future__ import annotations

import json
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.schemas.validation import FixedWidthConfig, FixedWidthField, FixedWidthMatchStrategy
from pegasus.services.validation_service import ValidationService
from pegasus.validation.archive_leaf import (
    archive_sample_has_fixed_width_leaf,
    archive_sample_has_json_leaf,
    archive_sample_has_tabular_leaf,
    archive_sample_may_be_fixed_width,
    materialize_archive_fixed_width_leaf,
    materialize_archive_json_leaf,
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


def _build_json_zip_pair(work: Path) -> tuple[Path, Path]:
    import zipfile

    for prefix in ("src", "tgt"):
        payload = {"id": 1, "value": "A" if prefix == "src" else "Z"}
        json_path = work / f"{prefix}.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        zip_path = work / f"case_json_{prefix}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(json_path, arcname=json_path.name)
    return work / "case_json_src.zip", work / "case_json_tgt.zip"


def _build_fixed_width_zip_pair(work: Path) -> tuple[Path, Path]:
    import zipfile

    def write_fw(path: Path, rows: list[tuple[str, str]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row_id, value in rows:
                handle.write(f"{row_id:<12}  {value:<12}\n")

    for prefix, rows in (
        ("src", [("1", "A"), ("2", "B")]),
        ("tgt", [("1", "A"), ("2", "X")]),
    ):
        fw_path = work / f"{prefix}.txt"
        write_fw(fw_path, rows)
        zip_path = work / f"case_fw_{prefix}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(fw_path, arcname=fw_path.name)
    return work / "case_fw_src.zip", work / "case_fw_tgt.zip"


def _sample_fixed_width_config() -> FixedWidthConfig:
    return FixedWidthConfig(
        uid_column="id",
        match_strategy=FixedWidthMatchStrategy.EXACT,
        fields=[
            FixedWidthField(
                field_name="id",
                source_start=0,
                source_end=12,
                target_start=0,
                target_end=12,
                field_type="text",
            ),
            FixedWidthField(
                field_name="value",
                source_start=14,
                source_end=26,
                target_start=14,
                target_end=26,
                field_type="text",
            ),
        ],
    )


def test_archive_sample_has_json_leaf() -> None:
    assert archive_sample_has_json_leaf(["inner.zip/data.json"])
    assert archive_sample_has_json_leaf(None, file_format="zip -> json")
    assert not archive_sample_has_tabular_leaf(None, file_format="zip -> json")


def test_materialize_json_zip_leaf(tmp_path: Path) -> None:
    src, _tgt = _build_json_zip_pair(tmp_path)
    settings = Settings()
    leaf = materialize_archive_json_leaf(src, settings=settings, work_dir=tmp_path / "work")
    assert leaf.name == "src.json"
    assert json.loads(leaf.read_text(encoding="utf-8"))["id"] == 1


def test_validate_archive_json_leaf_pair(tmp_path: Path) -> None:
    src, tgt = _build_json_zip_pair(tmp_path)
    service = ValidationService(Settings())
    result = service.validate_archive_pair_sync(
        src,
        tgt,
        file_format="zip",
        uid_column="document",
        column_mappings=[],
    )
    assert result.pipeline_metadata.get("path") == "archive_json_leaf"


def test_profile_archive_json_leaf_preview(tmp_path: Path) -> None:
    src, _tgt = _build_json_zip_pair(tmp_path)
    service = ValidationService(Settings())
    profile = service.profile_archive_adapter(
        None,
        local_path=src,
        object_name="case_json_src.zip",
        gcs_uri="gs://bucket/case_json_src.zip",
        file_format="zip",
    )
    assert archive_sample_has_json_leaf(profile.archive_entries_sample, file_format=profile.file_format)
    assert profile.json_preview is not None
    assert '"id"' in profile.json_preview


def test_materialize_fixed_width_zip_leaf(tmp_path: Path) -> None:
    src, _tgt = _build_fixed_width_zip_pair(tmp_path)
    settings = Settings()
    leaf = materialize_archive_fixed_width_leaf(src, settings=settings, work_dir=tmp_path / "work")
    assert leaf.name == "src.txt"
    assert leaf.read_text(encoding="utf-8").startswith("1")


def test_validate_archive_fixed_width_leaf_pair(tmp_path: Path) -> None:
    src, tgt = _build_fixed_width_zip_pair(tmp_path)
    service = ValidationService(Settings())
    result = service.validate_archive_pair_sync(
        src,
        tgt,
        file_format="zip",
        fixed_width_config=_sample_fixed_width_config(),
    )
    assert result.pipeline_metadata.get("path") == "archive_fixed_width_leaf"
    assert result.source_row_count == 2
    assert result.target_row_count == 2


def test_fixed_width_archive_not_treated_as_tabular(tmp_path: Path) -> None:
    src, _tgt = _build_fixed_width_zip_pair(tmp_path)
    service = ValidationService(Settings())
    profile = service.profile_archive_adapter(
        None,
        local_path=src,
        object_name="case_fw_src.zip",
        gcs_uri="gs://bucket/case_fw_src.zip",
        file_format="zip",
    )
    assert archive_sample_may_be_fixed_width(
        profile.archive_entries_sample,
        file_format=profile.file_format,
    )
    assert not archive_sample_has_tabular_leaf(
        profile.archive_entries_sample,
        file_format=profile.file_format,
    )
    assert profile.delimiter is None
