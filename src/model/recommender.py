"""Price-positioning recommendation. NOT a RevPAN optimizer (unidentifiable from this snapshot).

Composes the hedonic point estimate, the shrunk peer price distribution, and demand context into a
suggested price RANGE with the top drivers. The price-selection policy is the author's contribution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src import config


@dataclass(frozen=True)
class PriceRecommendation:
    low: float
    high: float
    anchor: float  # the central recommended price
    price_percentile: float  # current price's position among peers (0..1)
    position_label: str  # e.g. "below market" / "in line" / "above market"
    top_drivers: list[tuple[str, float]]
    demand_note: str
    caveats: tuple[str, ...]


_OCC_CAVEAT = (
    "Occupancy/RevPAN are reviews-driven estimates, not observed bookings; "
    "use this range as price positioning, not a guaranteed-revenue optimum."
)


def recommend_price(
    hedonic_point: float,
    peer_median: float,
    peer_iqr: float,
    price_percentile: float,
    top_drivers: list[tuple[str, float]],
    demand_note: str,
) -> PriceRecommendation:
    # Boundary validation: this is a system boundary (consumes hedonic + comparables + demand).
    # `hedonic_point` is expected in PRICE space (BRL), not log space — the caller exponentiates.
    if not (math.isfinite(hedonic_point) and math.isfinite(peer_median)):
        raise ValueError("hedonic_point and peer_median must be finite")
    if peer_median <= 0:
        raise ValueError(f"peer_median must be > 0, got {peer_median}")
    if peer_iqr < 0:
        raise ValueError(f"peer_iqr must be >= 0, got {peer_iqr}")
    if not 0.0 <= price_percentile <= 1.0:
        raise ValueError(f"price_percentile must be in [0, 1], got {price_percentile}")

    # ---- AUTHOR CONTRIBUTION (spec §11): the positioning policy (tunable via config) ----
    # Blend model & market by HEDONIC_MARKET_BLEND_WEIGHT; the hedonic adjR2 ~0.52 means neither
    # the model nor the peers alone is decisive, so the default weights them equally.
    w = config.HEDONIC_MARKET_BLEND_WEIGHT
    anchor = w * hedonic_point + (1 - w) * peer_median
    half_band = config.BAND_IQR_FRACTION * peer_iqr
    # floor `low` at a fraction of the anchor: never suggest <=0 or an absurd lowball
    low = max(anchor - half_band, config.ANCHOR_FLOOR_FRACTION * anchor)
    high = anchor + half_band
    if price_percentile < config.POSITION_BELOW_PCTL:
        position_label = "below market"
    elif price_percentile > config.POSITION_ABOVE_PCTL:
        position_label = "above market"
    else:
        position_label = "in line"
    # ------------------------------------------------------------------------------
    return PriceRecommendation(
        low=float(low),
        high=float(high),
        anchor=float(anchor),
        price_percentile=price_percentile,
        position_label=position_label,
        top_drivers=top_drivers[:5],
        demand_note=demand_note,
        caveats=(_OCC_CAVEAT,),
    )
