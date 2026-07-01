# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:53:09Z
# --- END GENERATED FILE METADATA ---

"""VALIDATION_RESULTS.md report writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.validation.pipeline.result import PipelineResult


def write_validation_results(
    path: Path,
    result: PipelineResult,
    *,
    source_label: str = "",
    target_label: str = "",
    extra_stats: dict[str, Any] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = extra_stats or {}
    lines = [
        "# Validation Results",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Schema Difference Count | {len(result.schema_differences)} |",
        f"| Row Count Match | {result.row_count_match} |",
        f"| Source Row Count | {result.source_row_count} |",
        f"| Target Row Count | {result.target_row_count} |",
        f"| Mismatched Partitions | {result.mismatched_partitions} |",
        f"| Missing Records | {result.missing_count} |",
        f"| Extra Records | {result.extra_count} |",
        f"| Changed Records | {result.changed_count} |",
        f"| Matching Records | {result.matching_count} |",
        "",
        f"**Execution time:** {result.execution_seconds:.4f} s",
        f"**Source:** {source_label}",
        f"**Target:** {target_label}",
        "",
    ]
    stage_report = (result.extra_stats or {}).get("stage_report")
    if stage_report:
        lines.extend(["## Stage Metrics", "", "```", stage_report, "```", ""])
    if stats:
        lines.extend(["## Runtime Configuration", ""])
        for k, v in stats.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    lines.extend(["## Schema Differences", ""])
    if result.schema_differences:
        for d in result.schema_differences:
            lines.append(f"- `{d.column}` ({d.difference_type}): {d.source_value} → {d.target_value}")
    else:
        lines.append("_No schema differences._")
    lines.append("")

    if result.sample_mismatches:
        lines.extend(["## Sample Mismatches", ""])
        for m in result.sample_mismatches[:50]:
            lines.append(f"- **{m.mismatch_type}** `{m.record_key}`")
            for cd in m.column_differences:
                lines.append(f"  - {cd.column}: {cd.source_value} → {cd.target_value}")

    path.write_text("\n".join(lines), encoding="utf-8")
