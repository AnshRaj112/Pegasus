# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T07:31:26Z
# --- END GENERATED FILE METADATA ---

"""Worker-side mismatch persistence must survive repeated asyncio.run calls."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from pegasus.api.v1.validation_helpers import persist_completed_job_blocking
from pegasus.core.config import get_settings
from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, empty_mismatch_frame


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_persist_completed_job_blocking_uses_isolated_engine_twice() -> None:
    settings = get_settings()
    if not settings.enable_validation_persistence:
        pytest.skip("validation persistence disabled")

    run_id = uuid.uuid4()
    run_result = ValidationRunResult(
        report=MismatchReport(
            mismatches=empty_mismatch_frame(),
            summary={"missing_in_target": 0, "extra_in_target": 0, "value_mismatch": 0},
        ),
        source_row_count=1,
        target_row_count=1,
        compared_column_count=1,
        compared_columns=["id"],
    )

    with patch(
        "pegasus.api.v1.validation_helpers.maybe_persist_completed_job",
        new_callable=AsyncMock,
        return_value=0.01,
    ) as mock_persist:
        persist_completed_job_blocking(
            settings,
            run_id=run_id,
            run_result=run_result,
            job_meta={"column_mappings": []},
        )
        persist_completed_job_blocking(
            settings,
            run_id=run_id,
            run_result=run_result,
            job_meta={"column_mappings": []},
        )

    assert mock_persist.await_count == 2
    for call in mock_persist.await_args_list:
        session_factory = call.kwargs["session_factory"]
        assert session_factory is not None

        async def _open_session() -> None:
            async with session_factory() as session:
                assert session is not None

        asyncio.run(_open_session())


def test_create_isolated_async_sessionmaker_disposes_cleanly() -> None:
    from pegasus.core.database import create_isolated_async_sessionmaker

    async def _exercise() -> None:
        engine, session_factory = create_isolated_async_sessionmaker()
        try:
            async with session_factory() as session:
                assert session is not None
        finally:
            await engine.dispose()

    asyncio.run(_exercise())
    asyncio.run(_exercise())
