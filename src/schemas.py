"""Pandera contracts for the curated tables.

Grains:
  - curated_listings: 1 row = 1 listing (listing_id unique)
  - curated_occupancy: 1 row = 1 listing (listing_id unique)
  - curated_seasonality: 1 row = (listing_id, month, dow)
  - curated_seasonality_detrended: 1 row = 1 calendar date (date unique)

Note: on pandera >= 0.23 the import is `import pandera.pandas as pa`; the guard
below keeps both new and old installs working. coerce=True normalizes nullable
ExtensionDtypes before checking.
"""

from __future__ import annotations

try:  # pandera >= 0.23 split the pandas API into a submodule
    from pandera.pandas import Check, Column, DataFrameSchema
except ImportError:  # pragma: no cover
    from pandera import Check, Column, DataFrameSchema

import pandas as pd

CURATED_LISTINGS_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", unique=True, nullable=False),
        "neighbourhood": Column("string", nullable=False),
        "room_type": Column("string", nullable=False),
        "price": Column("float64", Check.gt(0), nullable=False),
        "accommodates": Column("Int64", Check.ge(0), nullable=True),
        "min_nights": Column("Int64", Check.ge(0), nullable=True),
        "number_of_reviews_ltm": Column("Int64", Check.ge(0), nullable=True),
        "host_is_superhost": Column("boolean", nullable=True),
        "instant_bookable": Column("boolean", nullable=True),
        "host_response_rate": Column("float64", Check.in_range(0, 1), nullable=True),
        "host_acceptance_rate": Column("float64", Check.in_range(0, 1), nullable=True),
        "review_scores_rating": Column("float64", Check.in_range(0, 5), nullable=True),
    },
    strict=False,  # allow extra columns (optional passthrough, derived features)
    coerce=True,
)

CURATED_OCCUPANCY_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", unique=True, nullable=False),
        "occupancy_est": Column("float64", Check.in_range(0, 1), nullable=False),
    },
    strict=False,
    coerce=True,
)

CURATED_SEASONALITY_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", nullable=False),
        "month": Column("int64", Check.in_range(1, 12), nullable=False),
        "dow": Column("int64", Check.in_range(0, 6), nullable=False),
        "median_cal_price": Column("float64", Check.ge(0), nullable=True),
        "booked_rate": Column("float64", Check.in_range(0, 1), nullable=False),
    },
    strict=False,
    coerce=True,
    unique=["listing_id", "month", "dow"],
)

# Market-level, horizon-detrended seasonality (grain = 1 row per calendar date).
# horizon_days intentionally has NO lower bound: a snapshot taken after some
# calendar dates yields negative horizons, which are valid (see seasonality.py).
# event_uplift = unavail_rate - baseline, so it lives in [-1, 1].
CURATED_SEASONALITY_DETRENDED_SCHEMA = DataFrameSchema(
    {
        "date": Column("datetime64[ns]", nullable=False),
        "dow": Column("int64", Check.in_range(0, 6), nullable=False),
        "horizon_days": Column("int64", nullable=False),
        "unavail_rate": Column("float64", Check.in_range(0, 1), nullable=False),
        "baseline": Column("float64", Check.in_range(0, 1), nullable=False),
        "event_uplift": Column("float64", Check.in_range(-1, 1), nullable=False),
        # Dense, non-nullable NumPy bool (DuckDB emits it filled). Deliberately
        # NOT the pandas "boolean" ExtensionType used for the nullable t/f/None
        # flags in CURATED_LISTINGS_SCHEMA -- is_edge is never null.
        "is_edge": Column("bool", nullable=False),
    },
    strict=False,
    coerce=True,
    unique=["date"],
)


def validate_curated_listings(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated listings table against its contract. Raises on violation."""
    return CURATED_LISTINGS_SCHEMA.validate(df, lazy=False)


def validate_curated_occupancy(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated occupancy table. Raises on violation."""
    return CURATED_OCCUPANCY_SCHEMA.validate(df, lazy=False)


def validate_curated_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated seasonality table. Raises on violation."""
    return CURATED_SEASONALITY_SCHEMA.validate(df, lazy=False)


def validate_curated_seasonality_detrended(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the detrended (market-level) seasonality table. Raises on violation."""
    return CURATED_SEASONALITY_DETRENDED_SCHEMA.validate(df, lazy=False)
