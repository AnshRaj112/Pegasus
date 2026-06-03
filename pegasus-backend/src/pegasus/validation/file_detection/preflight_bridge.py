"""Bridge detection layers to legacy CSV preflight errors."""

from __future__ import annotations

from pegasus.validation.preflight_errors import CsvPreflightError
from pegasus.validation.file_detection.layers.compression import detect_compression
from pegasus.validation.file_detection.layers.encoding import detect_encoding
from pegasus.validation.file_detection.layers.magic_bytes import detect_magic_bytes
from pegasus.validation.file_detection.sampling import FileSample

GZIP_MAGIC = b"\x1f\x8b"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
UTF8_BOM = b"\xef\xbb\xbf"


def check_csv_prefix_bytes(prefix: bytes, *, label: str) -> None:
    """Raise :class:`CsvPreflightError` when prefix indicates unsupported encoding/compression."""
    if not prefix:
        return
    if prefix == UTF8_BOM:
        raise CsvPreflightError(f"{label}: file contains only a UTF-8 BOM and no CSV content.")

    sample = FileSample(
        path=__import__("pathlib").Path(label),
        file_size_bytes=len(prefix),
        prefix=prefix,
        prefix_4k=prefix[:4096],
        prefix_8k=prefix[:8192],
    )
    magic = detect_magic_bytes(sample)
    compression = detect_compression(sample, magic_result=magic)
    encoding = detect_encoding(sample, magic_result=magic)

    if compression.detected_type == "gzip" or prefix.startswith(GZIP_MAGIC):
        raise CsvPreflightError(
            f"{label}: file looks gzip-compressed (not plain CSV). Decompress before validating."
        )
    if encoding.detected_type in {"utf-16-le", "utf-16-be", "utf-16"} or prefix.startswith(
        (UTF16_LE_BOM, UTF16_BE_BOM)
    ):
        raise CsvPreflightError(
            f"{label}: UTF-16 byte order mark detected; save the file as UTF-8 before validating."
        )
