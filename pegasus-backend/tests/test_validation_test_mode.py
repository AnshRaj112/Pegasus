# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:26:25Z
# --- END GENERATED FILE METADATA ---

"""Tests for validation test-mode policy and per-column snippet sampling."""

from __future__ import annotations

import polars as pl

from pegasus.api.v1.mismatch_sample import (
    build_grouped_mismatch_samples,
    per_column_value_mismatch_sample,
)
from pegasus.core.config import Settings
from pegasus.schemas.validation import ValidationTestMode
from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.test_mode_policy import (
    build_litmus_row_count_failure,
    clamp_snippet_limit,
    effective_run_is_match,
    finalize_litmus_run_result,
    normalize_test_mode,
    resolve_mismatch_collection_policy,
    read_footer_test_mode,
    validation_run_is_match,
)
from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, empty_mismatch_frame


def test_normalize_test_mode_maps_legacy_full_plus() -> None:
    assert normalize_test_mode("full_plus") == ValidationTestMode.FULL
    assert normalize_test_mode(ValidationTestMode.FULL) == ValidationTestMode.FULL


def test_validation_run_is_match_row_count_mismatch_is_fail() -> None:
    assert validation_run_is_match({"row_count_mismatch": True}, total_mismatch_records=0) is False
    assert validation_run_is_match({}, total_mismatch_records=0) is True
    assert validation_run_is_match({}, total_mismatch_records=3) is False
    assert validation_run_is_match(
        {},
        total_mismatch_records=0,
        test_mode="litmus",
        source_row_count=100_000,
        target_row_count=104_000,
    ) is False


def test_finalize_litmus_run_result_fails_on_row_count_delta() -> None:
    run = ValidationRunResult(
        report=MismatchReport(mismatches=empty_mismatch_frame(), summary={}),
        source_row_count=100_000,
        target_row_count=104_000,
        compared_column_count=4,
        compared_columns=["a", "b"],
        test_mode="litmus",
    )
    out = finalize_litmus_run_result(run)
    assert out.test_mode == "litmus"
    assert out.report.summary.get("row_count_mismatch") is True
    assert validation_run_is_match(
        out.report.summary,
        total_mismatch_records=0,
        test_mode=out.test_mode,
        source_row_count=out.source_row_count,
        target_row_count=out.target_row_count,
    ) is False


def test_effective_run_is_match_for_persisted_litmus() -> None:
    assert effective_run_is_match(
        is_match=True,
        test_mode="litmus",
        source_row_count=100,
        target_row_count=200,
        total_mismatch_records=0,
    ) is False
    assert read_footer_test_mode({"litmus": {"checks_failed": ["row_count"]}}) == "litmus"


def test_clamp_snippet_limit_uses_admin_bounds() -> None:
    settings = Settings(
        validation_mismatch_snippet_limit_default=10,
        validation_mismatch_snippet_limit_max=50,
    )
    assert clamp_snippet_limit(settings, requested=None) == 10
    assert clamp_snippet_limit(settings, requested=25) == 25
    assert clamp_snippet_limit(settings, requested=99) == 50


def test_litmus_policy_skips_artifacts() -> None:
    settings = Settings()
    policy = resolve_mismatch_collection_policy(settings, test_mode=ValidationTestMode.LITMUS)
    assert policy.fail_on_row_count_mismatch is True
    assert policy.export_mismatch_artifact is False
    assert policy.pipeline_sample_limit == 0


def test_full_policy_caps_per_category() -> None:
    settings = Settings(
        validation_mismatch_snippet_limit_default=10,
        validation_mismatch_snippet_limit_max=50,
    )
    policy = resolve_mismatch_collection_policy(
        settings,
        test_mode=ValidationTestMode.FULL,
        mismatch_snippet_limit=12,
        compare_column_count=4,
    )
    assert policy.presence_snippet_cap == 12
    assert policy.value_per_column_cap == 12
    assert policy.pipeline_sample_limit == 12 * 2 + 12 * 4


def test_litmus_row_count_failure_has_no_samples() -> None:
    result = build_litmus_row_count_failure(
        source_row_count=10,
        target_row_count=9,
        compared_columns=["a"],
    )
    assert result.test_mode == "litmus"
    assert result.report.mismatches.is_empty()
    assert result.litmus is not None
    assert "row_count" in result.litmus["checks_failed"]


def test_per_column_value_mismatch_sample_limits_each_column() -> None:
    rows = []
    for col in ("c1", "c2"):
        for i in range(20):
            rows.append({
                "uid": f"{col}-{i}",
                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                "column_name": col,
                "source_value": "a",
                "target_value": "b",
                "row_detail": None,
            })
    vm = pl.DataFrame(rows)
    sample = per_column_value_mismatch_sample(vm, 10)
    assert sample.height == 20
    for col in ("c1", "c2"):
        assert sample.filter(pl.col("column_name") == col).height == 10


def test_build_grouped_samples_full_caps_presence_and_columns() -> None:
    rows = []
    for i in range(30):
        rows.append({
            "uid": f"m{i}",
            "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
            "column_name": None,
            "source_value": None,
            "target_value": None,
            "row_detail": None,
        })
    for col in ("x", "y"):
        for i in range(30):
            rows.append({
                "uid": f"v{col}{i}",
                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                "column_name": col,
                "source_value": "1",
                "target_value": "2",
                "row_detail": None,
            })
    frame = pl.DataFrame(rows)
    miss, ext, val = build_grouped_mismatch_samples(
        frame,
        0,
        presence_max_rows=10,
        value_per_column_limit=10,
    )
    assert miss.height == 10
    assert ext.height == 0
    assert val.height == 20
    assert val.filter(pl.col("column_name") == "x").height == 10
