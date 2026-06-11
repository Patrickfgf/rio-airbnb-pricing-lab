"""Aggregate the large calendar file in DuckDB (never load 13M rows into pandas).

Grain of the output: listing_id x month x day-of-week, with median calendar
price and a naive booked_rate (= share of days marked unavailable).
The booked_rate is a NAIVE signal; occupancy.py refines it (see spec section 6).

Schema-flexible: the current Inside Airbnb Rio calendar dump has NO `price`
column (only listing_id/date/available/minimum_nights/maximum_nights), so
median_cal_price is emitted as NULL when price is absent. booked_rate (the
core seasonality signal) is computed over ALL days regardless of price.
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _agg_sql(src: str, *, has_price: bool) -> str:
    """Build the aggregation SQL over relation `src` (an internal, allow-listed name).

    When the source has no `price` column, median_cal_price is NULL. We do NOT
    filter on price: blocked days often carry no price, so filtering would bias
    booked_rate downward; MEDIAN ignores NULLs anyway.
    """
    if not _VALID_IDENT.match(src):  # defence-in-depth: never interpolate an unchecked name
        raise ValueError(f"Invalid relation name: {src!r}")
    cal_price_expr = (
        "CAST(REPLACE(REPLACE(price, '$', ''), ',', '') AS DOUBLE)"
        if has_price
        else "CAST(NULL AS DOUBLE)"
    )
    return f"""
    WITH parsed AS (
        SELECT
            CAST(listing_id AS BIGINT)   AS listing_id,
            CAST(date AS DATE)           AS d,
            (available = 'f')            AS is_unavailable,
            {cal_price_expr}             AS cal_price
        FROM {src}
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
    has_price = "price" in calendar.columns
    con.register("cal", calendar)
    try:
        return con.execute(_agg_sql("cal", has_price=has_price)).df()
    finally:
        con.unregister("cal")


def aggregate_calendar_table(
    con: duckdb.DuckDBPyConnection, table: str = "raw_calendar"
) -> pd.DataFrame:
    """Aggregate an already-loaded raw calendar table (used by the pipeline)."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    cols = {r[0].lower() for r in con.execute(f"DESCRIBE {table}").fetchall()}
    return con.execute(_agg_sql(table, has_price="price" in cols)).df()
