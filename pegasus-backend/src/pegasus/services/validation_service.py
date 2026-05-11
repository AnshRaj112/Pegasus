"""Orchestrates CSV load and UID-based comparison (blocking Polars in a thread pool)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl

from pegasus.core.config import Settings
from pegasus.services.exceptions import (
    ValidationBadRequestError,
    ValidationUnprocessableError,
)
from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport
from pegasus.validation.comparators.uid_based import UIDBasedComparator
from pegasus.validation.readers.exceptions import (
    CSVFileNotFoundError,
    CSVParseError,
    CSVValidationError,
)
from pegasus.validation.readers.delimiter_detection import detect_delimiter
from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationRunResult:
    """Outcome of a single validation run (in-memory Polars state)."""

    report: MismatchReport
    source_row_count: int
    target_row_count: int
    compared_column_count: int
    compared_columns: list[str]


class ValidationService:
    """Load two CSV files and compare rows on a shared UID column."""

    __slots__ = ("_settings",)

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def validate_csv_pair(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
    ) -> ValidationRunResult:
        """Run validation off the event loop so Polars work does not block asyncio."""
        return await asyncio.to_thread(
            self._validate_csv_pair_sync,
            source_path,
            target_path,
            uid_column,
            delimiter,
        )

    def _validate_csv_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
    ) -> ValidationRunResult:
        uid = uid_column.strip()
        if not uid:
            raise ValidationBadRequestError("uid_column must be a non-empty string")

        reader = PolarsCSVReader()
        try:
            reader.validate_file(source_path)
            reader.validate_file(target_path)
        except CSVFileNotFoundError as exc:
            raise ValidationBadRequestError(str(exc)) from exc
        except CSVValidationError as exc:
            raise ValidationBadRequestError(str(exc)) from exc

        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )

        logger.info(
            "Loading CSV pair for validation source=%s target=%s uid_column=%r delimiter=%r",
            source_path.name,
            target_path.name,
            uid,
            delim,
        )
        try:
            source_df = self._read_dataframe(reader, source_path, delim)
            target_df = self._read_dataframe(reader, target_path, delim)
        except CSVParseError as exc:
            logger.warning("CSV parse failed during validation: %s", exc)
            raise ValidationBadRequestError(f"Could not parse CSV: {exc}") from exc

        if uid not in source_df.columns:
            raise ValidationBadRequestError(
                f"uid_column {uid!r} not found in source file columns: {list(source_df.columns)}"
            )
        if uid not in target_df.columns:
            raise ValidationBadRequestError(
                f"uid_column {uid!r} not found in target file columns: {list(target_df.columns)}"
            )

        src_cols = set(source_df.columns)
        tgt_cols = set(target_df.columns)
        shared = src_cols & tgt_cols
        compared_columns = sorted(shared - {uid})
        compared = len(compared_columns)

        comparator = UIDBasedComparator(stringify_null_in_report=True)
        try:
            report = comparator.compare_dataframes(
                source_df,
                target_df,
                uid_column=uid,
                compare_columns=None,
            )
        except UIDComparisonError as exc:
            logger.warning("UID comparison rejected input: %s", exc)
            raise ValidationUnprocessableError(str(exc)) from exc

        logger.info(
            "Validation finished source_rows=%d target_rows=%d mismatch_report_rows=%d",
            source_df.height,
            target_df.height,
            report.mismatches.height,
        )
        return ValidationRunResult(
            report=report,
            source_row_count=source_df.height,
            target_row_count=target_df.height,
            compared_column_count=compared,
            compared_columns=compared_columns,
        )

    def _resolve_delimiter(
        self,
        *,
        source_path: Path,
        target_path: Path,
        delimiter: str | None,
    ) -> str:
        token = (delimiter or "").strip()
        lowered = token.lower()
        if lowered in {"", "auto", "infer", "detect"}:
            src = detect_delimiter(source_path).delimiter
            tgt = detect_delimiter(target_path).delimiter
            if src != tgt:
                raise ValidationBadRequestError(
                    f"Could not infer a shared delimiter automatically (source={src!r}, target={tgt!r}). "
                    "Please provide delimiter explicitly."
                )
            return src

        if token in {"\\t", "\\\\t"} or lowered == "tab":
            return "\t"

        if len(token) != 1:
            # explicit multi-char delimiter: supported through pandas fallback
            return token
        return token

    def _read_dataframe(self, reader: PolarsCSVReader, path: Path, delimiter: str) -> pl.DataFrame:
        if len(delimiter) == 1:
            return reader.read_file(
                path,
                delimiter=delimiter,
                encoding="utf-8",
                use_streaming_engine=True,
            )

        # Multi-character delimiters are not supported by Polars CSV parser.
        # Use pandas python engine, then convert to Polars for downstream pipeline.
        logger.info("Using pandas fallback for multi-character delimiter %r on %s", delimiter, path.name)
        try:
            pdf = pd.read_csv(
                path,
                sep=re.escape(delimiter),
                engine="python",
                encoding="utf-8",
            )
        except Exception as exc:
            raise CSVParseError(f"Failed pandas fallback parse for {path.name}: {exc}") from exc

        return pl.from_pandas(pdf, include_index=False)
