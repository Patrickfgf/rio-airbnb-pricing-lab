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
