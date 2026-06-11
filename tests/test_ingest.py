import gzip
from pathlib import Path

import duckdb

from src.data.ingest import load_csv_to_duckdb


def _write_csv_gz(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)


def test_loads_csv_gz_as_raw_table(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id,price\n1,$10.00\n2,$20.00\n")
    con = duckdb.connect()
    n = load_csv_to_duckdb(con, csv, "raw_listings")
    assert n == 2
    cols = [r[0] for r in con.execute("DESCRIBE raw_listings").fetchall()]
    assert cols == ["id", "price"]


def test_extra_columns_do_not_break(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id,price,estimated_occupancy_l365d\n1,$10.00,200\n")
    con = duckdb.connect()
    load_csv_to_duckdb(con, csv, "raw_listings")
    cols = [r[0] for r in con.execute("DESCRIBE raw_listings").fetchall()]
    assert "estimated_occupancy_l365d" in cols


def test_rejects_bad_table_name(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id\n1\n")
    con = duckdb.connect()
    import pytest

    with pytest.raises(ValueError):
        load_csv_to_duckdb(con, csv, "raw; DROP TABLE x")
