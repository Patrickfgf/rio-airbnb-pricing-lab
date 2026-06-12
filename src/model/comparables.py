"""Shrunk peer PRICE distribution + percentile position for one listing.

Partial pooling (empirical-Bayes): a slice's price median is blended with its parent-tier median by
weight n/(n+m). Thin slices borrow strength continuously — no arbitrary k_min cliff. We benchmark
price (within-slice CV ~0.82), never RevPAN (CV ~1.28), per the 2026-06-12 findings.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import config


@dataclass(frozen=True)
class PeerPosition:
    tier_used: tuple[str, ...]
    n_effective: int
    shrunk_median: float
    iqr: float
    cv: float | None
    price_percentile: float


def _slice(listings: pd.DataFrame, target: pd.Series, cols: tuple[str, ...]) -> pd.DataFrame:
    mask = np.logical_and.reduce([listings[c] == target[c] for c in cols])
    return listings.loc[mask]


def peer_positioning(target: pd.Series, listings: pd.DataFrame) -> PeerPosition:
    m = config.SHRINKAGE_PRIOR_STRENGTH
    parent_median = float(listings["price"].median())
    for cols in config.COMPARABLE_TIERS:
        peers = _slice(listings, target, cols)
        n = len(peers)
        if n == 0:
            continue
        raw_median = float(peers["price"].median())
        w = n / (n + m)
        shrunk = w * raw_median + (1 - w) * parent_median
        q1, q3 = peers["price"].quantile([0.25, 0.75])
        cv = float(peers["price"].std() / peers["price"].mean()) if peers["price"].mean() else None
        pct = float((peers["price"] < target["price"]).mean())
        if n >= config.SHRINKAGE_PRIOR_STRENGTH or cols == config.COMPARABLE_TIERS[-1]:
            return PeerPosition(cols, n, shrunk, float(q3 - q1), cv, pct)
        parent_median = shrunk  # widen: this tier becomes the prior for the next
    return PeerPosition(("room_type",), 0, parent_median, 0.0, None, 0.5)
