"""Build the curated listings table (grain: 1 row = 1 analyzable listing).

Pure function: raw DataFrame in, typed curated DataFrame out. No I/O.
Replaces the removed `cancellation_policy` with operational flexibility proxies.
Works whether the raw frame comes from pandas (native dtypes) or from DuckDB
read with all_varchar=true (everything arrives as strings) — all casts below
tolerate string inputs.
"""

from __future__ import annotations

import pandas as pd

from src.config import PRICE_WINSOR_LOWER_Q, PRICE_WINSOR_UPPER_Q, RIO_BEACHES
from src.transform.clean_price import clean_price
from src.transform.geo import distance_to_nearest_beach_km
from src.transform.parse_fields import parse_bathrooms, parse_percent, parse_tf_bool

# Optional columns kept only if the dump provides them (schema-flexible).
OPTIONAL_PASSTHROUGH = ("estimated_occupancy_l365d", "estimated_revenue_l365d")


def _winsorize(s: pd.Series, lower_q: float, upper_q: float) -> pd.Series:
    lo, hi = s.quantile(lower_q), s.quantile(upper_q)
    return s.clip(lower=lo, upper=hi)


def build_curated_listings(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean, type, and feature-engineer raw listings into the curated table."""
    df = pd.DataFrame(
        {
            "listing_id": pd.to_numeric(raw["id"], errors="coerce").astype("int64"),
            "neighbourhood": raw["neighbourhood_cleansed"].astype("string"),
            "room_type": raw["room_type"].astype("string"),
            "property_type": raw["property_type"].astype("string"),
            "accommodates": pd.to_numeric(raw["accommodates"], errors="coerce").astype("Int64"),
            "bedrooms": pd.to_numeric(raw["bedrooms"], errors="coerce").astype("Int64"),
            "beds": pd.to_numeric(raw["beds"], errors="coerce").astype("Int64"),
            "bathrooms_num": parse_bathrooms(raw["bathrooms_text"]),
            "price": clean_price(raw["price"]),
            "distance_to_beach_km": pd.Series(
                distance_to_nearest_beach_km(
                    pd.to_numeric(raw["latitude"], errors="coerce").to_numpy(),
                    pd.to_numeric(raw["longitude"], errors="coerce").to_numpy(),
                    RIO_BEACHES,
                ),
                index=raw.index,
            ).astype("float64"),
            "min_nights": pd.to_numeric(raw["minimum_nights"], errors="coerce").astype("Int64"),
            "host_is_superhost": parse_tf_bool(raw["host_is_superhost"]),
            "instant_bookable": parse_tf_bool(raw["instant_bookable"]),
            "host_response_time": raw["host_response_time"].astype("string"),
            "host_response_rate": parse_percent(raw["host_response_rate"]),
            "host_acceptance_rate": parse_percent(raw["host_acceptance_rate"]),
            "number_of_reviews": pd.to_numeric(raw["number_of_reviews"], errors="coerce").astype(
                "Int64"
            ),
            "number_of_reviews_ltm": pd.to_numeric(
                raw["number_of_reviews_ltm"], errors="coerce"
            ).astype("Int64"),
            "reviews_per_month": pd.to_numeric(raw["reviews_per_month"], errors="coerce").astype(
                "float64"
            ),
            "review_scores_rating": pd.to_numeric(
                raw["review_scores_rating"], errors="coerce"
            ).astype("float64"),
            "availability_365": pd.to_numeric(raw["availability_365"], errors="coerce").astype(
                "Int64"
            ),
            "last_review": pd.to_datetime(raw["last_review"], errors="coerce"),
            "first_review": pd.to_datetime(raw["first_review"], errors="coerce"),
        }
    )

    for col in OPTIONAL_PASSTHROUGH:
        if col in raw.columns:
            df[col] = pd.to_numeric(raw[col], errors="coerce")

    # Treat empty strings (from CSV reads) as missing for the analysis keys.
    for key in ("neighbourhood", "room_type"):
        df[key] = df[key].replace("", pd.NA)

    # Keep only analyzable listings: positive price + neighbourhood + room_type.
    # price > 0 is deliberate — a free listing has no RevPAN to optimize.
    keep = (
        df["price"].notna()
        & (df["price"] > 0)
        & df["neighbourhood"].notna()
        & df["room_type"].notna()
    )
    df = df.loc[keep].reset_index(drop=True)

    # Winsorize price to documented quantiles (spec section 6: outlier handling).
    df["price"] = _winsorize(df["price"], PRICE_WINSOR_LOWER_Q, PRICE_WINSOR_UPPER_Q)

    return df
