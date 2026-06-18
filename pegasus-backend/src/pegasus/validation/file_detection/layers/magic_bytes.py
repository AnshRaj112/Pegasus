# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Layer 2: magic-byte and MIME detection (bounded prefix)."""

from __future__ import annotations

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage

_BUILTIN_SIGNATURES: list[tuple[bytes, str, str, int]] = [
    (b"\x1f\x8b", "gzip", "application/gzip", 92),
    (b"BZh", "bzip2", "application/x-bzip2", 90),
    (b"\xfd7zXZ\x00", "xz", "application/x-xz", 90),
    (b"\x28\xb5\x2f\xfd", "zstd", "application/zstd", 90),
    (b"\x04\x22\x4d\x18", "lz4", "application/x-lz4", 88),
    (b"PK\x03\x04", "zip", "application/zip", 95),
    (b"PK\x05\x06", "zip", "application/zip", 90),
    (b"PK\x07\x08", "zip", "application/zip", 90),
    (b"\x37\x7a\xbc\xaf\x27\x1c", "7z", "application/x-7z-compressed", 95),
    (b"Rar!\x1a\x07", "rar", "application/vnd.rar", 95),
    (b"PAR1", "parquet", "application/vnd.apache.parquet", 98),
    (b"ORC", "orc", "application/orc", 95),
    (b"Obj\x01", "avro", "application/avro", 90),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png", 98),
    (b"%PDF", "pdf", "application/pdf", 98),
    (b"{", "json", "application/json", 55),
    (b"[", "json", "application/json", 50),
    (b"<?xml", "xml", "application/xml", 85),
    (b"\xef\xbb\xbf", "utf-8-bom", "text/plain", 70),
    (b"\xff\xfe", "utf-16-le", "text/plain", 80),
    (b"\xfe\xff", "utf-16-be", "text/plain", 80),
    (b"\xff\xfe\x00\x00", "utf-32-le", "text/plain", 75),
    (b"\x00\x00\xfe\xff", "utf-32-be", "text/plain", 75),
    (b"\xd0\xcf\x11\xe0", "excel-ole", "application/vnd.ms-excel", 90),
]

_EXCEL_ZIP = b"PK\x03\x04"


def _builtin_magic(prefix: bytes, suffix_4: bytes) -> DetectionStage | None:
    for sig, kind, mime, conf in _BUILTIN_SIGNATURES:
        if prefix.startswith(sig):
            return DetectionStage(
                detected_type=kind,
                confidence=conf,
                evidence=[f"builtin signature {sig[:8]!r}"],
                metadata={"mime": mime, "source": "builtin"},
            )
    if prefix.startswith(_EXCEL_ZIP):
        return DetectionStage(
            detected_type="zip",
            confidence=85,
            evidence=["ZIP local header (may be xlsx/docx)"],
            metadata={"mime": "application/zip", "source": "builtin"},
        )
    if suffix_4 == b"PAR1" and len(prefix) >= 4:
        return DetectionStage(
            detected_type="parquet",
            confidence=98,
            evidence=["footer magic PAR1"],
            metadata={"mime": "application/vnd.apache.parquet", "source": "builtin"},
        )
    return None


def _try_python_magic(prefix: bytes) -> DetectionStage | None:
    try:
        import magic  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        mime = magic.from_buffer(prefix, mime=True)
        desc = magic.from_buffer(prefix)
    except Exception:
        return None
    if not mime or mime == "application/octet-stream":
        return None
    kind = _mime_to_kind(mime, desc)
    return DetectionStage(
        detected_type=kind,
        confidence=88,
        evidence=[f"libmagic mime={mime!r}", f"description={desc!r}"],
        metadata={"mime": mime, "description": desc, "source": "python-magic"},
    )


def _try_filetype(prefix: bytes) -> DetectionStage | None:
    try:
        import filetype
    except ImportError:
        return None
    kind = filetype.guess(prefix)
    if kind is None:
        return None
    return DetectionStage(
        detected_type=kind.extension or kind.mime.split("/")[-1],
        confidence=82,
        evidence=[f"filetype extension={kind.extension!r}", f"mime={kind.mime!r}"],
        metadata={"mime": kind.mime, "source": "filetype"},
    )


def _try_puremagic(prefix: bytes) -> DetectionStage | None:
    try:
        import puremagic
    except ImportError:
        return None
    try:
        matches = puremagic.magic_string(prefix)
    except Exception:
        return None
    if not matches:
        return None
    best = matches[0]
    ext = (best.extension or "").lstrip(".") or "unknown"
    return DetectionStage(
        detected_type=ext,
        confidence=78,
        evidence=[f"puremagic name={best.name!r}", f"extension={best.extension!r}"],
        metadata={"mime": getattr(best, "mime_type", None), "source": "puremagic"},
    )


def _mime_to_kind(mime: str, description: str) -> str:
    m = mime.lower()
    if "gzip" in m:
        return "gzip"
    if "zip" in m:
        return "zip"
    if "json" in m:
        return "json"
    if "xml" in m:
        return "xml"
    if "csv" in m or "comma-separated" in description.lower():
        return "csv"
    if "parquet" in m:
        return "parquet"
    if "orc" in m:
        return "orc"
    if "avro" in m:
        return "avro"
    if "spreadsheet" in m or "excel" in m:
        return "excel"
    if m.startswith("text/"):
        return "text"
    return m.split("/")[-1] if "/" in m else mime


def detect_magic_bytes(sample: FileSample) -> DetectionStage:
    prefix = sample.prefix_8k
    suffix_4 = sample.suffix_4
    builtin = _builtin_magic(prefix, suffix_4)
    if builtin and builtin.confidence >= 85:
        return builtin

    for fn in (_try_python_magic, _try_filetype, _try_puremagic):
        stage = fn(prefix)
        if stage and stage.confidence >= 78:
            return stage

    if builtin:
        return builtin

    if _looks_like_tar(sample):
        return DetectionStage(
            detected_type="tar",
            confidence=80,
            evidence=["ustar header at offset 257"],
            metadata={"mime": "application/x-tar", "source": "builtin"},
        )

    return DetectionStage(
        detected_type="unknown",
        confidence=15,
        evidence=["no magic signature matched"],
        metadata={},
    )


def _looks_like_tar(sample: FileSample) -> bool:
    if len(sample.raw) < 512:
        return False
    try:
        with sample.path.open("rb") as fh:
            fh.seek(257)
            marker = fh.read(5)
        return marker in (b"ustar", b"ustar\x00")
    except OSError:
        return False
