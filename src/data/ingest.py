"""Load raw Inside Airbnb csv.gz files into DuckDB raw tables (verbatim, text-typed)."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_csv_to_duckdb(con: duckdb.DuckDBPyConnection, csv_gz_path: Path, table: str) -> int:
    """Create/replace `table` from the csv.gz, all columns as VARCHAR. Returns row count."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        "SELECT * FROM read_csv_auto(?, header=true, all_varchar=true)",
        [str(csv_gz_path)],
    )
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
