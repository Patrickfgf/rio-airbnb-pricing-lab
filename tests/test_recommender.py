import math

import pytest

from src import config
from src.model.recommender import PriceRecommendation, recommend_price


def test_returns_valid_range_and_drivers():
    rec = recommend_price(
        hedonic_point=600.0,
        peer_median=500.0,
        peer_iqr=200.0,
        price_percentile=0.8,
        top_drivers=[("accommodates", 0.25), ("neighbourhood=Ipanema", 0.4)],
        demand_note="Réveillon ~+9pp (lower bound)",
    )
    assert isinstance(rec, PriceRecommendation)
    assert rec.low < rec.high
    assert rec.low > 0
    assert len(rec.top_drivers) >= 1
    assert "lower bound" in rec.demand_note
    assert rec.caveats  # must carry the occupancy caveat


def test_no_revpan_optimum_field():
    rec = recommend_price(
        hedonic_point=600.0,
        peer_median=500.0,
        peer_iqr=200.0,
        price_percentile=0.5,
        top_drivers=[],
        demand_note="",
    )
    assert not hasattr(rec, "revpan_max_price")  # we deliberately do NOT expose this


def _rec(**kw):
    base = dict(
        hedonic_point=600.0,
        peer_median=500.0,
        peer_iqr=200.0,
        price_percentile=0.5,
        top_drivers=[],
        demand_note="",
    )
    base.update(kw)
    return recommend_price(**base)


def test_position_labels_cover_all_branches():
    assert _rec(price_percentile=0.10).position_label == "below market"
    assert _rec(price_percentile=0.50).position_label == "in line"
    assert _rec(price_percentile=0.90).position_label == "above market"  # covers the >0.66 branch


def test_anchor_is_configured_blend():
    rec = _rec(hedonic_point=600.0, peer_median=400.0)
    w = config.HEDONIC_MARKET_BLEND_WEIGHT
    assert math.isclose(rec.anchor, w * 600.0 + (1 - w) * 400.0)


def test_band_width_equals_peer_iqr_when_unfloored():
    rec = _rec(peer_iqr=200.0)  # symmetric band = 2 * BAND_IQR_FRACTION * iqr, floor not hit
    assert math.isclose(rec.high - rec.low, 200.0)


def test_large_iqr_floors_low_at_fraction_of_anchor():
    rec = _rec(peer_iqr=5000.0)
    assert math.isclose(rec.low, config.ANCHOR_FLOOR_FRACTION * rec.anchor)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        _rec(peer_iqr=-1.0)
    with pytest.raises(ValueError):
        _rec(price_percentile=1.5)
    with pytest.raises(ValueError):
        _rec(peer_median=0.0)
    with pytest.raises(ValueError):
        _rec(hedonic_point=float("nan"))
