# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T10:19:19Z
# --- END GENERATED FILE METADATA ---

"""Resolve validation test-mode behavior for reconciliation and snippet caps."""

from __future__ import annotations

from dataclasses import dataclass

from pegasus.core.config import Settings
from pegasus.schemas.validation import ValidationTestMode
from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, VALUE_MISMATCH_ROWS_SUMMARY_KEY, empty_mismatch_frame


@dataclass(frozen=True, slots=True)
class MismatchCollectionPolicy:
    """Controls mismatch sampling, artifact export, and litmus pre-checks."""

    fail_on_row_count_mismatch: bool
    export_mismatch_artifact: bool
    pipeline_sample_limit: int
    presence_snippet_cap: int
    value_per_column_cap: int
    persistence_row_cap: int


def normalize_test_mode(test_mode: ValidationTestMode | str) -> ValidationTestMode:
    """Normalize legacy mode strings to the supported enum values."""
    if isinstance(test_mode, ValidationTestMode):
        return test_mode
    raw = str(test_mode).strip().lower()
    if raw == "full_plus":
        raw = "full"
    return ValidationTestMode(raw)


def clamp_snippet_limit(
    settings: Settings,
    *,
    requested: int | None,
) -> int:
    """Return a snippet limit within admin bounds (default when omitted)."""
    default = settings.validation_mismatch_snippet_limit_default
    max_allowed = settings.validation_mismatch_snippet_limit_max
    if requested is None:
        return min(default, max_allowed)
    return max(1, min(int(requested), max_allowed))


def resolve_mismatch_collection_policy(
    settings: Settings,
    *,
    test_mode: ValidationTestMode | str,
    mismatch_snippet_limit: int | None = None,
    compare_column_count: int = 0,
) -> MismatchCollectionPolicy:
    """Map *test_mode* to reconciliation and snippet collection behavior."""
    mode = normalize_test_mode(test_mode)
    if mode == ValidationTestMode.LITMUS:
        return MismatchCollectionPolicy(
            fail_on_row_count_mismatch=True,
            export_mismatch_artifact=False,
            pipeline_sample_limit=0,
            presence_snippet_cap=0,
            value_per_column_cap=0,
            persistence_row_cap=0,
        )

    cap = clamp_snippet_limit(settings, requested=mismatch_snippet_limit)
    cols = max(compare_column_count, 1)
    pipeline_budget = cap * 2 + cap * cols
    return MismatchCollectionPolicy(
        fail_on_row_count_mismatch=False,
        export_mismatch_artifact=True,
        pipeline_sample_limit=pipeline_budget,
        presence_snippet_cap=cap,
        value_per_column_cap=cap,
        persistence_row_cap=pipeline_budget,
    )


def validation_run_is_match(
    summary: dict,
    *,
    total_mismatch_records: int,
    test_mode: str | None = None,
    source_row_count: int | None = None,
    target_row_count: int | None = None,
) -> bool:
    """True only when there are no mismatch records and no litmus row-count failure."""
    if summary.get("row_count_mismatch"):
        return False
    mode = normalize_test_mode(test_mode or ValidationTestMode.FULL)
    if mode == ValidationTestMode.LITMUS:
        if (
            source_row_count is not None
            and target_row_count is not None
            and source_row_count != target_row_count
        ):
            return False
    return total_mismatch_records == 0


def finalize_litmus_run_result(run_result: ValidationRunResult) -> ValidationRunResult:
    """After a litmus reconciliation, fail when final row counts still differ."""
    if normalize_test_mode(run_result.test_mode) != ValidationTestMode.LITMUS:
        return run_result
    src = int(run_result.source_row_count or 0)
    tgt = int(run_result.target_row_count or 0)
    if src == tgt:
        return run_result
    failed = build_litmus_row_count_failure(
        source_row_count=src,
        target_row_count=tgt,
        compared_columns=run_result.compared_columns,
    )
    failed.durations = run_result.durations
    return failed


def read_footer_test_mode(raw: dict | None) -> str | None:
    """Read persisted ``test_mode`` from ``footer_validation`` JSON."""
    if not raw or not isinstance(raw, dict):
        return None
    token = raw.get("test_mode")
    if token is not None:
        text = str(token).strip().lower()
        if text:
            return text
    if isinstance(raw.get("litmus"), dict):
        return ValidationTestMode.LITMUS.value
    return None


def effective_run_is_match(
    *,
    is_match: bool | None,
    test_mode: str | None,
    source_row_count: int | None,
    target_row_count: int | None,
    total_mismatch_records: int = 0,
) -> bool | None:
    """Apply litmus row-count rules when rendering persisted history."""
    if (
        normalize_test_mode(test_mode or ValidationTestMode.FULL) == ValidationTestMode.LITMUS
        and source_row_count is not None
        and target_row_count is not None
        and source_row_count != target_row_count
    ):
        return False
    if is_match is False:
        return False
    if total_mismatch_records > 0:
        return False
    return is_match


def build_litmus_row_count_failure(
    *,
    source_row_count: int,
    target_row_count: int,
    compared_columns: list[str] | None = None,
) -> ValidationRunResult:
    """Litmus pre-check: row counts differ — skip reconciliation."""
    cols = list(compared_columns or [])
    summary = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: 0,
        "row_count_mismatch": True,
    }
    return ValidationRunResult(
        report=MismatchReport(mismatches=empty_mismatch_frame(), summary=summary),
        source_row_count=source_row_count,
        target_row_count=target_row_count,
        compared_column_count=len(cols),
        compared_columns=cols,
        test_mode=ValidationTestMode.LITMUS.value,
        litmus={
            "checks_run": ["row_count"],
            "checks_passed": [],
            "checks_failed": ["row_count"],
            "notes": [
                "Source and target row counts differ; reconciliation was skipped in Litmus mode.",
            ],
        },
    )
