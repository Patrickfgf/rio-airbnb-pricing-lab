import pandas as pd
import pytest
from pandera.errors import SchemaError

from src.schemas import (
    validate_curated_listings,
    validate_curated_occupancy,
    validate_curated_seasonality,
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
