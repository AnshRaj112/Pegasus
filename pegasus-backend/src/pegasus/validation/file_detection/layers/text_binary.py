# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-27T14:34:28Z
# --- END GENERATED FILE METADATA ---

"""Layer 6: text vs binary classification."""

from __future__ import annotations

import math
from collections import Counter

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage


def detect_text_binary(sample: FileSample, encoding: DetectionStage | None) -> DetectionStage:
    raw = sample.raw
    if not raw:
        return DetectionStage("unknown", 10, evidence=["empty sample"])

    if encoding and encoding.detected_type.startswith("utf"):
        return DetectionStage(
            detected_type="text",
            confidence=min(95, encoding.confidence),
            evidence=["encoding layer indicates text"],
            metadata={"entropy": _shannon_entropy(raw)},
        )

    null_ratio = raw.count(0) / len(raw)
    printable = sum(1 for b in raw if 32 <= b <= 126 or b in (9, 10, 13)) / len(raw)
    entropy = _shannon_entropy(raw)

    if null_ratio > 0.05:
        return DetectionStage(
            detected_type="binary",
            confidence=90,
            evidence=[f"null_byte_ratio={null_ratio:.3f}"],
            metadata={"printable_ratio": printable, "entropy": entropy},
        )
    if printable >= 0.85 and entropy < 6.5:
        return DetectionStage(
            detected_type="text",
            confidence=82,
            evidence=[f"printable_ratio={printable:.3f}", f"entropy={entropy:.2f}"],
            metadata={"null_byte_ratio": null_ratio},
        )
    if printable < 0.4:
        return DetectionStage(
            detected_type="binary",
            confidence=80,
            evidence=[f"low printable_ratio={printable:.3f}"],
            metadata={"entropy": entropy},
        )
    return DetectionStage(
        detected_type="unknown",
        confidence=40,
        evidence=[f"ambiguous printable={printable:.3f} entropy={entropy:.2f}"],
        metadata={"null_byte_ratio": null_ratio},
    )


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
