"""Honest occupancy AGREEMENT report — explicitly NOT a validation against ground truth.

The 'benchmark' (estimated_occupancy_l365d) correlates 0.957 with reviews_ltm and the proxy also
consumes reviews_ltm, so their agreement is partly mechanical. We report it as agreement + caveats,
flag the 25.8% structural-zero cohort, and note the 0.699 censoring cap.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class OccupancyAgreement:
    pearson: float
    spearman: float
    mae: float
    bias: float
    structural_zero_frac: float
    censor_cap_hit_frac: float
    shared_input_warning: bool


def occupancy_agreement(
    proxy: pd.Series, benchmark: pd.Series, censor_cap: float = 0.699
) -> OccupancyAgreement:
    p, b = proxy.reset_index(drop=True), benchmark.reset_index(drop=True)
    return OccupancyAgreement(
        pearson=float(p.corr(b)),
        spearman=float(p.corr(b, method="spearman")),
        mae=float((p - b).abs().mean()),
        bias=float((p - b).mean()),
        structural_zero_frac=float((b == 0).mean()),
        censor_cap_hit_frac=float((b >= censor_cap - 1e-6).mean()),
        shared_input_warning=True,
    )
