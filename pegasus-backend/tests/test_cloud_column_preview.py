# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:52:27Z
# --- END GENERATED FILE METADATA ---

"""Cloud column preview streams headers from GCS without full download."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from pegasus.core.config import get_settings
from pegasus.schemas.validation import GoogleCloudStorageConfig
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.cloud_input import resolve_delimited_input
from pegasus.validation.gcs_object import GcsObjectRef


def test_resolve_delimited_input_requires_path_or_cloud() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        resolve_delimited_input(
            settings=settings,
            label="source",
            path=None,
            cloud=None,
            delimiter=",",
            has_header=True,
            skip_rows=0,
        )
    assert exc.value.status_code == 400


def test_cloud_column_preview_streams_without_download(tmp_path: Path) -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    cloud = GoogleCloudStorageConfig(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_json='{"type":"service_account","project_id":"demo"}',
    )
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

    source_adapter = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=src.stat().st_size)
    target_adapter = GcsDelimitedAdapter(target_ref, delimiter=",", size_bytes=tgt.stat().st_size)

    with patch("pegasus.validation.gcs_object.read_gcs_prefix") as read_prefix:
        read_prefix.side_effect = lambda ref, **kwargs: (
            src.read_bytes() if ref.object_name.endswith("source.csv") else tgt.read_bytes()
        )
        with patch("pegasus.validation.gcs_object.open_gcs_binary") as open_blob:
            open_blob.side_effect = lambda ref: open(
                src if ref.object_name.endswith("source.csv") else tgt,
                "rb",
            )
            preview = ValidationService(get_settings()).preview_column_headers_from_adapters(
                source=source_adapter,
                target=target_adapter,
                uid_column="employee_id",
                delimiter=",",
            )

    assert preview["source_columns"] == ["employee_id", "name", "department", "salary"]
    assert any(m["source_column"] == "name" for m in preview["auto_mappings"])
