# tests/test_features.py
import numpy as np
import pandas as pd
import pytest

from src.model.features import build_model_matrix


@pytest.fixture
def toy_listings():
    n = 60
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "listing_id": range(n),
            "price": rng.uniform(100, 2000, n),
            "neighbourhood": ["Copacabana"] * 40 + ["RareHood"] * 1 + ["Ipanema"] * 19,
            "room_type": ["Entire home/apt"] * 50 + ["Private room"] * 9 + ["Hotel room"] * 1,
            "property_type": (  # 11 distinct > PROPERTY_TYPE_TOP_K=8 -> collapse fires
                ["Entire rental unit"] * 50 + [f"Exotic {i}" for i in range(10)]
            ),
            # Curated parquet dtypes: Int64 / boolean nullable ExtensionTypes (NOT numpy int/float).
            "accommodates": pd.array(rng.integers(1, 9, n), dtype="Int64"),
            "bedrooms": pd.array(rng.integers(1, 4, n), dtype="Int64"),
            "beds": pd.array(rng.integers(1, 5, n), dtype="Int64"),
            "bathrooms_num": rng.uniform(1, 3, n),
            "min_nights": pd.array(rng.integers(1, 30, n), dtype="Int64"),
            "host_is_superhost": pd.array([True, False, None] * 20, dtype="boolean"),
            "number_of_reviews": [0] * 12 + list(rng.integers(1, 50, n - 12)),
            "number_of_reviews_ltm": rng.integers(0, 20, n),
            "availability_365": rng.integers(0, 365, n),
            "estimated_occupancy_l365d": rng.integers(0, 200, n),
            "estimated_revenue_l365d": rng.uniform(0, 1e5, n),
            "instant_bookable": [pd.NA] * n,
        }
    )


def test_target_is_log_price_no_nan(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert (y > 0).all() and not y.isna().any()
    assert np.allclose(np.exp(y.iloc[0]), toy_listings["price"].iloc[0])


def test_leakage_and_collinear_columns_absent(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    banned = {
        "beds",
        "availability_365",
        "estimated_occupancy_l365d",
        "estimated_revenue_l365d",
        "instant_bookable",
        "price",
    }
    assert banned.isdisjoint(X.columns)


def test_rare_neighbourhood_pooled(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert "RareHood" not in set(meta.neighbourhood)
    assert "Other" in set(meta.neighbourhood)


def test_hotel_folded_and_no_review_flag(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert "room_type_Hotel room" not in X.columns
    assert X["no_review_history"].sum() == 12


def test_property_type_collapsed(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    pt_cols = [c for c in X.columns if c.startswith("property_type_")]
    assert any(c.endswith("Other") for c in pt_cols)


def test_nullable_extension_dtypes(toy_listings):
    # curated parquet carries boolean / Int64 nullable dtypes; conversion must not raise
    X, y, meta = build_model_matrix(toy_listings)
    assert str(X["accommodates"].dtype) == "float64"
    assert X["host_is_superhost"].notna().all()  # NA filled to 0.0
    assert X["superhost_missing"].sum() == 20  # 20 None in the fixture
