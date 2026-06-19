# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T14:52:16+05:30
# --- END GENERATED FILE METADATA ---

"""Tests for mismatch row persistence cap."""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, empty_mismatch_frame


def test_complete_success_skips_rows_above_cap() -> None:
    async def _run() -> None:
        run_id = uuid.uuid4()
        session = AsyncMock()
        run = MagicMock()
        session.get = AsyncMock(return_value=run)

        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "mismatches.ndjson"
            with artifact.open("w", encoding="utf-8") as fp:
                for i in range(5):
                    fp.write(
                        json.dumps(
                            {
                                "uid": str(i),
                                "mismatch_type": "value_mismatch",
                                "column_name": "c",
                                "source_value": "a",
                                "target_value": "b",
                            }
                        )
                        + "\n"
                    )
            result = ValidationRunResult(
                report=MismatchReport(
                    mismatches=empty_mismatch_frame(),
                    summary={
                        "missing_in_target": 0,
                        "extra_in_target": 0,
                        "value_mismatch": 5,
                    },
                ),
                mismatch_artifact_path=artifact,
                source_row_count=10,
                target_row_count=10,
                compared_column_count=1,
                compared_columns=["c"],
            )

            await ValidationRunRepository.complete_success(
                session,
                run_id,
                result,
                max_mismatch_rows=3,
            )

        session.add_all.assert_not_called()
        assert run.total_mismatch_records == 5
        assert run.footer_validation is not None
        persistence = run.footer_validation.get("_persistence") or {}
        assert persistence.get("mismatch_rows_persisted") is False
        assert "mismatch_artifact_path" in persistence

    asyncio.run(_run())
