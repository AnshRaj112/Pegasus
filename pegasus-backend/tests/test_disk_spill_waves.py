from pathlib import Path

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader
from pegasus.validation.reconciliation.merkle import compute_csv_merkle_root


def test_streaming_merkle_root_matches_for_identical_files(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    content = "uid,a,b\n1,x,y\n2,m,n\n"
    src.write_text(content, encoding="utf-8")
    tgt.write_text(content, encoding="utf-8")

    reader = PolarsCSVReader(default_batch_size=2)
    src_root, src_rows = compute_csv_merkle_root(
        path=src,
        reader=reader,
        delimiter=",",
        has_header=True,
        batch_rows=2,
        columns=["uid", "a", "b"],
    )
    tgt_root, tgt_rows = compute_csv_merkle_root(
        path=tgt,
        reader=reader,
        delimiter=",",
        has_header=True,
        batch_rows=2,
        columns=["uid", "a", "b"],
    )
    assert src_rows == 2
    assert tgt_rows == 2
    assert src_root == tgt_root

