import duckdb

from src.transform.calendar import aggregate_calendar


def test_booked_rate_from_availability(raw_calendar):
    con = duckdb.connect()
    out = aggregate_calendar(con, raw_calendar)
    # 5 dates 2026-01-01..05 each fall on a DISTINCT day-of-week, so each
    # (listing, month, dow) group has 1 row (booked_rate 0.0 or 1.0). Averaging
    # those per-listing => listing 1: 3 unavailable / 5 = 0.6 ; listing 2: 1/5 = 0.2.
    by_listing = out.groupby("listing_id")["booked_rate"].mean().round(3).to_dict()
    assert by_listing[1] == 0.6
    assert by_listing[2] == 0.2


def test_has_calendar_price_and_keys(raw_calendar):
    con = duckdb.connect()
    out = aggregate_calendar(con, raw_calendar)
    assert {"listing_id", "month", "dow", "median_cal_price", "booked_rate"}.issubset(out.columns)
    assert (out["median_cal_price"] == 500.0).all()
