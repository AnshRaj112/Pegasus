"""CSV reader specific errors (distinct from generic Polars errors)."""


class CSVReaderError(RuntimeError):
    """Base class for Pegasus CSV ingestion failures."""


class CSVFileNotFoundError(CSVReaderError, FileNotFoundError):
    """Raised when the configured path does not exist."""


class CSVValidationError(CSVReaderError, ValueError):
    """Raised when a path exists but is not a valid ingestible CSV file."""


class CSVParseError(CSVReaderError):
    """Raised when Polars fails to parse CSV bytes according to the given options."""
