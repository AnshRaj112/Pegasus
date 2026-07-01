# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T07:31:54Z
# --- END GENERATED FILE METADATA ---

"""Integration tests for Category-1 reconciliation platform."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from category1.config import ReconciliationConfig
from category1.core.canonicalization import CanonicalizationEngine
from category1.core.fingerprint import FingerprintEngine
from category1.core.partitioner import PartitionWriter, StreamingPartitioner
from category1.core.schema_validator import SchemaValidator
from category1.core.reconciliation_engine import ReconciliationEngine
from category1.models.schemas import (
    ColumnSchema,
    ConnectionConfig,
    DataSourceType,
    DatasetSchema,
    FileFormat,
    KeyStrategy,
    ReconciliationJobConfig,
)
from category1.readers.base import StreamingReader


TEST_DATA = Path(__file__).parent.parent.parent / "test-data"


class TestCanonicalization:
    def test_null_handling(self):
        engine = CanonicalizationEngine()
        assert engine.canonicalize_value(None) == "__NULL__"
        assert engine.canonicalize_value("") == "__NULL__"
        assert engine.canonicalize_value("NULL") == "__NULL__"

    def test_whitespace_trim(self):
        engine = CanonicalizationEngine()
        assert engine.canonicalize_value("  hello  ") == "hello"

    def test_decimal_normalization(self):
        engine = CanonicalizationEngine()
        assert engine.canonicalize_value("100.00", "decimal") == "100"
        assert engine.canonicalize_value("1,234.50", "decimal") == "1234.5"

    def test_date_normalization(self):
        engine = CanonicalizationEngine()
        assert engine.canonicalize_value("2020-03-15", "date") == "2020-03-15"


class TestFingerprint:
    def test_deterministic_partition(self):
        fp = FingerprintEngine()
        key = "1001"
        p1 = fp.compute_partition_id(key, 4096)
        p2 = fp.compute_partition_id(key, 4096)
        assert p1 == p2
        assert 0 <= p1 < 4096

    def test_fingerprint_changes_with_data(self):
        fp = FingerprintEngine()
        r1 = {"name": "Alice", "salary": "95000"}
        r2 = {"name": "Alice", "salary": "96000"}
        fp1 = fp.compute_fingerprint(r1, ["name", "salary"])
        fp2 = fp.compute_fingerprint(r2, ["name", "salary"])
        assert fp1 != fp2


class TestSchemaValidator:
    def test_matching_schemas(self):
        source = DatasetSchema(columns=[
            ColumnSchema(name="id", data_type="integer", position=0),
            ColumnSchema(name="name", data_type="varchar", position=1),
        ])
        target = DatasetSchema(columns=[
            ColumnSchema(name="id", data_type="int", position=0),
            ColumnSchema(name="name", data_type="string", position=1),
        ])
        result = SchemaValidator().validate(source, target)
        assert result.is_valid

    def test_type_mismatch(self):
        source = DatasetSchema(columns=[
            ColumnSchema(name="amount", data_type="decimal", position=0),
        ])
        target = DatasetSchema(columns=[
            ColumnSchema(name="amount", data_type="varchar", position=0),
        ])
        result = SchemaValidator().validate(source, target)
        assert not result.is_valid
        assert any(d.difference_type == "type_mismatch" for d in result.differences)


class TestEndToEndReconciliation:
    def test_csv_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ReconciliationConfig(
                work_dir=Path(tmpdir),
                num_partitions=1024,
                memory_limit_mb=256,
            )
            job_config = ReconciliationJobConfig(
                job_id=uuid4(),
                source=ConnectionConfig(
                    source_type=DataSourceType.FILE,
                    file_path=str(TEST_DATA / "source_employees.csv"),
                    file_format=FileFormat.CSV,
                ),
                target=ConnectionConfig(
                    source_type=DataSourceType.FILE,
                    file_path=str(TEST_DATA / "target_employees.csv"),
                    file_format=FileFormat.CSV,
                ),
                key_columns=["employee_id"],
                key_strategy=KeyStrategy.PRIMARY,
                chunk_size=1000,
                num_partitions=1024,
                memory_limit_mb=256,
            )

            source_reader = StreamingReader.create(job_config.source)
            target_reader = StreamingReader.create(job_config.target)

            engine = ReconciliationEngine(config)
            result = engine.run(job_config, source_reader, target_reader)

            assert result.status.value == "completed"
            assert result.missing_count == 1  # 1005 missing from target
            assert result.extra_count == 1    # 1006 extra in target
            assert result.mismatched_count >= 1  # 1002 name change, 1003 salary change

            report_path = Path(tmpdir) / str(job_config.job_id) / "reports" / "VALIDATION_RESULTS.md"
            assert report_path.exists()

    def test_identical_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ReconciliationConfig(work_dir=Path(tmpdir), num_partitions=1024)
            job_config = ReconciliationJobConfig(
                job_id=uuid4(),
                source=ConnectionConfig(
                    source_type=DataSourceType.FILE,
                    file_path=str(TEST_DATA / "source_employees.csv"),
                    file_format=FileFormat.CSV,
                ),
                target=ConnectionConfig(
                    source_type=DataSourceType.FILE,
                    file_path=str(TEST_DATA / "source_employees.csv"),
                    file_format=FileFormat.CSV,
                ),
                key_columns=["employee_id"],
                num_partitions=1024,
            )

            engine = ReconciliationEngine(config)
            result = engine.run(
                job_config,
                StreamingReader.create(job_config.source),
                StreamingReader.create(job_config.target),
            )

            assert result.status.value == "completed"
            assert result.missing_count == 0
            assert result.extra_count == 0
            assert result.mismatched_count == 0


class TestNativeColumnarReaders:
    def test_native_parquet_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from category1.readers.native.parquet_writer import write_parquet
            path = Path(tmpdir) / "data.parquet"
            write_parquet(str(path), {"id": [10, 20], "label": ["x", "y"]})
            reader = StreamingReader.create(ConnectionConfig(
                source_type=DataSourceType.FILE,
                file_path=str(path),
                file_format=FileFormat.PARQUET,
            ))
            schema = reader.get_schema()
            assert len(schema.columns) == 2
            chunks = list(reader.read_chunks(100))
            assert chunks[0] == [{"id": 10, "label": "x"}, {"id": 20, "label": "y"}]

    def test_native_orc_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from category1.readers.native.orc_writer import write_orc
            path = Path(tmpdir) / "data.orc"
            write_orc(str(path), {"id": [10, 20], "label": ["x", "y"]})
            reader = StreamingReader.create(ConnectionConfig(
                source_type=DataSourceType.FILE,
                file_path=str(path),
                file_format=FileFormat.ORC,
            ))
            schema = reader.get_schema()
            assert len(schema.columns) == 2
            chunks = list(reader.read_chunks(100))
            assert chunks[0] == [{"id": 10, "label": "x"}, {"id": 20, "label": "y"}]

    def test_native_parquet_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from category1.readers.native.parquet_writer import write_parquet
            src = Path(tmpdir) / "source.parquet"
            tgt = Path(tmpdir) / "target.parquet"
            write_parquet(str(src), {"key": [1, 2], "val": ["a", "b"]})
            write_parquet(str(tgt), {"key": [1, 2], "val": ["a", "c"]})
            config = ReconciliationConfig(work_dir=Path(tmpdir), num_partitions=1024)
            job_config = ReconciliationJobConfig(
                job_id=uuid4(),
                source=ConnectionConfig(
                    source_type=DataSourceType.FILE, file_path=str(src), file_format=FileFormat.PARQUET,
                ),
                target=ConnectionConfig(
                    source_type=DataSourceType.FILE, file_path=str(tgt), file_format=FileFormat.PARQUET,
                ),
                key_columns=["key"],
                num_partitions=1024,
            )
            result = ReconciliationEngine(config).run(
                job_config,
                StreamingReader.create(job_config.source),
                StreamingReader.create(job_config.target),
            )
            assert result.status.value == "completed"
            assert result.mismatched_count == 1
