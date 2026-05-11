"""Delimiter detection utilities for messy CSV inputs."""

from __future__ import annotations

import csv
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import clevercsv


@dataclass(slots=True)
class DelimiterDetectionResult:
    """Detected delimiter and metadata for observability."""

    delimiter: str
    strategy: str


def detect_delimiter(path: Path) -> DelimiterDetectionResult:
    """Detect delimiter using package-first strategy with safe fallbacks.

    Order:
    1) multi-character heuristic (because dialect detectors typically assume one char)
    2) clevercsv sniffer
    3) stdlib csv.Sniffer
    4) common-candidates score fallback
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"Cannot infer delimiter for empty file: {path.name}")
    sample_lines = lines[:100]

    multi = _detect_multi_char_delimiter(sample_lines)
    if multi is not None:
        return DelimiterDetectionResult(delimiter=multi, strategy="heuristic-multi-char")

    sample_text = "\n".join(sample_lines)
    try:
        dialect = clevercsv.Sniffer().sniff(sample_text)
        if getattr(dialect, "delimiter", None):
            return DelimiterDetectionResult(delimiter=dialect.delimiter, strategy="clevercsv")
    except Exception:
        pass

    try:
        dialect2 = csv.Sniffer().sniff(sample_text)
        if getattr(dialect2, "delimiter", None):
            return DelimiterDetectionResult(delimiter=dialect2.delimiter, strategy="csv-sniffer")
    except Exception:
        pass

    single = _detect_single_char_delimiter(sample_lines)
    if single is None:
        raise ValueError(
            f"Could not infer delimiter for {path.name}; please provide delimiter explicitly"
        )
    return DelimiterDetectionResult(delimiter=single, strategy="heuristic-single-char")


def _detect_multi_char_delimiter(lines: list[str]) -> str | None:
    header = lines[0]
    # Candidate tokens between potential fields, e.g. "||", "::", "\t|"
    raw = re.findall(r"[^A-Za-z0-9_\"']{2,}", header)
    candidates = sorted({tok for tok in raw if tok.strip()}, key=len, reverse=True)
    if not candidates:
        return None

    scored: list[tuple[int, float, float, str]] = []
    for cand in candidates:
        counts = [line.count(cand) for line in lines]
        active = [c for c in counts if c > 0]
        if len(active) < max(2, len(lines) // 3):
            continue
        fields = [c + 1 for c in active]
        variance = statistics.pvariance(fields) if len(fields) > 1 else 0.0
        scored.append((len(active), -variance, sum(fields) / len(fields), cand))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][3]


def _detect_single_char_delimiter(lines: list[str]) -> str | None:
    candidates = [",", ";", "|", "\t", ":", "\x1f", "\x1e", "\x1d"]
    scored: list[tuple[int, float, float, str]] = []
    for cand in candidates:
        counts = [line.count(cand) for line in lines]
        active = [c for c in counts if c > 0]
        if not active:
            continue
        fields = [c + 1 for c in active]
        variance = statistics.pvariance(fields) if len(fields) > 1 else 0.0
        scored.append((len(active), -variance, sum(fields) / len(fields), cand))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][3]
