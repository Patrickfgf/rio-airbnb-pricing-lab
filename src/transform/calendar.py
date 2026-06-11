"""Aggregate the large calendar file in DuckDB (never load 13M rows into pandas).

Grain of the output: listing_id x month x day-of-week, with median calendar
price and a naive booked_rate (= share of days marked unavailable).
The booked_rate is a NAIVE signal; occupancy.py refines it (see spec section 6).
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _agg_sql(src: str) -> str:
    """Build the aggregation SQL over relation `src` (an internal, allow-listed name)."""
    return f"""
    WITH parsed AS (
        SELECT
            CAST(listing_id AS BIGINT)                                   AS listing_id,
            CAST(date AS DATE)                                           AS d,
            (available = 'f')                                            AS is_unavailable,
            CAST(REPLACE(REPLACE(price, '$', ''), ',', '') AS DOUBLE)   AS cal_price
        FROM {src}
        WHERE price IS NOT NULL
    )
    SELECT
        listing_id,
        MONTH(d)                                            AS month,
        DAYOFWEEK(d)                                        AS dow,  -- 0=Sunday .. 6=Saturday
        MEDIAN(cal_price)                                   AS median_cal_price,
        AVG(CASE WHEN is_unavailable THEN 1.0 ELSE 0.0 END) AS booked_rate
    FROM parsed
    GROUP BY listing_id, MONTH(d), DAYOFWEEK(d)
    ORDER BY listing_id, month, dow
    """


def aggregate_calendar(con: duckdb.DuckDBPyConnection, calendar: pd.DataFrame) -> pd.DataFrame:
    """Aggregate an in-memory calendar frame (used in tests)."""
    con.register("cal", calendar)
    try:
        return con.execute(_agg_sql("cal")).df()
    finally:
        con.unregister("cal")


def aggregate_calendar_table(
    con: duckdb.DuckDBPyConnection, table: str = "raw_calendar"
) -> pd.DataFrame:
    """Aggregate an already-loaded raw calendar table (used by the pipeline)."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return con.execute(_agg_sql(table)).df()
