import pandas as pd

from src.model.demand_context import seasonal_context


def _detrended():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-03-30", "2026-12-31", "2027-01-01", "2027-02-07", "2026-07-15"]
            ),
            "dow": [0, 4, 5, 6, 2],
            "horizon_days": [0, 276, 277, 314, 107],
            "unavail_rate": [0.63, 0.67, 0.66, 0.60, 0.30],
            "baseline": [0.45, 0.58, 0.58, 0.57, 0.30],
            "event_uplift": [0.22, 0.093, 0.083, 0.027, 0.0],
            "is_edge": [True, False, False, False, False],
        }
    )


def test_edge_dates_excluded():
    ctx = seasonal_context(_detrended())
    assert pd.Timestamp("2026-03-30") not in set(ctx.top_dates["date"])
    assert ctx.dropped_edge == 1


def test_known_events_surface_with_lower_bound_flag():
    ctx = seasonal_context(_detrended())
    assert "Réveillon" in ctx.events and "Carnaval" in ctx.events
    assert ctx.magnitudes_are_lower_bounds is True


def test_reveillon_spans_year_boundary():
    # Jan 1 (2027-01-01) must count toward Réveillon even though it is a different year/month
    ctx = seasonal_context(_detrended())
    assert ctx.events["Réveillon"] >= 0.083  # picks up Dec 31 (0.093) and Jan 1 (0.083)
