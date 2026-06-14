"""Seasonality CONTEXT from the horizon-detrended calendar — an indicator, not a price modulator.

is_edge rows (near-snapshot artifacts, uplift up to +0.22) are hard-filtered out. event_uplift is a
LOWER BOUND: far-horizon peaks (Réveillon) hit the 0.699 ceiling, so the true premium is larger.
A future multi-snapshot pull would de-saturate these (path to a v2 seasonal model).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_EVENT_WINDOWS = {  # (month, day) ranges, snapshot-year agnostic
    "Réveillon": ((12, 28), (1, 2)),
    "Carnaval": ((2, 6), (2, 12)),
}


@dataclass(frozen=True)
class DemandContext:
    top_dates: pd.DataFrame
    events: dict[str, float]
    magnitudes_are_lower_bounds: bool = True
    dropped_edge: int = 0


def _window_mask(dates: pd.Series, lo: tuple[int, int], hi: tuple[int, int]) -> pd.Series:
    """Vectorized (month, day) window membership; handles year-end wrap (e.g. Dec 28 -> Jan 2).

    Encode each date as month*100 + day, which is monotone in (month, day), so the window test is
    two comparisons instead of a per-row Python call.
    """
    md = dates.dt.month * 100 + dates.dt.day
    lo_ord, hi_ord = lo[0] * 100 + lo[1], hi[0] * 100 + hi[1]
    if lo[0] > hi[0]:  # window wraps the year-end
        return (md >= lo_ord) | (md <= hi_ord)
    return (md >= lo_ord) & (md <= hi_ord)


def seasonal_context(detrended: pd.DataFrame, top_n: int = 10) -> DemandContext:
    # is_edge may arrive as a pandas nullable `boolean` (curated ExtensionType); ~NA would propagate
    # NA and break .loc masking, so coerce to numpy bool with NA treated as "not an edge".
    edge = detrended["is_edge"].fillna(False).astype(bool)
    clean = detrended.loc[~edge].copy()
    top = clean.nlargest(top_n, "event_uplift")[["date", "dow", "horizon_days", "event_uplift"]]
    events: dict[str, float] = {}
    for name, (lo, hi) in _EVENT_WINDOWS.items():
        hit = clean[_window_mask(clean["date"], lo, hi)]
        if not hit.empty:
            events[name] = float(hit["event_uplift"].max())
    return DemandContext(top.reset_index(drop=True), events, dropped_edge=int(edge.sum()))
