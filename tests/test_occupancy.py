import pandas as pd

from src.config import SF_AVG_LENGTH_OF_STAY, SF_MAX_OCCUPANCY, SF_REVIEW_RATE
from src.transform.occupancy import estimate_occupancy, sf_model_occupancy


def test_sf_model_basic():
    # reviews_ltm=12 -> stays = 12 / 0.5 = 24 -> nights = 24*4 = 96 -> /365
    out = sf_model_occupancy(pd.Series([12.0]))
    expected = min((12 / SF_REVIEW_RATE) * SF_AVG_LENGTH_OF_STAY / 365.0, SF_MAX_OCCUPANCY)
    assert round(out.iloc[0], 4) == round(expected, 4)


def test_sf_model_caps_at_max():
    out = sf_model_occupancy(pd.Series([1000.0]))
    assert out.iloc[0] == SF_MAX_OCCUPANCY


def test_sf_model_zero_reviews_is_zero():
    out = sf_model_occupancy(pd.Series([0.0, None]))
    assert out.iloc[0] == 0.0
    assert out.iloc[1] == 0.0


def test_estimate_occupancy_blends_signals():
    listings = pd.DataFrame({"listing_id": [1, 2], "number_of_reviews_ltm": [12.0, 0.0]})
    cal_booked = pd.Series([0.6, 0.2], index=[1, 2])  # booked_rate per listing_id
    out = estimate_occupancy(listings, cal_booked)
    assert {"listing_id", "occupancy_est"}.issubset(out.columns)
    assert out["occupancy_est"].between(0, 1).all()
    occ = out.set_index("listing_id")["occupancy_est"]
    assert round(occ[2], 4) == 0.1  # sf=0.0, cal=0.2 -> mean = 0.1
    assert round(occ[1], 2) == 0.43  # sf~0.263, cal=0.6 -> mean ~0.4315


def test_estimate_occupancy_missing_calendar_is_finite():
    # listing 2 absent from cal_booked and has no reviews -> must not be NaN.
    listings = pd.DataFrame({"listing_id": [1, 2], "number_of_reviews_ltm": [12.0, None]})
    cal_booked = pd.Series([0.6], index=[1])
    out = estimate_occupancy(listings, cal_booked)
    occ = out.set_index("listing_id")["occupancy_est"]
    assert occ.notna().all()
    assert occ[2] == 0.0
    assert out["occupancy_est"].between(0, 1).all()
