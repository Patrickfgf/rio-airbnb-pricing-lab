"""Integration test for the end-to-end advisor glue (features -> hedonic -> peers -> recommend).

This is the cross-module test the Phase-2 audit flagged as missing: every other test exercises one
module in isolation; this one wires a single host input through the whole stack on a shared market.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.model.service import HostInput, fit_advisor, recommend


@pytest.fixture
def market() -> pd.DataFrame:
    """A synthetic but realistic Rio-shaped market: 2 neighbourhoods, price ~ area + location."""
    rng = np.random.default_rng(42)
    n = 240
    neighbourhood = rng.choice(["Copacabana", "Ipanema"], size=n, p=[0.6, 0.4])
    room_type = rng.choice(["Entire home/apt", "Private room"], size=n, p=[0.7, 0.3])
    accommodates = rng.integers(1, 7, size=n).astype(float)
    bedrooms = rng.integers(1, 4, size=n).astype(float)
    bathrooms = rng.choice([1.0, 1.5, 2.0], size=n)
    min_nights = rng.integers(1, 5, size=n).astype(float)
    superhost = rng.integers(0, 2, size=n).astype(float)
    superhost[rng.random(n) < 0.1] = np.nan  # real dumps have missing superhost -> varied flag
    reviews = rng.integers(0, 60, size=n).astype(float)

    base = np.where(neighbourhood == "Ipanema", 600.0, 420.0)
    room_adj = np.where(room_type == "Private room", -150.0, 0.0)
    price = base + room_adj + accommodates * 55 + rng.normal(0, 40, size=n)
    price = np.clip(price, 90.0, None)

    return pd.DataFrame(
        {
            "listing_id": np.arange(n),
            "price": price,
            "neighbourhood": neighbourhood,
            "room_type": room_type,
            "property_type": "Entire rental unit",
            "accommodates": accommodates,
            "bedrooms": bedrooms,
            "bathrooms_num": bathrooms,
            "min_nights": min_nights,
            "host_is_superhost": superhost,
            "number_of_reviews": reviews,
        }
    )


@pytest.fixture
def detrended() -> pd.DataFrame:
    """Minimal horizon-detrended seasonality table covering a Réveillon window."""
    dates = pd.date_range("2026-12-20", periods=30, freq="D")
    uplift = np.where((dates.month == 12) & (dates.day >= 28), 0.30, 0.02)
    return pd.DataFrame(
        {
            "date": dates,
            "dow": dates.dayofweek,
            "horizon_days": np.arange(len(dates)),
            "event_uplift": uplift,
            "is_edge": False,
        }
    )


def test_recommend_known_market_is_coherent(market, detrended):
    advisor = fit_advisor(market)
    inp = HostInput(
        neighbourhood="Copacabana",
        room_type="Entire home/apt",
        property_type="Entire rental unit",
        accommodates=4,
        bedrooms=2,
        bathrooms_num=1.0,
        min_nights=2,
        host_is_superhost=True,
        number_of_reviews=12,
        current_price=500.0,
    )
    advice = recommend(advisor, inp, detrended)
    rec = advice.recommendation

    assert rec.low <= rec.anchor <= rec.high
    assert advice.hedonic_price > 0
    assert advice.has_peer_signal is True  # plenty of Copacabana/Entire peers
    assert advice.neighbourhood_in_model is True
    assert 0.0 <= rec.price_percentile <= 1.0
    assert len(rec.top_drivers) <= 5
    assert any("Occupancy" in c or "occupancy" in c for c in rec.caveats)  # honesty caveat present


def test_hedonic_price_is_brl_not_log_space(market, detrended):
    advisor = fit_advisor(market)
    inp = HostInput(
        "Ipanema", "Entire home/apt", "Entire rental unit", 4, 2, 1.0, 2, True, 5, 700.0
    )
    advice = recommend(advisor, inp, detrended)
    # log-space would be ~6-7; a real BRL nightly price is in the hundreds.
    assert advice.hedonic_price > 100
    assert advice.recommendation.anchor > 100


def test_unknown_neighbourhood_is_flagged_and_coarsens(market, detrended):
    advisor = fit_advisor(market)
    inp = HostInput(
        "Atlantis", "Entire home/apt", "Entire rental unit", 4, 2, 1.0, 2, False, 0, None
    )
    advice = recommend(advisor, inp, detrended)

    assert advice.neighbourhood_in_model is False  # not a modelled FE -> UI must flag it
    assert "neighbourhood" not in advice.peer.tier_used  # widened past neighbourhood
    assert advice.hedonic_price > 0  # still finite/positive via handle_unknown='ignore'


def test_no_comparable_signal_uses_neutral_sentinel(market, detrended):
    advisor = fit_advisor(market)
    inp = HostInput("Atlantis", "Treehouse", "Yurt", 4, 2, 1.0, 2, False, 0, None)
    advice = recommend(advisor, inp, detrended)

    assert advice.has_peer_signal is False  # no tier matches an unknown room_type
    assert advice.peer.n_effective == 0
    assert advice.peer.price_percentile == 0.5  # neutral placeholder, not a fake position


def test_demand_note_surfaces_reveillon_lower_bound(market, detrended):
    advisor = fit_advisor(market)
    inp = HostInput(
        "Ipanema", "Entire home/apt", "Entire rental unit", 2, 1, 1.0, 2, False, 3, 450.0
    )
    advice = recommend(advisor, inp, detrended)
    assert "Réveillon" in advice.recommendation.demand_note
    assert advice.demand.magnitudes_are_lower_bounds is True


def _market_with_distance(median_distance: float, n: int = 240, seed: int = 7) -> pd.DataFrame:
    """`market`-shaped frame with a controlled beach-distance gradient (price falls ~5%/km).

    Structure (neighbourhood/room/size/noise) is drawn BEFORE distance, so two calls with the same
    seed differ ONLY in distance + the price it drives — isolating the distance effect cleanly.
    """
    rng = np.random.default_rng(seed)
    neighbourhood = rng.choice(["Copacabana", "Ipanema"], size=n, p=[0.6, 0.4])
    room_type = rng.choice(["Entire home/apt", "Private room"], size=n, p=[0.7, 0.3])
    accommodates = rng.integers(1, 7, size=n).astype(float)
    bedrooms = rng.integers(1, 4, size=n).astype(float)
    bathrooms = rng.choice([1.0, 1.5, 2.0], size=n)
    min_nights = rng.integers(1, 5, size=n).astype(float)
    superhost = rng.integers(0, 2, size=n).astype(float)
    reviews = rng.integers(0, 60, size=n).astype(float)
    noise = rng.normal(0, 10, size=n)
    distance = rng.uniform(median_distance - 1.0, median_distance + 1.0, size=n).clip(min=0.0)

    base = np.where(neighbourhood == "Ipanema", 600.0, 420.0)
    room_adj = np.where(room_type == "Private room", -150.0, 0.0)
    price = (base + room_adj + accommodates * 55) * np.exp(-0.05 * distance) + noise
    price = np.clip(price, 90.0, None)

    return pd.DataFrame(
        {
            "listing_id": np.arange(n),
            "price": price,
            "neighbourhood": neighbourhood,
            "room_type": room_type,
            "property_type": "Entire rental unit",
            "accommodates": accommodates,
            "bedrooms": bedrooms,
            "bathrooms_num": bathrooms,
            "min_nights": min_nights,
            "host_is_superhost": superhost,
            "number_of_reviews": reviews,
            "distance_to_beach_km": distance,
        }
    )


_NO_COORD_INPUT = HostInput(
    neighbourhood="Copacabana",
    room_type="Entire home/apt",
    property_type="Entire rental unit",
    accommodates=4,
    bedrooms=2,
    bathrooms_num=1.0,
    min_nights=2,
    host_is_superhost=True,
    number_of_reviews=12,
    current_price=None,
)


def test_recommender_fits_and_uses_distance_when_present(detrended):
    advisor = fit_advisor(_market_with_distance(median_distance=3.0))
    assert "distance_to_beach_km" in advisor.fitted.feature_cols  # the fit used the feature
    advice = recommend(advisor, _NO_COORD_INPUT, detrended)  # coordinate-less input must not raise
    assert advice.hedonic_price > 0


def test_coordinate_less_input_uses_market_median_distance_not_zero(detrended):
    # The host enters no coordinates. The design row must inherit the market-MEDIAN distance
    # (median-imputed), NOT 0 ("on the beach") — otherwise every recommendation is biased upward.
    near = recommend(
        fit_advisor(_market_with_distance(1.0)), _NO_COORD_INPUT, detrended
    ).hedonic_price
    far = recommend(
        fit_advisor(_market_with_distance(9.0)), _NO_COORD_INPUT, detrended
    ).hedonic_price
    # Farther-from-beach market -> the imputed input sits farther -> lower price. If the input were
    # pinned at distance=0, both markets would predict ~the same hedonic price.
    assert near > far * 1.03
