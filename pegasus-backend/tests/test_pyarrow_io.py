# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T16:16:26+05:30
# --- END GENERATED FILE METADATA ---

"""PyArrow I/O tests."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from io import BytesIO

from pegasus.validation.readers.pyarrow_io import (
    iter_csv_batches,
    iter_csv_batches_stream,
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


def test_pyarrow_stream_batches_from_binary() -> None:
    payload = b"id,value\n" + "\n".join(f"{i},{i}" for i in range(50)).encode() + b"\n"
    total = sum(
        batch.num_rows
        for batch in iter_csv_batches_stream(
            BytesIO(payload),
            delimiter=",",
            chunk_rows=10,
            column_names=["id", "value"],
        )
    )
    assert total == 50


def test_pyarrow_stream_batches(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,value\n" + "\n".join(f"{i},{i}" for i in range(100)) + "\n", encoding="utf-8")
    total = sum(batch.num_rows for batch in iter_csv_batches(path, delimiter=",", chunk_rows=25))
    assert total == 100


def test_pyarrow_keeps_mixed_numeric_and_alpha_as_strings(tmp_path: Path) -> None:
    path = tmp_path / "mixed.csv"
    lines = ["col_a,col_b,col_c"]
    for i in range(20):
        lines.append(f"{i},{i * 10},100")
    lines.append("21,210,K")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    table = read_csv_table(path, delimiter=",")
    frame = table_to_polars(table)
    assert frame.height == 21
    assert frame["col_c"][-1] == "K"


def test_delimited_adapter_uses_pyarrow_for_comma(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("uid,amount\n10,5\n20,6\n", encoding="utf-8")
    adapter = FileDelimitedAdapter(path, delimiter=",")
    rows = [row for chunk in adapter.stream_records(10) for row in chunk]
    assert len(rows) == 2
    assert rows[0]["uid"] == "10"
