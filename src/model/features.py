"""Curated listings -> (X design matrix, y=log_price, FeatureMeta). Pure function, no I/O.

Encodes the 2026-06-12 feature-governance decisions: drop all-null + leakage + collinear cols,
fold the n=13 Hotel room into Entire home/apt, collapse property_type to top-K, pool rare
neighbourhoods, and expose neighbourhood as a categorical for fixed-effects expansion in hedonic.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import config


@dataclass(frozen=True)
class FeatureMeta:
    neighbourhood: pd.Series  # pooled categorical, aligned to X.index (for C(neighbourhood) FE)
    dropped: tuple[str, ...]
    n_rows: int


def _collapse_top_k(s: pd.Series, k: int) -> pd.Series:
    top = s.value_counts().nlargest(k).index
    return s.where(s.isin(top), "Other")


def build_model_matrix(listings: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, FeatureMeta]:
    df = listings.loc[listings["price"] > 0].reset_index(drop=True)
    y = np.log(df["price"].astype(float)).rename("log_price")

    room = df["room_type"].replace({"Hotel room": "Entire home/apt"})
    prop = _collapse_top_k(
        df["property_type"].astype("string").fillna("Other"), config.PROPERTY_TYPE_TOP_K
    )
    nb_counts = df["neighbourhood"].value_counts()
    rare = nb_counts[nb_counts < config.MIN_NEIGHBOURHOOD_N].index
    neighbourhood = df["neighbourhood"].where(~df["neighbourhood"].isin(rare), "Other")

    numeric = pd.DataFrame(
        {
            "accommodates": pd.to_numeric(df["accommodates"], errors="coerce"),
            "bedrooms": pd.to_numeric(df["bedrooms"], errors="coerce"),
            "bathrooms_num": pd.to_numeric(df["bathrooms_num"], errors="coerce"),
            "min_nights": pd.to_numeric(df["min_nights"], errors="coerce"),
        }
    )
    numeric = numeric.fillna(numeric.median(numeric_only=True))

    superhost = pd.to_numeric(df["host_is_superhost"], errors="coerce")
    no_review = (pd.to_numeric(df["number_of_reviews"], errors="coerce").fillna(0) == 0).astype(int)
    cap_bucket = pd.cut(
        numeric["accommodates"], bins=config.CAP_BUCKET_EDGES, labels=config.CAP_BUCKET_LABELS
    )

    X = pd.concat(
        [
            numeric,
            pd.get_dummies(room, prefix="room_type", drop_first=True),
            pd.get_dummies(prop, prefix="property_type", drop_first=True),
            superhost.fillna(0).rename("host_is_superhost"),
            superhost.isna().astype(int).rename("superhost_missing"),
            no_review.rename("no_review_history"),
            cap_bucket.rename("cap_bucket"),
        ],
        axis=1,
    )

    dropped = config.MODEL_DROP_ALL_NULL + config.MODEL_DROP_LEAKAGE + config.MODEL_DROP_COLLINEAR
    return X, y, FeatureMeta(neighbourhood=neighbourhood, dropped=dropped, n_rows=len(df))
