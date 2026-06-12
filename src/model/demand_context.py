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


def _in_window(d: pd.Timestamp, lo: tuple[int, int], hi: tuple[int, int]) -> bool:
    md = (d.month, d.day)
    if lo[0] > hi[0]:  # window wraps the year-end (e.g. Dec 28 -> Jan 2)
        return md >= lo or md <= hi
    return lo <= md <= hi


def seasonal_context(detrended: pd.DataFrame, top_n: int = 10) -> DemandContext:
    clean = detrended.loc[~detrended["is_edge"]].copy()
    top = clean.nlargest(top_n, "event_uplift")[["date", "dow", "horizon_days", "event_uplift"]]
    events: dict[str, float] = {}
    for name, (lo, hi) in _EVENT_WINDOWS.items():
        hit = clean[clean["date"].apply(lambda d, lo=lo, hi=hi: _in_window(d, lo, hi))]
        if not hit.empty:
            events[name] = float(hit["event_uplift"].max())
    return DemandContext(
        top.reset_index(drop=True), events, dropped_edge=int(detrended["is_edge"].sum())
    )
