"""End-to-end orchestration: raw host input -> price-positioning recommendation.

This is the single tested entry point the Streamlit app calls, so the app stays a thin UI with
ZERO business logic (spec section 4). It wires build_model_matrix -> fit_hedonic (price-space
predict) -> shrunk peer positioning -> seasonal demand context -> recommend_price, and surfaces two
honesty flags the raw modules cannot on their own: whether the neighbourhood was actually a
modelled fixed effect (vs pooled into "Other"/unseen), and whether any comparable peers were found.

Design choice: instead of re-deriving the one-hot encoding by hand (which could drift from
features.build_model_matrix and silently mis-key the design vector), the input row is APPENDED to
the training market and the SAME feature pipeline is re-run; the last row is then re-indexed onto
the fitted model's feature columns. Encoding can't diverge from the fit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import config
from src.model.comparables import PeerPosition, peer_positioning
from src.model.demand_context import DemandContext, seasonal_context
from src.model.features import build_model_matrix
from src.model.hedonic import FittedHedonic, fit_hedonic
from src.model.recommender import PriceRecommendation, recommend_price

# Columns build_model_matrix consumes; the appended input row must supply all of them.
_INPUT_LISTING_COLS = (
    "price",
    "neighbourhood",
    "room_type",
    "property_type",
    "accommodates",
    "bedrooms",
    "bathrooms_num",
    "min_nights",
    "host_is_superhost",
    "number_of_reviews",
)


@dataclass(frozen=True)
class HostInput:
    """Raw listing attributes a host enters in the app (pre-feature-engineering)."""

    neighbourhood: str
    room_type: str
    property_type: str
    accommodates: int
    bedrooms: float
    bathrooms_num: float
    min_nights: int
    host_is_superhost: bool
    number_of_reviews: int
    current_price: float | None = None  # None -> percentile/peer price falls back to the estimate


@dataclass(frozen=True)
class FittedAdvisor:
    """A fitted model + the training market, ready to advise many listings (fit once, reuse)."""

    fitted: FittedHedonic
    coefs: pd.DataFrame
    listings: pd.DataFrame  # training market, used for peer comparison
    seen_neighbourhoods: frozenset[str]
    adj_r2: float


@dataclass(frozen=True)
class ListingAdvice:
    """Everything the UI needs to render an honest recommendation card."""

    recommendation: PriceRecommendation
    peer: PeerPosition
    hedonic_price: float
    neighbourhood_in_model: bool  # False -> estimated off the baseline, flag it in the UI
    has_peer_signal: bool  # False -> "no comparable listings", not a fake 0.5 position
    demand: DemandContext


def fit_advisor(listings: pd.DataFrame) -> FittedAdvisor:
    """Fit the hedonic model once over the curated market; reuse for every recommendation."""
    x, y, meta = build_model_matrix(listings)
    result = fit_hedonic(x, y, meta.neighbourhood)
    seen = frozenset(str(c) for c in result.fitted.encoder.categories_[0])
    return FittedAdvisor(
        fitted=result.fitted,
        coefs=result.coefs,
        listings=listings.reset_index(drop=True),
        seen_neighbourhoods=seen,
        adj_r2=result.adj_r2,
    )


def recommend(advisor: FittedAdvisor, inp: HostInput, detrended: pd.DataFrame) -> ListingAdvice:
    """Advise one listing end to end. Pure read over the fitted model + curated market."""
    listings = advisor.listings
    parent_median = float(listings["price"].median())
    current_price = (
        float(inp.current_price)
        if inp.current_price is not None and inp.current_price > 0
        else None
    )

    hedonic_price, nb_pooled = _predict_price(advisor, inp, listings, parent_median, current_price)

    peers_df = listings.assign(cap_bucket=_cap_bucket_series(listings["accommodates"]))
    target = pd.Series(
        {
            "neighbourhood": inp.neighbourhood,
            "room_type": inp.room_type,
            "cap_bucket": _cap_bucket_scalar(inp.accommodates),
            # percentile = where the listing sits among peers; no current price -> use the estimate
            "price": current_price if current_price is not None else hedonic_price,
        }
    )
    peer = peer_positioning(target, peers_df)

    demand = seasonal_context(detrended)
    rec = recommend_price(
        hedonic_point=hedonic_price,
        peer_median=peer.shrunk_median,
        peer_iqr=peer.iqr,
        price_percentile=peer.price_percentile,
        top_drivers=_top_drivers(advisor.coefs),
        demand_note=_demand_note(demand),
    )
    return ListingAdvice(
        recommendation=rec,
        peer=peer,
        hedonic_price=hedonic_price,
        neighbourhood_in_model=nb_pooled in advisor.seen_neighbourhoods and nb_pooled != "Other",
        has_peer_signal=peer.n_effective > 0,
        demand=demand,
    )


def _predict_price(
    advisor: FittedAdvisor,
    inp: HostInput,
    listings: pd.DataFrame,
    parent_median: float,
    current_price: float | None,
) -> tuple[float, str]:
    """Build the input's design row via the training pipeline, then predict a price-space point."""
    row = {
        "price": current_price if current_price is not None else parent_median,
        "neighbourhood": inp.neighbourhood,
        "room_type": inp.room_type,
        "property_type": inp.property_type,
        "accommodates": float(inp.accommodates),
        "bedrooms": float(inp.bedrooms),
        "bathrooms_num": float(inp.bathrooms_num),
        "min_nights": float(inp.min_nights),
        "host_is_superhost": float(inp.host_is_superhost),
        "number_of_reviews": float(inp.number_of_reviews),
    }
    augmented = pd.concat(
        [listings[list(_INPUT_LISTING_COLS)], pd.DataFrame([row])], ignore_index=True
    )
    x_all, _, meta = build_model_matrix(augmented)
    # Re-index onto the fitted columns: unseen dummies (e.g. an unknown room_type) drop out, and
    # columns the input didn't trigger fill with 0 — exactly the one-hot "absent level" encoding.
    x_row = x_all.iloc[-1].reindex(advisor.fitted.feature_cols).fillna(0.0)
    nb_pooled = str(meta.neighbourhood.iloc[-1])
    return advisor.fitted.predict_price(x_row, nb_pooled), nb_pooled


def _cap_bucket_series(accommodates: pd.Series) -> pd.Series:
    nums = pd.to_numeric(accommodates, errors="coerce").astype("float64")
    return pd.cut(nums, bins=config.CAP_BUCKET_EDGES, labels=config.CAP_BUCKET_LABELS)


def _cap_bucket_scalar(accommodates: int) -> str:
    bucket = pd.cut(
        [float(accommodates)], bins=config.CAP_BUCKET_EDGES, labels=config.CAP_BUCKET_LABELS
    )[0]
    return str(bucket)


def _top_drivers(coefs: pd.DataFrame, k: int = 5) -> list[tuple[str, float]]:
    effects = coefs["effect"].astype(float)
    order = effects.abs().sort_values(ascending=False).index[:k]
    return [(str(feat), float(effects[feat])) for feat in order]


def _demand_note(demand: DemandContext) -> str:
    if not demand.events:
        return "No strong dated demand peaks in the detrended calendar (lower-bound signal)."
    parts = [f"{name} +{uplift:.0%}" for name, uplift in demand.events.items()]
    return "Seasonal demand (lower bound): " + ", ".join(parts) + "."
