"""Price-positioning recommendation. NOT a RevPAN optimizer (unidentifiable from this snapshot).

Composes the hedonic point estimate, the shrunk peer price distribution, and demand context into a
suggested price RANGE with the top drivers. The price-selection policy is the author's contribution.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    # ---- AUTHOR CONTRIBUTION (spec §11): the positioning policy (~5-10 lines) ----
    # Decide `anchor`, `low`, `high`, and `position_label` from hedonic_point, peer_median,
    # peer_iqr, and price_percentile. Questions to answer in code:
    #   - How do you weight the model's hedonic_point vs the peer_median for the anchor?
    #   - How wide is the band (use peer_iqr)? Symmetric, or skewed by percentile?
    #   - What percentile thresholds map to "below"/"in line"/"above market"?
    # DEFAULT POLICY (author: tune these). Blend model & market 50/50; the hedonic adjR2 ~0.52
    # means neither the model nor the peers alone is decisive, so weight them equally.
    anchor = 0.5 * hedonic_point + 0.5 * peer_median
    half_band = 0.5 * peer_iqr
    low = max(
        anchor - half_band, 0.5 * anchor
    )  # floor at 50% of anchor: never suggest <=0 or absurd
    high = anchor + half_band
    if price_percentile < 0.33:
        position_label = "below market"
    elif price_percentile > 0.66:
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
