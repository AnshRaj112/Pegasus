"""PyArrow I/O tests."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.readers.pyarrow_io import (
    iter_csv_batches,
    pyarrow_supports_delimiter,
    read_csv_table,
    table_to_polars,
)


def test_pyarrow_reads_comma_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")
    assert pyarrow_supports_delimiter(",")
    table = read_csv_table(path, delimiter=",")
    frame = table_to_polars(table)
    assert frame.height == 2
    assert frame.columns == ["id", "name"]


def test_pyarrow_stream_batches(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,value\n" + "\n".join(f"{i},{i}" for i in range(100)) + "\n", encoding="utf-8")
    total = sum(batch.num_rows for batch in iter_csv_batches(path, delimiter=",", chunk_rows=25))
    assert total == 100


def test_delimited_adapter_uses_pyarrow_for_comma(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("uid,amount\n10,5\n20,6\n", encoding="utf-8")
    adapter = FileDelimitedAdapter(path, delimiter=",")
    rows = [row for chunk in adapter.stream_records(10) for row in chunk]
    assert len(rows) == 2
    assert rows[0]["uid"] == "10"
