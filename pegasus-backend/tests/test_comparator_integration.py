# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T06:35:41Z
# --- END GENERATED FILE METADATA ---

"""Integration tests: core compare policy wired into ValidationService."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping
from pegasus.services.validation_service import ValidationService
from pegasus.validation.comparators.policy import active_compare_policy
from pegasus.validation.pipeline.fingerprint import canonical

REPO = Path(__file__).resolve().parents[2]
STRUCTURED = REPO / "test-data" / "structured-compare" / "csv"
EXPECTED = {"missing_in_target": 1, "extra_in_target": 1, "value_mismatch": 3}


@pytest.fixture
def service() -> ValidationService:
    get_settings.cache_clear()
    return ValidationService(get_settings())


@pytest.mark.skipif(not STRUCTURED.joinpath("source.csv").is_file(), reason="fixtures missing")
def test_main_pipeline_structured_compare(service: ValidationService) -> None:
    mappings = [
        ColumnMapping(source_column="tags", target_column="tags"),
        ColumnMapping(source_column="metadata", target_column="metadata"),
        ColumnMapping(source_column="notes", target_column="notes"),
    ]
    result = service._validate_csv_pair_sync(
        STRUCTURED / "source.csv",
        STRUCTURED / "target.csv",
        "id",
        ",",
        column_mappings=mappings,
        has_header=True,
    )
    summary = dict(result.report.summary)
    for key, want in EXPECTED.items():
        assert summary.get(key, 0) == want, f"{key}: got {summary.get(key)!r}, want {want}"


def test_fingerprint_uses_active_policy() -> None:
    from pegasus.validation.comparators.policy import ComparePolicy, ColumnRule, compare_policy_context

    policy = ComparePolicy(
        rules={"tags": ColumnRule(mode="structured", complex=True, order_sensitive=False)},
    )
    with compare_policy_context(policy):
        assert active_compare_policy() is policy
        assert canonical('["b","a"]', column="tags") == canonical('["a","b"]', column="tags")
        assert canonical('["b","a"]', column="notes") != canonical('["a","b"]', column="notes")
