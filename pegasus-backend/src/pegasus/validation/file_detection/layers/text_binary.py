"""Layer 6: text vs binary classification."""

from __future__ import annotations

import math
from collections import Counter

from pegasus.validation.file_detection.models import DetectionStageResult, TextBinaryClass
from pegasus.validation.file_detection.sampling import FileSample


def classify_text_binary(
    sample: FileSample,
    *,
    compression_result: DetectionStageResult | None = None,
    magic_result: DetectionStageResult | None = None,
) -> DetectionStageResult:
    if compression_result and compression_result.detected_type not in {"none", "unknown"}:
        return DetectionStageResult(
            TextBinaryClass.BINARY.value,
            85,
            [f"compressed ({compression_result.detected_type})"],
        )

    if magic_result and magic_result.detected_type in {
        "parquet",
        "orc",
        "avro",
        "png",
        "pdf",
        "elf",
        "gzip",
        "zip",
        "7z",
        "rar",
    }:
        return DetectionStageResult(
            TextBinaryClass.BINARY.value,
            magic_result.confidence,
            [f"magic indicates binary ({magic_result.detected_type})"],
        )

    data = sample.prefix_8k
    if not data:
        return DetectionStageResult(TextBinaryClass.UNKNOWN.value, 50, ["empty"])

    null_ratio = data.count(0) / len(data)
    printable = sum(1 for b in data if 32 <= b <= 126 or b in (9, 10, 13))
    printable_ratio = printable / len(data)
    entropy = _shannon_entropy(data)

    evidence = [
        f"printable_ratio={printable_ratio:.3f}",
        f"null_ratio={null_ratio:.3f}",
        f"entropy={entropy:.2f}",
    ]

    if null_ratio > 0.05 and printable_ratio < 0.7:
        return DetectionStageResult(
            TextBinaryClass.BINARY.value,
            80,
            evidence + ["elevated null bytes"],
        )

    if printable_ratio >= 0.85 and null_ratio < 0.01:
        return DetectionStageResult(
            TextBinaryClass.TEXT.value,
            min(95, int(printable_ratio * 100)),
            evidence,
        )

    if entropy > 7.5 and printable_ratio < 0.5:
        return DetectionStageResult(
            TextBinaryClass.BINARY.value,
            70,
            evidence + ["high entropy"],
        )

    if printable_ratio >= 0.6:
        return DetectionStageResult(
            TextBinaryClass.TEXT.value,
            int(printable_ratio * 80),
            evidence,
        )

    return DetectionStageResult(
        TextBinaryClass.UNKNOWN.value,
        40,
        evidence,
    )


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
