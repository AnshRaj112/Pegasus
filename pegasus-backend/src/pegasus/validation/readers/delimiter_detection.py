# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T07:38:07Z
# --- END GENERATED FILE METADATA ---

"""Delimiter detection utilities for messy CSV inputs."""

from __future__ import annotations

import csv
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import clevercsv

from pegasus.validation.flat_file import field_count

# Sniff delimiters from a bounded prefix only (never read multi‑GiB files into RAM).
_DEFAULT_SNIFF_PREFIX_BYTES = 512 * 1024
_DEFAULT_SNIFF_MAX_LINES = 500


def _read_utf8_prefix(path: Path, *, max_bytes: int = _DEFAULT_SNIFF_PREFIX_BYTES) -> str:
    """Read up to *max_bytes* from *path* and decode as UTF-8 (replacement on errors)."""
    with path.open("rb") as fh:
        raw = fh.read(max_bytes)
    return raw.decode("utf-8", errors="replace")


def _sample_non_empty_lines(
    path: Path,
    *,
    max_bytes: int = _DEFAULT_SNIFF_PREFIX_BYTES,
    max_lines: int = _DEFAULT_SNIFF_MAX_LINES,
) -> list[str]:
    """Read a bounded number of non-empty lines from a bounded byte prefix."""
    out: list[str] = []
    consumed = 0
    with path.open("rb") as fh:
        while consumed < max_bytes and len(out) < max_lines:
            raw = fh.readline()
            if not raw:
                break
            consumed += len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                out.append(line)
    return out


@dataclass(slots=True)
class DelimiterDetectionResult:
    """Detected delimiter and metadata for observability."""

    delimiter: str
    strategy: str


def polars_supports_csv_delimiter(delimiter: str) -> bool:
    """True when *delimiter* can be passed to Polars ``scan_csv``/``read_csv``.

    Polars requires a single-byte separator. Multi-character tokens (``xx``,
    ``||``) and single Unicode code points that encode to multiple UTF-8 bytes
    (e.g. ``🚀``) must use the pandas fallback parser instead.
    """
    return len(delimiter) == 1 and len(delimiter.encode("utf-8")) == 1


def resolve_shared_auto_delimiter(
    source_path: Path,
    target_path: Path,
    *,
    source_lines: list[str] | None = None,
    target_lines: list[str] | None = None,
) -> DelimiterDetectionResult:
    """Pick one delimiter that fits **both** files when per-file sniffers disagree.

    ``detect_delimiter`` runs independently on each path; real pipelines sometimes
    yield different guesses (sample variance, header quirks). This helper scores a
    small candidate set on both files and returns the strongest shared delimiter.

    Raises
    ------
    ValueError
        If no candidate produces stable, matching field counts on both sides.
    """
    left = (
        detect_delimiter_from_lines(source_lines, path=source_path)
        if source_lines is not None
        else detect_delimiter(source_path)
    )
    right = (
        detect_delimiter_from_lines(target_lines, path=target_path)
        if target_lines is not None
        else detect_delimiter(target_path)
    )
    if left.delimiter == right.delimiter:
        return DelimiterDetectionResult(
            delimiter=left.delimiter,
            strategy=f"per-file-agree:{left.strategy}",
        )

    candidates: list[str] = []
    for d in (
        left.delimiter,
        right.delimiter,
        ",",
        ";",
        "\t",
        "|",
        "||",
        "::",
        "xx",
    ):
        if d not in candidates:
            candidates.append(d)

    best: str | None = None
    best_rank: tuple[int, float] = (-1, float("-inf"))

    for delim in candidates:
        q = _pair_delimiter_quality(source_path, target_path, delim)
        if q is None:
            continue
        # Prefer same modal field count on both sides, then higher stability score.
        rank = (1 if q.modes_match else 0, q.score)
        if rank > best_rank:
            best_rank = rank
            best = delim

    if best is None:
        raise ValueError(
            "Could not infer a shared delimiter automatically "
            f"(source_hint={left.delimiter!r}, target_hint={right.delimiter!r}). "
            "Please set delimiter explicitly in the request."
        )
    return DelimiterDetectionResult(delimiter=best, strategy="shared-auto-resolve")


def _pair_delimiter_quality(source_path: Path, target_path: Path, delim: str) -> _PairDelimiterQuality | None:
    m1, s1 = _file_delimiter_stability(source_path, delim)
    m2, s2 = _file_delimiter_stability(target_path, delim)
    if m1 is None or m2 is None:
        return None
    modes_match = m1 == m2
    score = min(s1, s2)
    return _PairDelimiterQuality(modes_match=modes_match, score=score)


@dataclass(slots=True)
class _PairDelimiterQuality:
    modes_match: bool
    score: float


def _file_delimiter_stability(path: Path, delim: str) -> tuple[int | None, float]:
    """Return ``(modal_field_count, score)`` or ``(None, _)`` if *delim* is a poor fit."""
    lines = _sample_non_empty_lines(path, max_lines=500)
    if len(lines) < 2:
        return None, float("-inf")

    counts = [field_count(ln, delim) for ln in lines]
    mode_value, mode_freq = Counter(counts).most_common(1)[0]
    if mode_value < 2:
        return None, float("-inf")

    consistency = mode_freq / len(counts)
    if consistency < 0.90:
        return None, float("-inf")

    matched = [c for c in counts if c == mode_value]
    var = statistics.pvariance(matched) if len(matched) > 1 else 0.0
    score = consistency * 100.0 - var
    return mode_value, score


