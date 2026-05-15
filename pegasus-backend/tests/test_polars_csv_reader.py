"""Tests for :class:`pegasus.validation.readers.polars_csv_reader.PolarsCSVReader`."""

from __future__ import annotations

import pytest
import polars as pl

from pegasus.validation.readers import (
    CSVFileNotFoundError,
    CSVValidationError,
    PolarsCSVReader,
)


def _write_csv(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_validate_and_detect_schema_prints(tmp_path, capsys):
    """Smoke test with visible schema output (run with ``pytest -s``)."""
    csv_path = tmp_path / "sample.csv"
    _write_csv(csv_path, "id;amount;name\n1;10.5;alpha\n2;20;beta\n")

    reader = PolarsCSVReader(default_batch_size=2)
    resolved = reader.validate_file(csv_path)
    assert resolved.is_file()

    schema = reader.detect_schema(csv_path, delimiter=";", encoding="utf-8")
    print("\n--- detect_schema ---")
    print(schema)

    assert "id" in schema
    assert len(schema) == 3


def test_iter_batches_yields_chunks(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(csv_path, "a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(5)))

    reader = PolarsCSVReader(default_batch_size=2)
    batches = list(
        reader.iter_batches(
            csv_path,
            read_options={"separator": ",", "encoding": "utf-8"},
        )
    )
    total = sum(b.height for b in batches)
    assert total == 5
    assert len(batches) >= 2


def test_read_file_streaming(tmp_path, capsys):
    csv_path = tmp_path / "full.csv"
    _write_csv(csv_path, "x,y\n1,2\n3,4\n")

    reader = PolarsCSVReader()
    df = reader.read_file(csv_path, use_streaming_engine=True)
    print("\n--- read_file (streaming) ---")
    print(df)
    assert df.shape == (2, 2)


def test_missing_file_raises():
    reader = PolarsCSVReader()
    with pytest.raises(CSVFileNotFoundError):
        reader.validate_file("/nonexistent/path/pegasus_missing.csv")


def test_iter_batches_non_utf8_raises(tmp_path):
    csv_path = tmp_path / "latin.csv"
    csv_path.write_bytes(b"a;b\n\xc9;1\n")

    reader = PolarsCSVReader()
    with pytest.raises(CSVValidationError):
        next(
            reader.iter_batches(
                csv_path,
                read_options={"separator": ";", "encoding": "latin-1"},
            )
        )


def test_iter_batches_forces_string_schema_for_stability(tmp_path):
    csv_path = tmp_path / "mixed.csv"
    rows = ["".join(["c1", ",", "c2", ",", "c19"])]
    rows.extend(f"{i},{i * 2},{i * 3}" for i in range(1, 3))
    rows.append("3,6,K")
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    reader = PolarsCSVReader(default_batch_size=2)
    batches = list(
        reader.iter_batches(
            csv_path,
            read_options={"separator": ",", "encoding": "utf-8", "infer_schema_length": 1},
        )
    )

    assert sum(batch.height for batch in batches) == 3
    assert batches[-1].schema["c19"] == pl.String
    assert batches[-1].select("c19").to_series().to_list()[-1] == "K"
