# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T07:48:09Z
# --- END GENERATED FILE METADATA ---

"""Report generation for reconciliation results."""

from datetime import datetime
from pathlib import Path

from category1.models.schemas import ReconciliationJobConfig, ReconciliationResult


class ReportGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, result: ReconciliationResult, config: ReconciliationJobConfig) -> Path:
        report_path = self.output_dir / "VALIDATION_RESULTS.md"
        lines = self._build_report(result, config)
        report_path.write_text("\n".join(lines))
        return report_path

    def _build_report(self, result: ReconciliationResult, config: ReconciliationJobConfig) -> list[str]:
        lines = [
            "# Validation Results",
            "",
            f"**Job ID:** `{result.job_id}`",
            f"**Status:** {result.status.value}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "## Summary",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Source Rows | {result.execution_stats.source_rows_processed if result.execution_stats else 'N/A'} |",
            f"| Target Rows | {result.execution_stats.target_rows_processed if result.execution_stats else 'N/A'} |",
            f"| Missing Records | {result.missing_count} |",
            f"| Extra Records | {result.extra_count} |",
            f"| Mismatched Records | {result.mismatched_count} |",
            f"| Matching Records | {result.matching_count} |",
            "",
        ]

        # Schema differences
        lines.extend(["## Schema Differences", ""])
        if result.schema_validation and result.schema_validation.differences:
            lines.append("| Column | Type | Source | Target |")
            lines.append("|--------|------|--------|--------|")
            for diff in result.schema_validation.differences:
                lines.append(
                    f"| {diff.column} | {diff.difference_type} | "
                    f"{diff.source_value or '-'} | {diff.target_value or '-'} |"
                )
        else:
            lines.append("No schema differences detected.")
        lines.append("")

        # Sample mismatches
        lines.extend(["## Sample Mismatches", ""])
        if result.sample_mismatches:
            for m in result.sample_mismatches[:50]:
                lines.append(f"### {m.mismatch_type.upper()}: `{m.record_key}` (partition {m.partition_id})")
                if m.column_differences:
                    lines.append("")
                    lines.append("| Column | Source | Target |")
                    lines.append("|--------|--------|--------|")
                    for cd in m.column_differences:
                        lines.append(f"| {cd.column} | {cd.source_value or '-'} | {cd.target_value or '-'} |")
                lines.append("")
        else:
            lines.append("No mismatches detected.")
        lines.append("")

        # Execution statistics
        lines.extend(["## Execution Statistics", ""])
        if result.execution_stats:
            es = result.execution_stats
            lines.extend([
                f"- **Duration:** {es.duration_seconds:.2f}s",
                f"- **Partitions Processed:** {es.partitions_processed}",
                f"- **Chunks Processed:** {es.chunks_processed}",
                f"- **Peak Memory:** {es.peak_memory_mb:.1f} MB",
                f"- **Disk Spill:** {es.disk_spill_mb:.1f} MB",
                f"- **Network Read:** {es.network_bytes_read:,} bytes",
                f"- **Network Written:** {es.network_bytes_written:,} bytes",
            ])
        lines.append("")

        # Partition stats summary
        if result.partition_stats:
            lines.extend(["## Partition Statistics", ""])
            lines.append("| Partition | Source | Target | Missing | Extra | Mismatched | Time (ms) |")
            lines.append("|-----------|--------|--------|---------|-------|------------|-----------|")
            for ps in result.partition_stats[:100]:
                lines.append(
                    f"| {ps.partition_id} | {ps.source_records} | {ps.target_records} | "
                    f"{ps.missing} | {ps.extra} | {ps.mismatched} | {ps.processing_time_ms:.1f} |"
                )
            if len(result.partition_stats) > 100:
                lines.append(f"| ... | ({len(result.partition_stats) - 100} more partitions) | | | | | |")

        # Configuration
        lines.extend([
            "", "## Configuration", "",
            f"- Chunk Size: {config.chunk_size}",
            f"- Partitions: {config.num_partitions}",
            f"- Memory Limit: {config.memory_limit_mb} MB",
            f"- Key Columns: {', '.join(config.key_columns)}",
            f"- Key Strategy: {config.key_strategy.value}",
        ])

        return lines
