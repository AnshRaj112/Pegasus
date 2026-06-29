# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""Value canonicalization engine for deterministic fingerprinting."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from category1.config import ReconciliationConfig


class CanonicalizationEngine:
    """Normalizes values before fingerprinting and comparison."""

    def __init__(self, config: Optional[ReconciliationConfig] = None, overrides: Optional[dict] = None):
        self.config = config or ReconciliationConfig()
        if overrides:
            for k, v in overrides.items():
                if hasattr(self.config, k):
                    setattr(self.config, k, v)
        self._null_set = {s.lower() for s in self.config.null_representations}

    def canonicalize_value(self, value: Any, data_type: str = "string") -> str:
        if value is None:
            return "__NULL__"

        text = str(value)
        if self._is_null_representation(text):
            return "__NULL__"

        if self.config.trim_whitespace:
            text = text.strip()

        if not self.config.case_sensitive and data_type in ("string", "varchar", "text", "char"):
            text = text.lower()

        dtype = data_type.lower()
        if dtype in ("decimal", "numeric", "float", "double", "real", "number"):
            return self._canonicalize_decimal(text)
        if dtype in ("date",):
            return self._canonicalize_date(text)
        if dtype in ("timestamp", "datetime", "timestamptz"):
            return self._canonicalize_timestamp(text)
        if dtype in ("integer", "int", "bigint", "smallint"):
            return self._canonicalize_integer(text)
        if dtype in ("boolean", "bool"):
            return self._canonicalize_boolean(text)

        return text

    def canonicalize_record(
        self,
        record: dict[str, Any],
        columns: list[str],
        column_types: Optional[dict[str, str]] = None,
        column_mapping: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        types = column_types or {}
        mapping = column_mapping or {}
        result: dict[str, str] = {}
        for col in columns:
            mapped = mapping.get(col, col)
            raw = record.get(mapped)
            dtype = types.get(col, "string")
            result[col] = self.canonicalize_value(raw, dtype)
        return result

    def _is_null_representation(self, text: str) -> bool:
        return text.strip().lower() in self._null_set

    def _canonicalize_decimal(self, text: str) -> str:
        try:
            d = Decimal(text.replace(",", ""))
            if self.config.decimal_precision is not None:
                quantize_str = "0." + "0" * self.config.decimal_precision
                d = d.quantize(Decimal(quantize_str))
            normalized = format(d.normalize(), "f")
            if "." in normalized:
                normalized = normalized.rstrip("0").rstrip(".")
            return normalized if normalized else "0"
        except (InvalidOperation, ValueError):
            return text

    def _canonicalize_date(self, text: str) -> str:
        for fmt in (self.config.date_format, "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(text.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return text

    def _canonicalize_timestamp(self, text: str) -> str:
        formats = [
            self.config.timestamp_format,
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        for fmt in formats:
            try:
                clean = text.strip().replace("Z", "")
                if "." in clean and "T" in clean:
                    clean = clean.split(".")[0]
                dt = datetime.strptime(clean[:19], fmt[: min(len(fmt), 19)])
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        return text

    def _canonicalize_integer(self, text: str) -> str:
        try:
            return str(int(float(text.replace(",", ""))))
        except (ValueError, OverflowError):
            return text

    def _canonicalize_boolean(self, text: str) -> str:
        lower = text.strip().lower()
        if lower in ("true", "1", "yes", "y", "t"):
            return "true"
        if lower in ("false", "0", "no", "n", "f"):
            return "false"
        return text

    @staticmethod
    def harmonize_type(source_type: str, target_type: str) -> tuple[str, str]:
        """Map heterogeneous DB types to a common comparison type."""
        type_map = {
            "varchar": "string", "varchar2": "string", "nvarchar": "string",
            "char": "string", "nchar": "string", "text": "string", "clob": "string",
            "int": "integer", "integer": "integer", "bigint": "integer",
            "smallint": "integer", "tinyint": "integer", "number": "decimal",
            "numeric": "decimal", "decimal": "decimal", "float": "decimal",
            "double": "decimal", "real": "decimal", "date": "date",
            "timestamp": "timestamp", "datetime": "timestamp",
            "datetime2": "timestamp", "timestamptz": "timestamp",
            "bool": "boolean", "boolean": "boolean", "bit": "boolean",
        }
        s = type_map.get(source_type.lower().split("(")[0].strip(), source_type.lower())
        t = type_map.get(target_type.lower().split("(")[0].strip(), target_type.lower())
        return s, t
