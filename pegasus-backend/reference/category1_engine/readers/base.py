# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:11:28Z
# --- END GENERATED FILE METADATA ---

"""Base streaming reader interface."""

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema, FileFormat


class StreamingReader(ABC):
    """Iterator-based reader that never loads full datasets."""

    def __init__(self, config: ConnectionConfig):
        self._config = config

    @abstractmethod
    def get_schema(self) -> DatasetSchema:
        ...

    @abstractmethod
    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        ...

    def get_row_count(self) -> Optional[int]:
        """Cheap row count if available from metadata; None otherwise."""
        return None

    @staticmethod
    def create(config: ConnectionConfig) -> "StreamingReader":
        if config.source_type.value == "file":
            return FileReaderFactory.create(config)
        from category1.adapters.database import DatabaseReaderFactory
        return DatabaseReaderFactory.create(config)


class FileReaderFactory:
    @staticmethod
    def create(config: ConnectionConfig) -> StreamingReader:
        fmt = config.file_format or FileFormat.CSV
        readers = {
            FileFormat.CSV: "category1.readers.delimited.CSVReader",
            FileFormat.TSV: "category1.readers.delimited.TSVReader",
            FileFormat.PSV: "category1.readers.delimited.PSVReader",
            FileFormat.FIXED_WIDTH: "category1.readers.fixed_width.FixedWidthReader",
            FileFormat.PARQUET: "category1.readers.parquet_reader.ParquetReader",
            FileFormat.ORC: "category1.readers.orc_reader.ORCReader",
            FileFormat.AVRO: "category1.readers.avro_reader.AvroReader",
            FileFormat.EXCEL: "category1.readers.excel_reader.ExcelReader",
        }
        import importlib
        module_path, cls_name = readers[fmt].rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, cls_name)
        return cls(config)
