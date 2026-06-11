"""Occupancy estimation.

Two signals:
  1. calendar booked_rate  — direct but noisy (blocked != booked; stale calendars).
  2. reviews SF model      — indirect but robust (Inside Airbnb's own method).

The reviews-based San Francisco Model and a deterministic 50/50 baseline blend
are committed here so the pipeline runs end-to-end. The CHOICE of how to weight
the two signals is the author's contribution (spec §11) — refine estimate_occupancy
and its test when you want to encode that judgment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import SF_AVG_LENGTH_OF_STAY, SF_MAX_OCCUPANCY, SF_REVIEW_RATE


def sf_model_occupancy(reviews_ltm: pd.Series) -> pd.Series:
    """Estimate annual occupancy from reviews in the last 12 months (San Francisco Model).

    stays = reviews_ltm / review_rate ; nights = stays * avg_length_of_stay
    occupancy = min(nights / 365, max_cap). NaN reviews -> 0.
    """
    r = pd.to_numeric(reviews_ltm, errors="coerce").fillna(0.0)
    nights = (r / SF_REVIEW_RATE) * SF_AVG_LENGTH_OF_STAY
    occ = (nights / 365.0).clip(upper=SF_MAX_OCCUPANCY)
    return occ.astype("float64")


def estimate_occupancy(listings: pd.DataFrame, cal_booked_rate: pd.Series) -> pd.DataFrame:
    """Combine the reviews SF model with the calendar booked_rate into one occupancy.

    `cal_booked_rate` MUST be indexed by listing_id. Baseline = element-wise mean
    of the two signals, NaN-safe (a missing signal falls back to the other; if both
    are missing the result is 0.0), bounded to [0, SF_MAX_OCCUPANCY].

    ⭐ AUTHOR (spec §11): reweight this blend — e.g. trust reviews more when the
    calendar looks stale (very low availability), or shrink toward the market mean
    for listings with few reviews. Update test_estimate_occupancy_* accordingly.
    """
    sf = pd.Series(
        sf_model_occupancy(listings["number_of_reviews_ltm"]).to_numpy(),
        index=listings["listing_id"].to_numpy(),
    )
    cal = cal_booked_rate.reindex(sf.index)
    blended = np.nanmean(np.vstack([sf.to_numpy(), cal.to_numpy()]), axis=0)
    occ = pd.Series(blended, index=sf.index).fillna(0.0).clip(0.0, SF_MAX_OCCUPANCY)
    return pd.DataFrame({"listing_id": occ.index, "occupancy_est": occ.to_numpy()})
