# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:10:34Z
# --- END GENERATED FILE METADATA ---

"""Layer 9: validation strategy and dataset model selection."""

from __future__ import annotations

from pegasus.validation.file_detection.plugins.registry import apply_format_plugins
from pegasus.validation.file_detection.types import DetectionStage
from pegasus.validation.file_format import is_columnar_format, normalize_file_format

_COLUMNAR = frozenset({"parquet", "orc", "avro", "excel"})
_HIERARCHICAL = frozenset({"json"})
_TABULAR = frozenset({"csv", "tsv", "psv", "fixed-width"})
_CONTAINERS = frozenset({"zip", "tar", "7z", "rar"})
_COMPRESSION = frozenset({"gzip", "bzip2", "xz", "zstd", "lz4"})


def select_validation_strategy(
    *,
    extension: DetectionStage | None,
    magic: DetectionStage | None,
    container: DetectionStage | None,
    compression: DetectionStage | None,
    encoding: DetectionStage | None,
    structured: DetectionStage | None,
    user_format_hint: str | None,
) -> tuple[DetectionStage, str, str | None, str | None, list[str]]:
    """Return (strategy stage, dataset_model, suggested_file_format, delimiter, warnings)."""
    warnings: list[str] = []
    candidates: list[tuple[str, int, str]] = []

    def add(kind: str, conf: int, source: str) -> None:
        if conf > 0:
            candidates.append((kind, conf, source))

    if structured and structured.confidence >= 60:
        add(structured.detected_type, structured.confidence, "structured")
        if structured.metadata.get("delimiter"):
            pass
    if magic and magic.confidence >= 70:
        magic_type = magic.detected_type
        structured_tabular = (
            structured
            and structured.confidence >= 60
            and structured.detected_type in {"fixed-width", "csv", "tsv", "psv"}
        )
        if not (magic_type == "text" and structured_tabular):
            add(magic_type, magic.confidence, "magic")
    if compression and compression.detected_type != "none" and compression.confidence >= 80:
        add(compression.detected_type, compression.confidence, "compression")
    if container and container.detected_type not in {"none"} and container.confidence >= 70:
        add(container.detected_type, container.confidence, "container")
    if extension and extension.confidence >= 20:
        add(extension.detected_type, extension.confidence, "extension")

    plugin = apply_format_plugins(candidates)
    if plugin:
        candidates.append((plugin.detected_type, plugin.confidence, "plugin"))

    hint = normalize_file_format(user_format_hint) if user_format_hint else None
    if hint and hint != "auto":
        candidates.append((hint, 45, "user_hint"))

    if not candidates:
        stage = DetectionStage("unknown", 15, evidence=["insufficient signals"])
        return stage, "unknown", None, None, warnings

    candidates.sort(key=lambda x: x[1], reverse=True)
    best_kind, best_conf, best_src = candidates[0]

    if extension and extension.detected_type != best_kind and extension.confidence >= 30:
        if best_conf >= 70:
            warnings.append(
                f"extension suggests {extension.detected_type!r} but content suggests {best_kind!r}"
            )

    if best_conf < 50:
        stage = DetectionStage(
            "unknown",
            best_conf,
            evidence=[f"low confidence best={best_kind!r} from {best_src}"],
        )
        return stage, "unknown", None, None, warnings

    if compression and compression.detected_type in _COMPRESSION and best_kind in _COMPRESSION:
        stage = DetectionStage(
            "decompress_first",
            compression.confidence,
            evidence=["compressed payload must be decompressed before validation"],
            metadata={"compression": compression.detected_type},
        )
        return stage, "binary_asset", None, None, warnings

    if encoding and encoding.metadata.get("strategy_hint") == "transcode_first":
        stage = DetectionStage(
            "transcode_first",
            encoding.confidence,
            evidence=[f"encoding={encoding.detected_type}"],
            metadata={},
        )
        return stage, "binary_asset", None, None, warnings

    if best_kind in _CONTAINERS or (container and container.detected_type not in {"none", ""}):
        stage = DetectionStage(
            "container",
            max(best_conf, container.confidence if container else 0),
            evidence=["archive container — inspect entries before validation"],
            metadata=container.metadata if container else {},
        )
        return stage, "container", None, None, warnings

    if best_kind in _COLUMNAR or is_columnar_format(best_kind):
        fmt = "excel" if best_kind in {"excel-ole", "xlsx"} else best_kind
        if fmt == "excel-ole":
            fmt = "excel"
        stage = DetectionStage(
            fmt,
            best_conf,
            evidence=[f"columnar route {fmt!r} from {best_src}"],
            metadata={"pegasus_route": fmt},
        )
        return stage, "binary_asset", fmt, None, warnings

    if best_kind in _HIERARCHICAL or best_kind == "json":
        stage = DetectionStage("json", best_conf, evidence=[f"resolved from {best_src}"])
        return stage, "hierarchical", "json", None, warnings

    if best_kind == "fixed-width":
        stage = DetectionStage("fixed-width", best_conf, evidence=[f"resolved from {best_src}"])
        return stage, "tabular", "fixed-width", None, warnings

    ambiguous_tabular = (
        extension is not None
        and extension.metadata.get("ambiguous_tabular")
        and not (structured and structured.confidence >= 60)
    )

    _DELIMITED_EXTENSIONS = {".csv", ".tsv", ".psv"}

    if best_kind == "text" and not (structured and structured.confidence >= 60):
        ext = str(extension.metadata.get("extension", "") if extension else "").lower()
        if ext in _DELIMITED_EXTENSIONS:
            fmt = "tsv" if ext == ".tsv" else "psv" if ext == ".psv" else "csv"
            stage = DetectionStage(fmt, best_conf, evidence=[f"text/plain with {ext} extension"])
            return stage, "tabular", fmt, None, warnings
        stage = DetectionStage(
            "txt",
            best_conf,
            evidence=["generic text without tabular structure"],
        )
        return stage, "unknown", None, None, warnings

    if best_kind in _TABULAR or best_kind in {"csv", "tsv", "psv", "text"}:
        if ambiguous_tabular and best_kind == "text":
            stage = DetectionStage(
                "txt",
                best_conf,
                evidence=["plain text without delimited/fixed-width structure"],
            )
            return stage, "unknown", None, None, warnings
        fmt = best_kind if best_kind in {"csv", "tsv", "psv"} else "csv"
        delim = None
        if structured and structured.metadata.get("delimiter"):
            delim = structured.metadata["delimiter"]
        stage = DetectionStage(fmt, best_conf, evidence=[f"tabular route from {best_src}"])
        return stage, "tabular", fmt, delim, warnings

    if best_kind == "txt" and ambiguous_tabular:
        stage = DetectionStage(
            "txt",
            best_conf,
            evidence=["ambiguous tabular suffix without structure match"],
        )
        return stage, "unknown", None, None, warnings

    if best_kind == "xml" or best_kind == "yaml":
        stage = DetectionStage("unknown", 40, evidence=[f"{best_kind} not yet supported for validation"])
        return stage, "unknown", None, None, warnings + [f"{best_kind} validation not implemented"]

    stage = DetectionStage("unknown", best_conf, evidence=[f"unmapped kind={best_kind!r}"])
    return stage, "unknown", None, None, warnings
