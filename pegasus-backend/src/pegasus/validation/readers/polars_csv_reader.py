"""Polars-backed streaming CSV reader for large files."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Literal

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.readers.base import CSVReader
from pegasus.validation.readers.encoding import normalize_lazy_csv_encoding, try_lazy_csv_encoding
from pegasus.validation.readers.exceptions import (
    CSVFileNotFoundError,
    CSVParseError,
    CSVValidationError,
)

logger = logging.getLogger(__name__)


class PolarsCSVReader(CSVReader):
    """Memory-conscious CSV ingestion using Polars lazy scans and chunked collection.

    * :meth:`scan` / :meth:`scan_with_options` return a :class:`polars.LazyFrame` for
      pipeline-friendly I/O. Lazy scans require UTF-8 (or ``utf8-lossy``) encodings
      as enforced by Polars.
    * :meth:`iter_batches` uses :meth:`polars.LazyFrame.collect_batches` with the
      streaming engine so large UTF-8 files are processed in bounded chunks.
    * :meth:`read_file` prefers ``scan_csv`` + ``collect(engine=\"streaming\")`` for
      UTF-8 inputs; other encodings use :func:`polars.read_csv` with ``low_memory``
      (full-file materialization).

    Parameters
    ----------
    default_batch_size
        Rows per chunk for :meth:`iter_batches` when ``batch_size`` is omitted.
    default_infer_schema_length
        Rows Polars inspects for dtype inference in lazy mode unless overridden.
    """

    __slots__ = ("_default_batch_size", "_default_infer_schema_length")

    def __init__(
        self,
        *,
        default_batch_size: int = 500_000,
        default_infer_schema_length: int | None = 10_000,
    ) -> None:
        if default_batch_size < 1:
            raise ValueError("default_batch_size must be >= 1")
        self._default_batch_size = default_batch_size
        self._default_infer_schema_length = default_infer_schema_length

    def validate_file(
        self,
        path: str | Path,
        *,
        reject_empty: bool = True,
    ) -> Path:
        """Check that *path* exists, is a regular file, and optionally is non-empty.

        Parameters
        ----------
        path
            Filesystem path to a CSV file.
        reject_empty
            If ``True``, reject zero-byte files as invalid for ingestion.

        Returns
        -------
        pathlib.Path
            Resolved, absolute path.

        Raises
        ------
        CSVFileNotFoundError
            If the path does not exist.
        CSVValidationError
            If the path is not a file, or is empty when ``reject_empty`` is set.
        """
        resolved = Path(path).expanduser()
        try:
            resolved = resolved.resolve(strict=True)
        except FileNotFoundError as exc:
            logger.warning("CSV path not found: %s", path)
            raise CSVFileNotFoundError(f"CSV file not found: {path}") from exc
        except OSError as exc:
            logger.error("Failed to resolve CSV path %s: %s", path, exc)
            raise CSVValidationError(f"Cannot resolve CSV path: {path}") from exc

        if not resolved.is_file():
            logger.warning("CSV path is not a regular file: %s", resolved)
            raise CSVValidationError(f"Not a regular file: {resolved}")

        if reject_empty and resolved.stat().st_size == 0:
            logger.warning("CSV file is empty: %s", resolved)
            raise CSVValidationError(f"Empty CSV file: {resolved}")

        return resolved

    def detect_schema(
        self,
        path: str | Path,
        *,
        delimiter: str = ",",
        encoding: str = "utf-8",
        has_header: bool = True,
        infer_schema_length: int | None = None,
        try_parse_dates: bool = False,
        read_options: Mapping[str, Any] | None = None,
    ) -> pl.Schema:
        """Infer column names and dtypes from *path*.

        UTF-8-compatible encodings use :func:`polars.scan_csv` plus
        :meth:`polars.LazyFrame.collect_schema`. Other encodings use a bounded
        :func:`polars.read_csv` sample (``n_rows``) so the whole file is not loaded.

        Parameters
        ----------
        path
            CSV location on the local filesystem.
        delimiter
            Field separator passed to Polars as ``separator``.
        encoding
            Character encoding (for example ``\"utf-8\"`` or ``\"latin-1\"``).
        has_header
            Whether the first row contains column names.
        infer_schema_length
            Rows scanned for dtype inference; defaults to ``default_infer_schema_length``.
        try_parse_dates
            Whether Polars should attempt automatic date parsing.
        read_options
            Extra keyword arguments forwarded to ``scan_csv`` or ``read_csv`` (filtered
            to supported parameters).

        Returns
        -------
        polars.Schema
            Inferred schema for the file.

        Raises
        ------
        CSVFileNotFoundError, CSVValidationError
            From :meth:`validate_file` if the file is unusable.
        CSVParseError
            If Polars cannot parse the file with the supplied options.
        """
        resolved = self.validate_file(path)
        infer_len = infer_schema_length if infer_schema_length is not None else self._default_infer_schema_length

        if try_lazy_csv_encoding(encoding) is None:
            sample_rows = max(infer_len or 10_000, 1)
            logger.info(
                "Probing schema via eager read_csv sample (encoding=%s n_rows=%s)",
                encoding,
                sample_rows,
            )
            return self._schema_from_eager_sample(
                resolved,
                delimiter=delimiter,
                encoding=encoding,
                has_header=has_header,
                infer_schema_length=infer_len,
                try_parse_dates=try_parse_dates,
                read_options=read_options,
                sample_rows=sample_rows,
            )

        scan_kw = self._scan_csv_kwargs(
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            infer_schema_length=infer_len,
            schema_overrides=None,
            try_parse_dates=try_parse_dates,
            read_options=read_options,
        )
        logger.debug("Detecting schema (lazy) for %s infer_schema_length=%s", resolved, infer_len)
        try:
            schema = pl.scan_csv(str(resolved), **scan_kw).collect_schema()
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed inferring schema for %s", resolved)
            raise CSVParseError(f"Failed to infer CSV schema: {resolved}") from exc
        logger.info("Inferred schema for %s with %d columns", resolved.name, len(schema))
        return schema

    def read_file(
        self,
        path: str | Path,
        *,
        delimiter: str = ",",
        encoding: str = "utf-8",
        has_header: bool = True,
        infer_schema_length: int | None = None,
        schema_overrides: Mapping[str, Any] | None = None,
        try_parse_dates: bool = False,
        use_streaming_engine: bool = True,
        n_rows: int | None = None,
        read_options: Mapping[str, Any] | None = None,
    ) -> pl.DataFrame:
        """Load the CSV as a :class:`polars.DataFrame`.

        UTF-8-compatible encodings use ``scan_csv`` + :meth:`~polars.LazyFrame.collect`.
        Set ``use_streaming_engine=True`` to prefer ``engine=\"streaming\"``. Other
        encodings always use :func:`polars.read_csv` (eager, ``low_memory=True``).

        For very large UTF-8 files, prefer :meth:`iter_batches` or :meth:`scan` so peak
        memory stays closer to chunk size than to output size.

        Parameters
        ----------
        path
            CSV path.
        delimiter, encoding, has_header, infer_schema_length, schema_overrides, try_parse_dates
            Same semantics as :meth:`detect_schema`.
        use_streaming_engine
            When the lazy path is used, pass ``engine=\"streaming\"`` if ``True``.
        n_rows
            Optional cap on rows to read.
        read_options
            Extra Polars keyword arguments (filtered per API).

        Returns
        -------
        polars.DataFrame
            Materialized frame.

        Raises
        ------
        CSVFileNotFoundError, CSVValidationError, CSVParseError
            Same as :meth:`detect_schema`.
        """
        resolved = self.validate_file(path)
        infer_len = infer_schema_length if infer_schema_length is not None else self._default_infer_schema_length

        if try_lazy_csv_encoding(encoding) is None:
            logger.warning(
                "Using eager read_csv for encoding=%s (lazy streaming not supported by Polars for this encoding)",
                encoding,
            )
            kw = self._read_csv_kwargs(
                delimiter=delimiter,
                encoding=encoding,
                has_header=has_header,
                infer_schema_length=infer_len,
                schema_overrides=schema_overrides,
                try_parse_dates=try_parse_dates,
                read_options=read_options,
                n_rows=n_rows,
            )
            try:
                df = pl.read_csv(str(resolved), **kw)
            except pl_exc.PolarsError as exc:
                logger.exception("Polars read_csv failed for %s", resolved)
                raise CSVParseError(f"Failed to read CSV: {resolved}") from exc
            logger.debug("Loaded DataFrame (eager) shape=%s", df.shape)
            return df

        scan_kw = self._scan_csv_kwargs(
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            infer_schema_length=infer_len,
            schema_overrides=schema_overrides,
            try_parse_dates=try_parse_dates,
            read_options=read_options,
        )
        if n_rows is not None:
            scan_kw["n_rows"] = n_rows

        lf = pl.scan_csv(str(resolved), **scan_kw)
        engine: Literal["streaming", "auto"] = "streaming" if use_streaming_engine else "auto"
        logger.info(
            "Collecting CSV path=%s engine=%s",
            resolved.name,
            engine,
        )
        try:
            if use_streaming_engine:
                df = lf.collect(engine="streaming")
            else:
                df = lf.collect()
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed collecting CSV %s", resolved)
            raise CSVParseError(f"Failed to read CSV: {resolved}") from exc

        logger.debug("Loaded DataFrame shape=%s", df.shape)
        return df

    def scan(
        self,
        path: str | Path,
        *,
        read_options: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Build a lazy scan from ``read_options`` (see :meth:`scan_with_options`)."""
        ro = dict(read_options or {})
        return self.scan_with_options(
            path,
            delimiter=str(ro.pop("separator", ",")),
            encoding=str(ro.pop("encoding", "utf-8")),
            has_header=bool(ro.pop("has_header", True)),
            infer_schema_length=ro.pop("infer_schema_length", self._default_infer_schema_length),
            schema_overrides=ro.pop("schema_overrides", None),
            try_parse_dates=bool(ro.pop("try_parse_dates", False)),
            read_options=ro,
        )

    def scan_with_options(
        self,
        path: str | Path,
        *,
        delimiter: str = ",",
        encoding: str = "utf-8",
        has_header: bool = True,
        infer_schema_length: int | None = None,
        schema_overrides: Mapping[str, Any] | None = None,
        try_parse_dates: bool = False,
        read_options: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Return :func:`polars.scan_csv` with explicit delimiter, encoding, and schema hints.

        Raises
        ------
        CSVValidationError
            If *encoding* is not compatible with Polars lazy CSV (non UTF-8 / utf8-lossy).
        """
        resolved = self.validate_file(path)
        infer_len = infer_schema_length if infer_schema_length is not None else self._default_infer_schema_length
        scan_kw = self._scan_csv_kwargs(
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            infer_schema_length=infer_len,
            schema_overrides=schema_overrides,
            try_parse_dates=try_parse_dates,
            read_options=read_options,
        )
        try:
            return pl.scan_csv(str(resolved), **scan_kw)
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed to open scan for %s", resolved)
            raise CSVParseError(f"Failed to scan CSV: {resolved}") from exc

    def iter_batches(
        self,
        path: str | Path,
        *,
        batch_size: int | None = None,
        schema_overrides: Mapping[str, Any] | None = None,
        read_options: Mapping[str, Any] | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Yield ``DataFrame`` chunks via lazy scan + streaming batch collection.

        ``read_options`` may include ``separator``, ``encoding``, ``has_header``,
        ``infer_schema_length``, ``try_parse_dates``, and other ``scan_csv`` keys.

        Raises
        ------
        CSVValidationError
            If *encoding* is not UTF-8 compatible for lazy I/O (use UTF-8 sources or
            transcode); :func:`polars.read_csv` streaming for arbitrary encodings is not
            wired here to keep memory behaviour predictable.
        """
        resolved = self.validate_file(path)
        chunk = batch_size if batch_size is not None else self._default_batch_size
        ro = dict(read_options or {})
        delimiter = str(ro.pop("separator", ","))
        encoding = str(ro.pop("encoding", "utf-8"))
        has_header = bool(ro.pop("has_header", True))
        infer_schema_length = ro.pop("infer_schema_length", self._default_infer_schema_length)
        try_parse_dates = bool(ro.pop("try_parse_dates", False))
        sov = schema_overrides if schema_overrides is not None else ro.pop("schema_overrides", None)

        if try_lazy_csv_encoding(encoding) is None:
            raise CSVValidationError(
                "iter_batches only supports UTF-8 / utf8-lossy encodings for lazy CSV I/O "
                f"(got {encoding!r}). Transcode to UTF-8 or use read_file / detect_schema with "
                "eager Polars paths."
            )

        scan_kw = self._scan_csv_kwargs(
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            infer_schema_length=infer_schema_length,
            schema_overrides=sov,
            try_parse_dates=try_parse_dates,
            read_options=ro,
        )
        logger.info(
            "Starting chunked CSV collect_batches path=%s chunk_size=%s",
            resolved.name,
            chunk,
        )
        try:
            lazy = pl.scan_csv(str(resolved), **scan_kw)
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed to open scan for batched read %s", resolved)
            raise CSVParseError(f"Failed to open CSV scan: {resolved}") from exc

        total_rows = 0
        try:
            for batch in lazy.collect_batches(chunk_size=chunk, engine="streaming"):
                rows = batch.height
                total_rows += rows
                logger.debug("Yielding CSV batch rows=%s cumulative=%s", rows, total_rows)
                yield batch
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed during collect_batches for %s", resolved)
            raise CSVParseError(f"Failed while reading CSV batches: {resolved}") from exc

        logger.info("Finished batched CSV read path=%s total_rows=%s", resolved.name, total_rows)

    def _schema_from_eager_sample(
        self,
        resolved: Path,
        *,
        delimiter: str,
        encoding: str,
        has_header: bool,
        infer_schema_length: int | None,
        try_parse_dates: bool,
        read_options: Mapping[str, Any] | None,
        sample_rows: int,
    ) -> pl.Schema:
        kw = self._read_csv_kwargs(
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            infer_schema_length=infer_schema_length,
            schema_overrides=None,
            try_parse_dates=try_parse_dates,
            read_options=read_options,
            n_rows=sample_rows,
        )
        try:
            schema = pl.read_csv(str(resolved), **kw).schema
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed schema probe (eager) for %s", resolved)
            raise CSVParseError(f"Failed to infer CSV schema: {resolved}") from exc
        logger.info("Inferred schema (eager sample) for %s with %d columns", resolved.name, len(schema))
        return schema

    @staticmethod
    def _scan_csv_kwargs(
        *,
        delimiter: str,
        encoding: str,
        has_header: bool,
        infer_schema_length: int | None,
        schema_overrides: Mapping[str, Any] | None,
        try_parse_dates: bool,
        read_options: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        scan_params = set(inspect.signature(pl.scan_csv).parameters)
        extra_raw = dict(read_options or {})
        extra: dict[str, Any] = {}
        for key, val in extra_raw.items():
            if key not in scan_params:
                logger.debug("Ignoring unsupported scan_csv option %r", key)
                continue
            if key in {"separator", "encoding", "has_header", "infer_schema_length", "try_parse_dates"}:
                continue
            extra[key] = val

        polars_encoding = normalize_lazy_csv_encoding(encoding)
        out: dict[str, Any] = {
            "separator": delimiter,
            "encoding": polars_encoding,
            "has_header": has_header,
            "infer_schema_length": infer_schema_length,
            "low_memory": True,
            "try_parse_dates": try_parse_dates,
        }
        out.update(extra)
        out["separator"] = delimiter
        out["encoding"] = polars_encoding
        out["has_header"] = has_header
        out["infer_schema_length"] = infer_schema_length
        out["low_memory"] = True
        out["try_parse_dates"] = try_parse_dates
        if schema_overrides is not None:
            out["schema_overrides"] = dict(schema_overrides)
        return out

    @staticmethod
    def _read_csv_kwargs(
        *,
        delimiter: str,
        encoding: str,
        has_header: bool,
        infer_schema_length: int | None,
        schema_overrides: Mapping[str, Any] | None,
        try_parse_dates: bool,
        read_options: Mapping[str, Any] | None,
        n_rows: int | None,
    ) -> dict[str, Any]:
        read_params = set(inspect.signature(pl.read_csv).parameters)
        extra_raw = dict(read_options or {})
        extra: dict[str, Any] = {}
        for key, val in extra_raw.items():
            if key not in read_params:
                logger.debug("Ignoring unsupported read_csv option %r", key)
                continue
            if key in {
                "separator",
                "encoding",
                "has_header",
                "infer_schema_length",
                "try_parse_dates",
                "schema_overrides",
                "n_rows",
                "low_memory",
            }:
                continue
            extra[key] = val

        out: dict[str, Any] = {
            "has_header": has_header,
            "separator": delimiter,
            "encoding": encoding,
            "infer_schema_length": infer_schema_length,
            "try_parse_dates": try_parse_dates,
            "low_memory": True,
        }
        out.update(extra)
        out["has_header"] = has_header
        out["separator"] = delimiter
        out["encoding"] = encoding
        out["infer_schema_length"] = infer_schema_length
        out["try_parse_dates"] = try_parse_dates
        out["low_memory"] = True
        if schema_overrides is not None:
            out["schema_overrides"] = dict(schema_overrides)
        if n_rows is not None:
            out["n_rows"] = n_rows
        return {k: v for k, v in out.items() if k in read_params}
