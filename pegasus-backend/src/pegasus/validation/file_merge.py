"""Merge multiple on-disk files into one logical source or target for validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.core.json_util import dumps_bytes, loads_bytes, loads_str
from pegasus.services.exceptions import ValidationBadRequestError
from pegasus.validation.fixed_width_meta import normalize_file_format


def merge_paths_for_format(
    paths: list[Path],
    *,
    file_format: str,
    destination: Path,
    delimiter: str = ",",
    has_header: bool = True,
) -> Path:
    """Concatenate *paths* into *destination* according to *file_format*."""
    if not paths:
        raise ValidationBadRequestError("At least one file path is required to merge")
    if len(paths) == 1:
        return paths[0].resolve()

    fmt = normalize_file_format(file_format)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        return _merge_json_files(paths, destination)
    if fmt == "fixed-width":
        return _merge_text_lines(paths, destination)
    return _merge_csv_files(paths, destination, delimiter=delimiter, has_header=has_header)


def _merge_text_lines(paths: list[Path], destination: Path) -> Path:
    with destination.open("wb") as out:
        for idx, path in enumerate(paths):
            data = path.read_bytes()
            if idx > 0 and data and not data.startswith(b"\n") and out.tell() > 0:
                out.write(b"\n")
            out.write(data)
            if data and not data.endswith(b"\n"):
                out.write(b"\n")
    return destination.resolve()


def _merge_csv_files(
    paths: list[Path],
    destination: Path,
    *,
    delimiter: str,
    has_header: bool,
) -> Path:
    delim = delimiter if delimiter else ","
    if len(delim) != 1:
        delim = ","
    with destination.open("w", encoding="utf-8", newline="") as out:
        for idx, path in enumerate(paths):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            if not lines:
                continue
            start = 0
            if has_header and idx > 0:
                start = 1
            chunk = "\n".join(lines[start:])
            if not chunk:
                continue
            if out.tell() > 0:
                out.write("\n")
            out.write(chunk)
    return destination.resolve()


def _parse_json_file(path: Path) -> Any:
    """Parse one JSON file as a single document (whole file or NDJSON lines → list)."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationBadRequestError(f"Cannot read JSON file: {path}") from exc
    if not raw.strip():
        raise ValidationBadRequestError(f"Empty JSON file: {path}")

    try:
        return loads_bytes(raw)
    except (ValueError, TypeError):
        pass

    values: list[Any] = []
    text = raw.decode("utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            values.append(loads_str(stripped))
        except (ValueError, TypeError) as exc:
            raise ValidationBadRequestError(
                f"Invalid JSON in {path.name} line {line_no}: {exc}"
            ) from exc
    if not values:
        raise ValidationBadRequestError(f"No JSON content in {path.name}")
    if len(values) == 1:
        return values[0]
    return values


def _merge_json_files(paths: list[Path], destination: Path) -> Path:
    """Merge heterogeneous JSON shards into one document for comparison."""
    docs = [_parse_json_file(path) for path in paths]
    if len(docs) == 1:
        payload: Any = docs[0]
    elif all(isinstance(doc, list) for doc in docs):
        payload = [item for doc in docs for item in doc]
    elif all(isinstance(doc, dict) for doc in docs):
        payload = {}
        for doc in docs:
            assert isinstance(doc, dict)
            payload.update(doc)
    else:
        payload = docs

    destination.write_bytes(dumps_bytes(payload))
    return destination.resolve()