def _sniffer_delimiter_hints(sample_text: str) -> list[str]:
    """Optional delimiter hints from dialect sniffers (validated later)."""
    hints: list[str] = []
    try:
        dialect = clevercsv.Sniffer().sniff(sample_text)
        delim = getattr(dialect, "delimiter", None)
        if delim and delim not in hints:
            hints.append(delim)
    except Exception:
        pass
    try:
        dialect = csv.Sniffer().sniff(sample_text)
        delim = getattr(dialect, "delimiter", None)
        if delim and delim not in hints:
            hints.append(delim)
    except Exception:
        pass
    return hints


def _delimiter_candidate_tokens(header: str) -> list[str]:
    """Single- and multi-character delimiter candidates for one file."""
    single = [",", ";", "|", "\t", ":", "\x1f", "\x1e", "\x1d"]
    multi = _multi_char_candidates(header)
    merged: list[str] = []
    for token in (*single, *multi):
        if token and token not in merged:
            merged.append(token)
    return merged


def _pick_best_delimiter(
    lines: list[str],
    *,
    extra_candidates: list[str] | None = None,
) -> DelimiterDetectionResult | None:
    """Choose the delimiter with the most stable quote-aware field counts."""
    header = lines[0]
    candidates = _delimiter_candidate_tokens(header)
    for token in extra_candidates or []:
        if token and token not in candidates:
            candidates.append(token)

    scored: list[tuple[int, float, float, int, str]] = []
    for cand in candidates:
        row = _score_delimiter_candidate(lines, cand)
        if row is not None:
            scored.append(row)
    if not scored:
        return None

    scored.sort(reverse=True)
    best_row = scored[0]
    best = best_row[4]
    if len(best) == 1:
        strategy = "heuristic-single-char"
    elif best in (extra_candidates or []):
        strategy = "clevercsv" if extra_candidates and best == extra_candidates[0] else "csv-sniffer"
    else:
        strategy = "heuristic-multi-char"
    return DelimiterDetectionResult(delimiter=best, strategy=strategy)


def detect_delimiter_from_lines(
    lines: list[str],
    *,
    path: Path | None = None,
) -> DelimiterDetectionResult:
    """Detect delimiter from pre-loaded sample lines (avoids extra file read)."""
    if not lines:
        name = path.name if path is not None else "file"
        raise ValueError(f"Cannot infer delimiter for empty file: {name}")
    sample_lines = lines[:100]
    sample_text = "\n".join(sample_lines)
    hints = _sniffer_delimiter_hints(sample_text)
    picked = _pick_best_delimiter(sample_lines, extra_candidates=hints)
    if picked is not None:
        return picked
    name = path.name if path is not None else "file"
    raise ValueError(f"Could not infer delimiter for {name}; please provide delimiter explicitly")


def detect_delimiter(path: Path) -> DelimiterDetectionResult:
    """Detect delimiter using quote-aware scoring over all plausible candidates.

    RFC 4180 comma files with quoted JSON/list cells are scored with the same
    quote-aware :func:`~pegasus.validation.flat_file.field_count` used at validation
    time, so commas inside ``"[1, 2, 3]"`` do not beat the real field separator.
    """
    lines = _sample_non_empty_lines(path)
    return detect_delimiter_from_lines(lines, path=path)


def _repeated_substring_candidates(
    header: str,
    *,
    min_len: int = 2,
    max_len: int = 8,
    min_occurrences: int = 2,
) -> list[str]:
    """Substrings that repeat in the header (covers alphabetic delimiters like ``xx``)."""
    if len(header) < min_len:
        return []
    counts: Counter[str] = Counter()
    upper = min(max_len, len(header))
    for length in range(min_len, upper + 1):
        for start in range(len(header) - length + 1):
            counts[header[start : start + length]] += 1
    return [token for token, freq in counts.items() if freq >= min_occurrences]


def _multi_char_candidates(header: str) -> list[str]:
    """Build delimiter candidates for multi-character detection."""
    # Symbol-heavy tokens: "||", "::", tab combinations, etc.
    symbolic = re.findall(r"[^A-Za-z0-9_\"']{2,}", header)
    repeated = _repeated_substring_candidates(header)
    merged: list[str] = []
    for token in (*symbolic, *repeated):
        if not token or token in merged:
            continue
        merged.append(token)
    return sorted(merged, key=len, reverse=True)


def _score_delimiter_candidate(lines: list[str], cand: str) -> tuple[int, float, float, int, str] | None:
    fields = [field_count(line, cand) for line in lines]
    active = [f for f in fields if f > 1]
    if len(active) < max(2, len(lines) // 3):
        return None
    variance = statistics.pvariance(fields) if len(fields) > 1 else 0.0
    mode_value, mode_freq = Counter(fields).most_common(1)[0]
    consistency = mode_freq / len(fields)
    if consistency < 0.85:
        return None
    # Prefer stable parses; when tied, prefer the longer delimiter token (``xx`` over ``x``,
    # ``~\^|~`` over ``~``) so substrings inside real separators are not chosen.
    return (len(active), -variance, consistency, len(cand), cand)


def _detect_multi_char_delimiter(lines: list[str]) -> str | None:
    """Legacy helper; prefer :func:`_pick_best_delimiter`."""
    picked = _pick_best_delimiter(lines)
    if picked is None or len(picked.delimiter) == 1:
        return None
    return picked.delimiter


def _detect_single_char_delimiter(lines: list[str]) -> str | None:
    """Legacy helper; prefer :func:`_pick_best_delimiter`."""
    picked = _pick_best_delimiter(lines)
    if picked is None or len(picked.delimiter) != 1:
        return None
    return picked.delimiter
