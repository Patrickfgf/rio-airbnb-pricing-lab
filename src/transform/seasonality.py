"""Horizon-detrended, market-level seasonality from the raw calendar.

A single Inside Airbnb snapshot cannot separate broad season (summer-high /
winter-low) from calendar *horizon*: far-future dates read as increasingly
"unavailable" largely because hosts have not opened those calendars yet, not
because demand is higher. What IS recoverable is *local* structure — short
events (Reveillon, national holidays) that spike above their neighbouring
baseline, plus the day-of-week effect (roughly orthogonal to horizon).

This module builds a market-level availability series (grain: 1 row per
calendar date) and detrends it with a centered rolling baseline. `event_uplift`
(= unavail_rate - baseline) isolates local spikes; broad season is absorbed
into `baseline` ON PURPOSE and must NOT be read as demand (it is confounded
with horizon). `is_edge` flags the leading/trailing dates whose baseline window
is truncated, so callers can drop them.
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VALID_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_WINDOW = 29  # centered: +/- 14 days around each date


def _detrend_sql(src: str, *, snapshot_date: str, window: int) -> str:
    """Build the detrend SQL over relation `src` (an internal, allow-listed name).

    Both `src` and `snapshot_date` are interpolated into the query, so they are
    validated against strict patterns first (DuckDB window-frame bounds cannot
    be passed as bind parameters, hence the literal `half`).
    """
    if not _VALID_IDENT.match(src):  # defence-in-depth: never interpolate an unchecked name
        raise ValueError(f"Invalid relation name: {src!r}")
    if not _VALID_DATE.match(snapshot_date):
        raise ValueError(f"Invalid snapshot_date: {snapshot_date!r}")
    half = int(window) // 2
    return f"""
    WITH daily AS (
        SELECT
            CAST(date AS DATE)                               AS d,
            (CAST(date AS DATE) - DATE '{snapshot_date}')    AS horizon_days,
            AVG(CASE WHEN available = 'f' THEN 1.0 ELSE 0.0 END) AS unavail_rate
        FROM {src}
        GROUP BY 1, 2
    ),
    windowed AS (
        SELECT
            d, horizon_days, unavail_rate,
            AVG(unavail_rate) OVER w AS baseline,
            ROW_NUMBER() OVER (ORDER BY d) AS rn,
            COUNT(*) OVER ()               AS n
        FROM daily
        WINDOW w AS (ORDER BY d ROWS BETWEEN {half} PRECEDING AND {half} FOLLOWING)
    )
    SELECT
        d                          AS date,
        DAYOFWEEK(d)               AS dow,            -- 0=Sunday .. 6=Saturday
        horizon_days,
        unavail_rate,
        baseline,
        unavail_rate - baseline    AS event_uplift,
        (rn <= {half} OR rn > n - {half}) AS is_edge
    FROM windowed
    ORDER BY d
    """


def seasonality_from_calendar(
    con: duckdb.DuckDBPyConnection,
    calendar: pd.DataFrame,
    *,
    snapshot_date: str,
    window: int = DEFAULT_WINDOW,
) -> pd.DataFrame:
    """Detrend an in-memory calendar frame (used in tests)."""
    con.register("cal", calendar)
    try:
        return con.execute(_detrend_sql("cal", snapshot_date=snapshot_date, window=window)).df()
    finally:
        con.unregister("cal")


def seasonality_from_table(
    con: duckdb.DuckDBPyConnection,
    table: str = "raw_calendar",
    *,
    snapshot_date: str,
    window: int = DEFAULT_WINDOW,
) -> pd.DataFrame:
    """Detrend an already-loaded raw calendar table (used by the pipeline)."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return con.execute(_detrend_sql(table, snapshot_date=snapshot_date, window=window)).df()
