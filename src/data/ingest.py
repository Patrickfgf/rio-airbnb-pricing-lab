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
    # Specify the dialect explicitly instead of relying on read_csv_auto's
    # sniffer: Inside Airbnb dumps are standard RFC-4180 (comma-delimited,
    # double-quoted, "" escape), and the sniffer fails on small/mixed-quoting
    # samples. all_varchar=true forces every column to VARCHAR (header-flexible).
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        "SELECT * FROM read_csv(?, header=true, all_varchar=true, "
        "delim=',', quote='\"', escape='\"')",
        [str(csv_gz_path)],
    )
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
