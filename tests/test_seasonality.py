import duckdb
import pandas as pd
import pytest

from src.transform.seasonality import seasonality_from_calendar, seasonality_from_table


def _market_calendar(
    *,
    n_days: int,
    snapshot: str,
    n_listings: int,
    base_unavail: int,
    spikes: dict[int, int] | None = None,
) -> pd.DataFrame:
    """Synthetic raw calendar (grain = 1 row per listing-day).

    On each date, `base_unavail` of `n_listings` are marked unavailable ('f'),
    so the market unavail_rate = base_unavail / n_listings. `spikes` overrides
    that count on specific day indices to plant a local demand spike.
    """
    spikes = spikes or {}
    dates = pd.date_range(snapshot, periods=n_days, freq="D")
    rows = []
    for i, dt in enumerate(dates):
        k = spikes.get(i, base_unavail)
        avails = ["f"] * k + ["t"] * (n_listings - k)
        for lid, a in enumerate(avails):
            rows.append({"listing_id": lid, "date": dt.strftime("%Y-%m-%d"), "available": a})
    return pd.DataFrame(rows)


def test_grain_keys_and_horizon():
    cal = _market_calendar(n_days=10, snapshot="2026-01-01", n_listings=4, base_unavail=1)
    out = seasonality_from_calendar(
        con=duckdb.connect(), calendar=cal, snapshot_date="2026-01-01", window=5
    )

    assert len(out) == out["date"].nunique() == 10  # grain: 1 row per date
    expected = {
        "date",
        "dow",
        "horizon_days",
        "unavail_rate",
        "baseline",
        "event_uplift",
        "is_edge",
    }
    assert expected.issubset(out.columns)
    row = out[out["date"].astype(str) == "2026-01-05"].iloc[0]
    assert row["horizon_days"] == 4  # 2026-01-05 minus snapshot 2026-01-01
    assert row["unavail_rate"] == 0.25  # 1 of 4 listings unavailable


def test_dow_sunday_is_zero():
    # Convention shared with calendar.py: DAYOFWEEK 0=Sunday. 2026-01-04 is a Sunday.
    cal = _market_calendar(n_days=10, snapshot="2026-01-01", n_listings=2, base_unavail=1)
    out = seasonality_from_calendar(
        con=duckdb.connect(), calendar=cal, snapshot_date="2026-01-01", window=5
    )
    assert out[out["date"].astype(str) == "2026-01-04"].iloc[0]["dow"] == 0
    assert out["dow"].between(0, 6).all()


def test_event_uplift_isolates_local_spike():
    # Flat 0.3 unavail with a single 0.9 spike at interior index 30 (2026-01-31).
    cal = _market_calendar(
        n_days=61, snapshot="2026-01-01", n_listings=10, base_unavail=3, spikes={30: 9}
    )
    out = seasonality_from_calendar(
        con=duckdb.connect(), calendar=cal, snapshot_date="2026-01-01", window=29
    )

    interior = out[~out["is_edge"]]
    top = interior.sort_values("event_uplift", ascending=False).iloc[0]
    assert pd.Timestamp(top["date"]).strftime("%Y-%m-%d") == "2026-01-31"  # day index 30
    assert top["event_uplift"] > 0.4  # spike (0.9) stands well above its local baseline
    # Flat interior days (still at 0.3) carry essentially no uplift.
    flat = interior[interior["unavail_rate"] == 0.3]
    assert flat["event_uplift"].abs().max() < 0.1


def test_edge_days_flagged():
    cal = _market_calendar(n_days=61, snapshot="2026-01-01", n_listings=10, base_unavail=3)
    out = (
        seasonality_from_calendar(
            con=duckdb.connect(), calendar=cal, snapshot_date="2026-01-01", window=29
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    half = 29 // 2  # 14
    assert out.loc[: half - 1, "is_edge"].all()  # first 14 rows: baseline truncated
    assert out.loc[len(out) - half :, "is_edge"].all()  # last 14 rows
    assert not out.loc[half : len(out) - half - 1, "is_edge"].any()  # interior


def test_from_table_is_the_pipeline_entry_point():
    # The pipeline calls the table variant; it must match the in-memory one.
    cal = _market_calendar(n_days=10, snapshot="2026-01-01", n_listings=4, base_unavail=1)
    con = duckdb.connect()
    con.register("cal_src", cal)
    con.execute("CREATE TABLE raw_calendar AS SELECT * FROM cal_src")
    out = seasonality_from_table(con, "raw_calendar", snapshot_date="2026-01-01", window=5)
    assert len(out) == 10
    expected = {
        "date",
        "dow",
        "horizon_days",
        "unavail_rate",
        "baseline",
        "event_uplift",
        "is_edge",
    }
    assert expected.issubset(out.columns)


def test_rejects_bad_table_name():
    with pytest.raises(ValueError):
        seasonality_from_table(duckdb.connect(), "raw; DROP TABLE x", snapshot_date="2026-01-01")


def test_rejects_bad_snapshot_date():
    cal = _market_calendar(n_days=3, snapshot="2026-01-01", n_listings=2, base_unavail=1)
    with pytest.raises(ValueError):
        seasonality_from_calendar(
            duckdb.connect(), cal, snapshot_date="2026-01-01'; DROP", window=3
        )
