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
    pearson: float | None  # None when either series is constant (the structural-zero cohort)
    spearman: float | None
    mae: float
    bias: float
    structural_zero_frac: float
    proxy_cap_hit_frac: float  # the pipeline censors the PROXY at the cap, so report it too
    benchmark_cap_hit_frac: float
    shared_input_warning: bool


def occupancy_agreement(
    proxy: pd.Series, benchmark: pd.Series, censor_cap: float = 0.699
) -> OccupancyAgreement:
    if len(proxy) != len(benchmark):
        raise ValueError(f"proxy/benchmark length mismatch: {len(proxy)} != {len(benchmark)}")
    if len(proxy) == 0:
        raise ValueError("occupancy_agreement requires non-empty inputs")
    p, b = proxy.reset_index(drop=True), benchmark.reset_index(drop=True)
    # Correlation is undefined for a constant series (e.g. the all-zero structural cohort); report
    # None rather than a NaN that reads like a real coefficient (and avoids ConstantInputWarning).
    degenerate = p.nunique(dropna=True) <= 1 or b.nunique(dropna=True) <= 1
    pearson = None if degenerate else float(p.corr(b))
    spearman = None if degenerate else float(p.corr(b, method="spearman"))
    return OccupancyAgreement(
        pearson=pearson,
        spearman=spearman,
        mae=float((p - b).abs().mean()),
        bias=float((p - b).mean()),
        structural_zero_frac=float((b == 0).mean()),
        proxy_cap_hit_frac=float((p >= censor_cap - 1e-6).mean()),
        benchmark_cap_hit_frac=float((b >= censor_cap - 1e-6).mean()),
        shared_input_warning=True,
    )
