import pandas as pd
import pytest
from pandera.errors import SchemaError

from src.schemas import (
    validate_curated_listings,
    validate_curated_occupancy,
    validate_curated_seasonality,
    validate_curated_seasonality_detrended,
)
from src.transform.listings import build_curated_listings


def test_valid_curated_listings_passes(raw_listings):
    out = build_curated_listings(raw_listings)
    validate_curated_listings(out)  # should not raise


def test_duplicate_listing_id_fails(raw_listings):
    out = build_curated_listings(raw_listings)
    dup = pd.concat([out, out.iloc[[0]]], ignore_index=True)
    with pytest.raises(SchemaError):
        validate_curated_listings(dup)


def test_negative_price_fails(raw_listings):
    out = build_curated_listings(raw_listings).copy()
    out.loc[0, "price"] = -10.0
    with pytest.raises(SchemaError):
        validate_curated_listings(out)


def test_valid_curated_occupancy():
    df = pd.DataFrame({"listing_id": [1, 2], "occupancy_est": [0.3, 0.5]})
    validate_curated_occupancy(df)


def test_occupancy_out_of_range_fails():
    df = pd.DataFrame({"listing_id": [1], "occupancy_est": [1.5]})
    with pytest.raises(SchemaError):
        validate_curated_occupancy(df)


def test_valid_curated_seasonality():
    df = pd.DataFrame(
        {
            "listing_id": [1, 1],
            "month": [1, 2],
            "dow": [3, 4],
            "median_cal_price": [500.0, 500.0],
            "booked_rate": [0.6, 0.2],
        }
    )
    validate_curated_seasonality(df)


def test_seasonality_duplicate_key_fails():
    df = pd.DataFrame(
        {
            "listing_id": [1, 1],
            "month": [1, 1],
            "dow": [3, 3],
            "median_cal_price": [500.0, 500.0],
            "booked_rate": [0.6, 0.2],
        }
    )
    with pytest.raises(SchemaError):
        validate_curated_seasonality(df)


def _detrended_df() -> pd.DataFrame:
    """Valid market-level detrended seasonality (grain = 1 row/date).

    Mirrors what `seasonality_from_table` emits: horizon_days may be negative
    (calendar dates predating the snapshot) and is_edge is a plain bool.
    """
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "dow": [4, 5, 6],
            "horizon_days": [-89, -88, -87],
            "unavail_rate": [0.0, 0.5, 0.5],
            "baseline": [0.25, 0.30, 0.40],
            "event_uplift": [-0.25, 0.20, 0.10],
            "is_edge": [True, True, False],
        }
    )


def test_valid_curated_seasonality_detrended():
    validate_curated_seasonality_detrended(_detrended_df())  # should not raise


def test_seasonality_detrended_duplicate_date_fails():
    df = _detrended_df()
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # repeats 2026-01-01
    with pytest.raises(SchemaError):
        validate_curated_seasonality_detrended(dup)


def test_seasonality_detrended_unavail_rate_out_of_range_fails():
    df = _detrended_df().copy()
    df.loc[0, "unavail_rate"] = 1.5  # outside [0, 1]
    with pytest.raises(SchemaError):
        validate_curated_seasonality_detrended(df)


def test_seasonality_detrended_event_uplift_out_of_range_fails():
    # event_uplift is the only asymmetric range ([-1, 1]); guard it explicitly.
    df = _detrended_df().copy()
    df.loc[0, "event_uplift"] = 1.5  # outside [-1, 1]
    with pytest.raises(SchemaError):
        validate_curated_seasonality_detrended(df)
