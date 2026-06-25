# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:10:34Z
# --- END GENERATED FILE METADATA ---

"""GCS URI parsing and coercion from gs:// paths."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from pegasus.models.cloud_connection import CloudConnection
from pegasus.schemas.validation import GoogleCloudStorageConfig
from pegasus.validation.cloud_input import (
    coerce_cloud_storage_reference,
    ensure_resolved_cloud_config,
    resolve_cloud_config_with_saved_connection,
)
from pegasus.validation.gcs_object import parse_gs_uri


def test_parse_gs_uri_splits_bucket_and_object() -> None:
    assert parse_gs_uri("gs://pelican_f2f_bucket/test-data/generated-100k/source.csv") == (
        "pelican_f2f_bucket",
        "test-data/generated-100k/source.csv",
    )
    assert parse_gs_uri("/home/user/file.csv") is None


def test_coerce_cloud_storage_reference_from_gs_path() -> None:
    conn_id = uuid.uuid4()
    saved = MagicMock(spec=CloudConnection)
    saved.id = conn_id
    saved.name = "pelican"
    saved.bucket = "pelican_f2f_bucket"
    saved.project_id = "demo-project"
    saved.credentials_json = '{"type":"service_account","project_id":"demo-project"}'
    saved.active = True

    session = AsyncMock()
    with patch(
        "pegasus.validation.cloud_input.CloudConnectionRepository.get_active_connection_by_bucket",
        AsyncMock(return_value=saved),
    ):
        with patch(
            "pegasus.validation.cloud_input.load_cloud_connection_or_404",
            AsyncMock(return_value=saved),
        ):
            cloud, path = asyncio.run(
                coerce_cloud_storage_reference(
                    session,
                    label="source",
                    path="gs://pelican_f2f_bucket/test-data/generated-100k/source.csv",
                    cloud=None,
                )
            )

    assert path is None
    assert cloud is not None
    assert cloud.bucket == "pelican_f2f_bucket"
    assert cloud.object_name == "test-data/generated-100k/source.csv"
    assert cloud.connection_id == conn_id
    assert "service_account" in (cloud.credentials_json or "")


def test_coerce_cloud_storage_reference_requires_credentials_without_saved_connection() -> None:
    session = AsyncMock()
    with patch(
        "pegasus.validation.cloud_input.CloudConnectionRepository.get_active_connection_by_bucket",
        AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                coerce_cloud_storage_reference(
                    session,
                    label="source",
                    path="gs://missing-bucket/data/source.csv",
                    cloud=None,
                )
            )
    assert exc.value.status_code == 400
    assert "Google Cloud Storage URI" in str(exc.value.detail)


def test_resolve_cloud_config_ignores_invalid_inline_json_when_connection_saved() -> None:
    conn_id = uuid.uuid4()
    saved = MagicMock(spec=CloudConnection)
    saved.id = conn_id
    saved.name = "pelican"
    saved.bucket = "pelican_f2f_bucket"
    saved.project_id = "demo-project"
    saved.credentials_json = '{"type":"service_account","project_id":"demo-project"}'

    session = AsyncMock()
    with patch(
        "pegasus.validation.cloud_input.load_cloud_connection_or_404",
        AsyncMock(return_value=saved),
    ):
        resolved = asyncio.run(
            resolve_cloud_config_with_saved_connection(
                GoogleCloudStorageConfig(
                    bucket="pelican_f2f_bucket",
                    object_name="source.csv",
                    connection_id=conn_id,
                    credentials_json="{not-json",
                ),
                session=session,
            )
        )
    assert resolved.credentials_json == saved.credentials_json


def test_ensure_resolved_cloud_config_loads_saved_credentials() -> None:
    conn_id = uuid.uuid4()
    saved = MagicMock(spec=CloudConnection)
    saved.id = conn_id
    saved.name = "pelican"
    saved.bucket = "pelican_f2f_bucket"
    saved.project_id = "demo-project"
    saved.credentials_json = '{"type":"service_account","project_id":"demo-project"}'

    session = AsyncMock()
    with patch(
        "pegasus.validation.cloud_input.load_cloud_connection_or_404",
        AsyncMock(return_value=saved),
    ):
        resolved = asyncio.run(
            ensure_resolved_cloud_config(
                session,
                GoogleCloudStorageConfig(
                    bucket="pelican_f2f_bucket",
                    object_name="source.csv",
                    connection_id=conn_id,
                ),
            )
        )
    assert resolved is not None
    assert "service_account" in (resolved.credentials_json or "")


def test_coerce_cloud_storage_reference_keeps_explicit_cloud_config() -> None:
    session = AsyncMock()
    cloud = GoogleCloudStorageConfig(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_json='{"type":"service_account","project_id":"demo"}',
    )
    with patch(
        "pegasus.validation.cloud_input.resolve_cloud_config_with_saved_connection",
        AsyncMock(return_value=cloud),
    ):
        resolved, path = asyncio.run(
            coerce_cloud_storage_reference(
                session,
                label="source",
                path=None,
                cloud=cloud,
            )
        )
    assert path is None
    assert resolved.bucket == "demo-bucket"
