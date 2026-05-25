"""Compare trailing CSV rows (footers) between source and target files."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.flat_file import split_line


def _parse_csv_line(line: str, delimiter: str) -> list[str]:
    """Split one physical line into fields (quote-aware for any delimiter)."""
    return split_line(line, delimiter)


def read_trailing_csv_rows(
    path: Path,
    *,
    delimiter: str,
    trailing_rows: int,
    encoding: str = "utf-8",
) -> list[list[str]]:
    """Return up to *trailing_rows* physical lines from the end of a CSV (parsed fields)."""
    if trailing_rows <= 0:
        return []

    text = path.read_text(encoding=encoding, errors="replace")
    lines = text.splitlines()
    if not lines:
        return []

    tail_lines = lines[-trailing_rows:]
    rows: list[list[str]] = []
    for line in tail_lines:
        if not line.strip():
            continue
        rows.append(_parse_csv_line(line, delimiter))
    return rows


def validate_footer_rows(
    source_rows: list[list[str]],
    target_rows: list[list[str]],
) -> dict[str, object]:
    """Compare trailing rows; exact match on normalized cell text."""
    if not source_rows and not target_rows:
        return {
            "enabled": True,
            "match": True,
            "source_trailing_rows": [],
            "target_trailing_rows": [],
            "message": "No trailing rows to compare.",
        }

    def _norm_row(row: list[str]) -> list[str]:
        return [c.strip() for c in row]

    src_norm = [_norm_row(r) for r in source_rows]
    tgt_norm = [_norm_row(r) for r in target_rows]

    if src_norm == tgt_norm:
        return {
            "enabled": True,
            "match": True,
            "source_trailing_rows": source_rows,
            "target_trailing_rows": target_rows,
            "message": None,
        }

    return {
        "enabled": True,
        "match": False,
        "source_trailing_rows": source_rows,
        "target_trailing_rows": target_rows,
        "message": (
            f"Footer rows differ: source has {len(source_rows)} trailing row(s), "
            f"target has {len(target_rows)}."
        ),
    }
