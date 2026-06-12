# Phase 2 — Price-Positioning Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Supersedes** the `2026-06-08-phase2-model-recommender.md` outline. That outline targeted a
> *RevPAN-maximizing* recommender; the 2026-06-12 EDA + adversarial verification proved that target is
> **not identifiable** from this snapshot (see "Why the re-scope" below). This plan is the expansion.

**Goal:** On top of the Phase-1 curated tables, build an interpretable **hedonic price model** and a
**price-positioning advisor** that tells a Rio host where their nightly price sits versus comparable
listings and the model's expectation, returns a suggested price *range* with the top drivers, and reports
demand/occupancy strictly as caveated context — never as a maximizable RevPAN optimum.

**Architecture:** `src/model/` consumes curated parquet and returns coefficients + a recommendation
function. Three composable, independently testable units — the hedonic fit (association of price with
attributes), the comparable-set positioning (shrunk peer price distribution), and the demand context
(seasonality indicator) — are wired by the author's recommender. The module knows nothing about any UI.

**Tech Stack (additions, already installed):** statsmodels 0.14 (OLS + fixed effects → interpretable
coefficients, std errors, p-values, R²) · scikit-learn 1.9 (VIF helper, scaling) · numpy. Seeds fixed
(`np.random.seed`, `random_state`).

---

## Why the re-scope (decisions locked at the 2026-06-12 checkpoint)

Verified deterministically on curated snapshot `2026-03-30` (`data/_eda_phase2.py`,
`data/_eda_phase2_verify.py`). Numbers are reproducible:

| Finding | Number | Consequence for the design |
|---|---|---|
| RevPAN is circular | `estimated_revenue_l365d == price × estimated_occupancy_l365d` for **73.4%** of listings (median ratio 1.0000) | RevPAN reconstructs its own input → **drop it as a target** |
| "Ground truth" is reviews | `corr(estimated_occupancy_l365d, reviews_ltm) = 0.957` | benchmark occupancy is a reviews estimate, **not observed bookings** |
| Price→occupancy signal is null | β(log_price_rel): **−0.086 → −0.008** (R² 0.075 → 0.916) once `reviews_ltm` is controlled | **no elasticity curve to maximize**; "interior max" is unidentified |
| Structural zeros | **25.8%** have `reviews_ltm==0` → bench/SF occupancy = 0 | occupancy is **zero-inflated**; never let `price×0` rows anchor a fit |
| Censoring | bench `p99 = max = 0.699` | high-demand tail is **truncated** |
| Peers aren't RevPAN-comparable | within-slice RevPAN CV (n≥30) = **1.28** | benchmark **price** (CV 0.82), not RevPAN |
| Capacity collinearity | `beds` net coef flips to **−0.025** (p~0), +0.002 adjR² | **drop `beds`**; VIF<3 missed this |
| `property_type` not redundant | within Entire home/apt, log_price spans 0.74 (loft→home), partial-F p=1e-13 | **keep collapsed** property_type (top-8 + Other) on significance |
| `superhost` sign | coef **−0.107** (p~0) | report as a **caveat**, not a quality premium |
| Rare neighbourhoods | **9 singletons, 34 cells n<5** of 155 | **pool** rare neighbourhoods before FE |
| All-NULL source cols | **100% null**: `instant_bookable`, `host_response_time`, `host_response_rate`, `host_acceptance_rate` | **drop** |
| Season signal | Réveillon **+9pp** (hits the 0.699 ceiling → lower bound), Carnaval **+3pp** (Feb 6-9), edge spikes are artifacts | **context only**, hard-filter `is_edge`, magnitudes are lower bounds |

**Net:** the hedonic price model is sound (adjR² ~0.52). Everything occupancy/RevPAN is demoted from
"target" to "caveated context". The author's contribution moves from "pick the RevPAN-max price" to
"the price-positioning rule".

---

## File Structure

```
src/model/__init__.py
src/model/features.py        # curated listings -> (X design matrix, y=log_price, FeatureMeta)
src/model/hedonic.py         # OLS log-price + neighbourhood FE; coef table; VIF; trivial baselines
src/model/comparables.py     # shrunk peer PRICE distribution + percentile position (hierarchical pooling)
src/model/demand_context.py  # seasonality indicator from the detrended calendar (is_edge filtered)
src/model/validation.py      # HONEST occupancy agreement report (proxy vs reviews-benchmark), not "validation"
src/model/recommender.py     # AUTHOR: positioning rule -> PriceRecommendation (range, position, drivers)
tests/test_features.py
tests/test_hedonic.py
tests/test_comparables.py
tests/test_demand_context.py
tests/test_validation.py
tests/test_recommender.py
```

Each file has one responsibility; files that change together live together. `recommender.py` is the only
unit that imports the others. No UI concerns anywhere.

**Shared constants** go in `src/config.py` (extend it): `MODEL_DROP_COLS`, `MODEL_TARGET_LEAK_COLS`,
`MIN_NEIGHBOURHOOD_N`, `COMPARABLE_TIERS`, `SHRINKAGE_PRIOR_STRENGTH`, `PROPERTY_TYPE_TOP_K`.

**Gotchas (carry forward from Phase 1):** run tests via `./.venv/Scripts/python.exe -m pytest`. A
formatter hook runs `ruff --fix` on every `.py` save → it **removes unused imports (F401)**, so add an
import and its use together, and re-Read a file before re-editing it. `ruff` `line-length = 100`. DuckDB
emits dates as `datetime64[us]`; pandera `coerce=True` normalizes. Curated parquet lives in
`data/curated/` (gitignored); regenerate with `python -m src.pipeline` if missing.

---

## Task 0: Extend config with model constants

**Files:**
- Modify: `src/config.py` (append)

- [ ] **Step 1: Add constants, then commit (no test — pure config consumed by later tasks).**

```python
# --- Phase 2: model feature governance (see docs/.../2026-06-12-phase2-positioning-advisor.md) ---
# Columns excluded from the hedonic feature matrix.
MODEL_DROP_ALL_NULL = (  # 100% null in the Rio 2026-03-30 dump (source reality)
    "instant_bookable", "host_response_time", "host_response_rate", "host_acceptance_rate",
)
MODEL_DROP_LEAKAGE = (  # outcomes/forward-looking — never predict price with these
    "availability_365", "estimated_occupancy_l365d", "estimated_revenue_l365d",
)
MODEL_DROP_COLLINEAR = ("beds",)  # net coef sign-flips (-0.025, p~0); +0.002 adjR2 only
MIN_NEIGHBOURHOOD_N = 30          # neighbourhoods with fewer listings are pooled to "Other"
PROPERTY_TYPE_TOP_K = 8           # keep top-K property_type levels, collapse the rest to "Other"
# Comparable-set hierarchy, widest-last; each tier is a tuple of grouping columns.
COMPARABLE_TIERS = (
    ("neighbourhood", "room_type", "cap_bucket"),
    ("neighbourhood", "room_type"),
    ("room_type", "cap_bucket"),
    ("room_type",),
)
SHRINKAGE_PRIOR_STRENGTH = 30.0   # pseudo-count m: slice mean shrinks toward parent by n/(n+m)
CAP_BUCKET_EDGES = (0, 2, 4, 6, 999)        # accommodates -> 1-2, 3-4, 5-6, 7+
CAP_BUCKET_LABELS = ("1-2", "3-4", "5-6", "7+")
```

```bash
git add src/config.py && git commit -m "feat: add Phase-2 model feature-governance constants"
```

---

## Task 1: `features.py` — curated → design matrix

**Files:**
- Create: `src/model/__init__.py` (empty), `src/model/features.py`
- Test: `tests/test_features.py`

Build `y = log(price)` and a design matrix `X` with: numeric `accommodates, bedrooms, bathrooms_num,
min_nights`; one-hot `room_type` (Hotel room folded into Entire home/apt — n=13); collapsed
`property_type` (top-8 + Other); `host_is_superhost` (0/1, NaN→0 with a missing flag); `no_review_history`
flag; and a pooled `neighbourhood` column (rare levels → "Other") returned **as a categorical for the
hedonic to expand into fixed effects**. Drop every column in `MODEL_DROP_*`. `cap_bucket` is added for the
comparables step.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_features.py
import numpy as np
import pandas as pd
import pytest
from src.model.features import build_model_matrix, FeatureMeta

@pytest.fixture
def toy_listings():
    n = 60
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "listing_id": range(n),
        "price": rng.uniform(100, 2000, n),
        "neighbourhood": ["Copacabana"] * 40 + ["RareHood"] * 1 + ["Ipanema"] * 19,
        "room_type": ["Entire home/apt"] * 50 + ["Private room"] * 9 + ["Hotel room"] * 1,
        "property_type": (["Entire rental unit"] * 50 + ["Entire loft"] * 5
                          + [f"Exotic {i}" for i in range(5)]),
        "accommodates": rng.integers(1, 9, n),
        "bedrooms": rng.integers(1, 4, n),
        "beds": rng.integers(1, 5, n),
        "bathrooms_num": rng.uniform(1, 3, n),
        "min_nights": rng.integers(1, 30, n),
        "host_is_superhost": rng.integers(0, 2, n).astype(float),
        "number_of_reviews": [0] * 12 + list(rng.integers(1, 50, n - 12)),
        "number_of_reviews_ltm": rng.integers(0, 20, n),
        "availability_365": rng.integers(0, 365, n),
        "estimated_occupancy_l365d": rng.integers(0, 200, n),
        "estimated_revenue_l365d": rng.uniform(0, 1e5, n),
        "instant_bookable": [pd.NA] * n,
    })

def test_target_is_log_price_no_nan(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert (y > 0).all() and not y.isna().any()
    assert np.allclose(np.exp(y.iloc[0]), toy_listings["price"].iloc[0])

def test_leakage_and_collinear_columns_absent(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    banned = {"beds", "availability_365", "estimated_occupancy_l365d",
              "estimated_revenue_l365d", "instant_bookable", "price"}
    assert banned.isdisjoint(X.columns)

def test_rare_neighbourhood_pooled(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert "RareHood" not in set(meta.neighbourhood)
    assert "Other" in set(meta.neighbourhood)

def test_hotel_folded_and_no_review_flag(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    assert "room_type_Hotel room" not in X.columns        # folded into baseline/Entire
    assert X["no_review_history"].sum() == 12             # 12 zero-review rows

def test_property_type_collapsed(toy_listings):
    X, y, meta = build_model_matrix(toy_listings)
    pt_cols = [c for c in X.columns if c.startswith("property_type_")]
    assert any(c.endswith("Other") for c in pt_cols)
```

- [ ] **Step 2: Run → expect FAIL** (`ModuleNotFoundError: src.model.features`).
  `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`

- [ ] **Step 3: Implement `src/model/features.py`**

```python
"""Curated listings -> (X design matrix, y=log_price, FeatureMeta). Pure function, no I/O.

Encodes the 2026-06-12 feature-governance decisions: drop all-null + leakage + collinear cols,
fold the n=13 Hotel room into Entire home/apt, collapse property_type to top-K, pool rare
neighbourhoods, and expose neighbourhood as a categorical for fixed-effects expansion in hedonic.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import config


@dataclass(frozen=True)
class FeatureMeta:
    neighbourhood: pd.Series          # pooled categorical, aligned to X.index (for C(neighbourhood) FE)
    dropped: tuple[str, ...]
    n_rows: int


def _collapse_top_k(s: pd.Series, k: int) -> pd.Series:
    top = s.value_counts().nlargest(k).index
    return s.where(s.isin(top), "Other")


def build_model_matrix(listings: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, FeatureMeta]:
    df = listings.loc[listings["price"] > 0].reset_index(drop=True)
    y = np.log(df["price"].astype(float)).rename("log_price")

    room = df["room_type"].replace({"Hotel room": "Entire home/apt"})
    prop = _collapse_top_k(df["property_type"].astype("string").fillna("Other"),
                           config.PROPERTY_TYPE_TOP_K)
    nb_counts = df["neighbourhood"].value_counts()
    rare = nb_counts[nb_counts < config.MIN_NEIGHBOURHOOD_N].index
    neighbourhood = df["neighbourhood"].where(~df["neighbourhood"].isin(rare), "Other")

    numeric = pd.DataFrame({
        "accommodates": pd.to_numeric(df["accommodates"], errors="coerce"),
        "bedrooms": pd.to_numeric(df["bedrooms"], errors="coerce"),
        "bathrooms_num": pd.to_numeric(df["bathrooms_num"], errors="coerce"),
        "min_nights": pd.to_numeric(df["min_nights"], errors="coerce"),
    })
    numeric = numeric.fillna(numeric.median(numeric_only=True))

    superhost = pd.to_numeric(df["host_is_superhost"], errors="coerce")
    no_review = (pd.to_numeric(df["number_of_reviews"], errors="coerce").fillna(0) == 0).astype(int)
    cap_bucket = pd.cut(numeric["accommodates"], bins=config.CAP_BUCKET_EDGES,
                        labels=config.CAP_BUCKET_LABELS)

    X = pd.concat([
        numeric,
        pd.get_dummies(room, prefix="room_type", drop_first=True),
        pd.get_dummies(prop, prefix="property_type", drop_first=True),
        superhost.fillna(0).rename("host_is_superhost"),
        superhost.isna().astype(int).rename("superhost_missing"),
        no_review.rename("no_review_history"),
        cap_bucket.rename("cap_bucket"),
    ], axis=1)

    dropped = config.MODEL_DROP_ALL_NULL + config.MODEL_DROP_LEAKAGE + config.MODEL_DROP_COLLINEAR
    return X, y, FeatureMeta(neighbourhood=neighbourhood, dropped=dropped, n_rows=len(df))
```

- [ ] **Step 4: Run → expect PASS.** `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
- [ ] **Step 5: Commit.** `git add src/model/__init__.py src/model/features.py tests/test_features.py && git commit -m "feat: model feature matrix (log-price target, leakage-blocked, pooled FE)"`

---

## Task 2: `hedonic.py` — OLS log-price + FE, VIF, trivial baselines

**Files:**
- Create: `src/model/hedonic.py`
- Test: `tests/test_hedonic.py`

Fit `log_price ~ X + C(neighbourhood)` via statsmodels OLS; return a tidy coefficient table
(`effect, std_err, p_value, ci_low, ci_high`), `adj_r2`, a VIF table, and the **trivial baseline**
(global-median and neighbourhood-median MAE) so we can prove the model beats it before trusting it.
`cap_bucket` is excluded from the regression (it's for comparables, not price).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hedonic.py
import numpy as np
import pandas as pd
from src.model.hedonic import fit_hedonic, compute_vif

def test_recovers_known_relationship():
    rng = np.random.default_rng(1)
    n = 500
    accommodates = rng.integers(1, 8, n)
    nb = rng.choice(["A", "B"], n)
    y = 5.0 + 0.25 * accommodates + (nb == "B") * 0.4 + rng.normal(0, 0.1, n)
    X = pd.DataFrame({"accommodates": accommodates})
    res = fit_hedonic(X, pd.Series(y, name="log_price"), pd.Series(nb, name="nb"))
    assert abs(res.coefs.loc["accommodates", "effect"] - 0.25) < 0.05
    assert res.coefs.loc["accommodates", "p_value"] < 0.01
    assert res.adj_r2 > 0.9

def test_beats_trivial_baseline():
    rng = np.random.default_rng(2)
    n = 400
    acc = rng.integers(1, 8, n)
    y = 5 + 0.3 * acc + rng.normal(0, 0.2, n)
    res = fit_hedonic(pd.DataFrame({"accommodates": acc}),
                      pd.Series(y, name="log_price"),
                      pd.Series(["A"] * n, name="nb"))
    assert res.model_mae < res.baseline_median_mae

def test_vif_flags_collinear_pair():
    rng = np.random.default_rng(3)
    a = rng.normal(0, 1, 300)
    X = pd.DataFrame({"a": a, "a_copy": a + rng.normal(0, 1e-3, 300), "b": rng.normal(0, 1, 300)})
    vif = compute_vif(X)
    assert vif.loc["a"] > 10 and vif.loc["b"] < 5
```

- [ ] **Step 2: Run → expect FAIL.** `./.venv/Scripts/python.exe -m pytest tests/test_hedonic.py -v`

- [ ] **Step 3: Implement `src/model/hedonic.py`**

```python
"""Interpretable hedonic price model: OLS log_price ~ features + neighbourhood fixed effects.

Returns coefficients with std errors / p-values / CIs (association, NOT causation), adjusted R²,
a VIF table, and trivial baselines so the model must out-predict median-by-neighbourhood before use.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.preprocessing import OneHotEncoder


@dataclass(frozen=True)
class HedonicResult:
    coefs: pd.DataFrame          # index=feature, cols: effect, std_err, p_value, ci_low, ci_high
    adj_r2: float
    vif: pd.Series
    model_mae: float
    baseline_median_mae: float
    baseline_nb_median_mae: float


def compute_vif(X: pd.DataFrame) -> pd.Series:
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    Xc = sm.add_constant(X.astype(float), has_constant="add")
    vals = [variance_inflation_factor(Xc.to_numpy(), i) for i in range(Xc.shape[1])]
    return pd.Series(vals, index=Xc.columns).drop("const")


def fit_hedonic(X: pd.DataFrame, y: pd.Series, neighbourhood: pd.Series) -> HedonicResult:
    Xnum = X.drop(columns=[c for c in ("cap_bucket",) if c in X.columns]).astype(float)
    enc = OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")
    fe = enc.fit_transform(neighbourhood.to_frame())
    fe_df = pd.DataFrame(fe, columns=enc.get_feature_names_out(["nb"]), index=Xnum.index)
    design = sm.add_constant(pd.concat([Xnum, fe_df], axis=1), has_constant="add")

    model = sm.OLS(y.to_numpy(), design.to_numpy()).fit()
    ci = model.conf_int()
    coefs = pd.DataFrame({
        "effect": model.params, "std_err": model.bse, "p_value": model.pvalues,
        "ci_low": ci[:, 0], "ci_high": ci[:, 1],
    }, index=design.columns).drop("const")
    coefs = coefs.loc[~coefs.index.str.startswith("nb_")]   # hide FE nuisance rows from the table

    pred = model.predict(design.to_numpy())
    model_mae = float(np.abs(y.to_numpy() - pred).mean())
    base_median = float(np.abs(y - y.median()).mean())
    nb_med = y.groupby(neighbourhood.to_numpy()).transform("median")
    base_nb = float(np.abs(y - nb_med).mean())
    return HedonicResult(coefs, float(model.rsquared_adj), compute_vif(Xnum),
                         model_mae, base_median, base_nb)
```

- [ ] **Step 4: Run → expect PASS.** `./.venv/Scripts/python.exe -m pytest tests/test_hedonic.py -v`
- [ ] **Step 5: Commit.** `git add src/model/hedonic.py tests/test_hedonic.py && git commit -m "feat: hedonic OLS with neighbourhood FE, VIF, and trivial-baseline guard"`

---

## Task 3: `comparables.py` — shrunk peer price positioning

**Files:**
- Create: `src/model/comparables.py`
- Test: `tests/test_comparables.py`

Return the peer **price** distribution and the listing's percentile, using **partial pooling**
(empirical-Bayes shrinkage `n/(n+m)` toward the parent tier) instead of a hard `k_min` cliff. Walk
`COMPARABLE_TIERS` to find the narrowest tier with the most precision; report `tier_used`,
`n_effective`, `shrunk_median`, `iqr`, `cv`, and `price_percentile`. Benchmark **price** (CV 0.82),
never RevPAN (CV 1.28).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_comparables.py
import numpy as np
import pandas as pd
from src.model.comparables import peer_positioning

def _market(n_dense=200):
    rng = np.random.default_rng(7)
    dense = pd.DataFrame({
        "listing_id": range(n_dense),
        "price": rng.normal(500, 100, n_dense).clip(50),
        "neighbourhood": "Copacabana", "room_type": "Entire home/apt", "cap_bucket": "3-4",
    })
    thin = pd.DataFrame({  # 2-listing slice -> must shrink toward parent
        "listing_id": [9001, 9002], "price": [3000.0, 50.0],
        "neighbourhood": "Copacabana", "room_type": "Entire home/apt", "cap_bucket": "7+",
    })
    return pd.concat([dense, thin], ignore_index=True)

def test_percentile_in_dense_slice():
    m = _market()
    target = m.iloc[0]
    out = peer_positioning(target, m)
    assert 0.0 <= out.price_percentile <= 1.0
    assert out.tier_used == ("neighbourhood", "room_type", "cap_bucket")
    assert out.n_effective >= 100

def test_thin_slice_shrinks_toward_parent():
    m = _market()
    thin_target = m[m["listing_id"] == 9001].iloc[0]   # price 3000 in a 2-row slice
    out = peer_positioning(thin_target, m)
    # raw slice median would be 1525; shrunk toward the ~500 parent median must be far lower
    assert out.shrunk_median < 1200
    assert out.cv is not None
```

- [ ] **Step 2: Run → expect FAIL.** `./.venv/Scripts/python.exe -m pytest tests/test_comparables.py -v`

- [ ] **Step 3: Implement `src/model/comparables.py`**

```python
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
        parent_median = shrunk   # widen: this tier becomes the prior for the next
    return PeerPosition(("room_type",), 0, parent_median, 0.0, None, 0.5)
```

- [ ] **Step 4: Run → expect PASS.** `./.venv/Scripts/python.exe -m pytest tests/test_comparables.py -v`
- [ ] **Step 5: Commit.** `git add src/model/comparables.py tests/test_comparables.py && git commit -m "feat: shrunk peer price positioning (partial pooling, no k_min cliff)"`

---

## Task 4: `demand_context.py` — seasonality indicator

**Files:**
- Create: `src/model/demand_context.py`
- Test: `tests/test_demand_context.py`

From the detrended parquet, return the top non-edge demand dates and named events (Réveillon, Carnaval)
with `event_uplift` flagged as a **lower bound** (right-censored). **Hard-filter `is_edge==True`** so
snapshot artifacts (uplift up to +0.22) never surface as demand.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_demand_context.py
import pandas as pd
from src.model.demand_context import seasonal_context

def _detrended():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-03-30", "2026-12-31", "2027-02-07", "2026-07-15"]),
        "dow": [0, 4, 6, 2], "horizon_days": [0, 276, 314, 107],
        "unavail_rate": [0.63, 0.67, 0.60, 0.30], "baseline": [0.45, 0.58, 0.57, 0.30],
        "event_uplift": [0.22, 0.093, 0.027, 0.0], "is_edge": [True, False, False, False],
    })

def test_edge_dates_excluded():
    ctx = seasonal_context(_detrended())
    assert pd.Timestamp("2026-03-30") not in set(ctx.top_dates["date"])

def test_known_events_surface_with_lower_bound_flag():
    ctx = seasonal_context(_detrended())
    assert "Réveillon" in ctx.events and "Carnaval" in ctx.events
    assert ctx.magnitudes_are_lower_bounds is True
```

- [ ] **Step 2: Run → expect FAIL.** `./.venv/Scripts/python.exe -m pytest tests/test_demand_context.py -v`

- [ ] **Step 3: Implement `src/model/demand_context.py`**

```python
"""Seasonality CONTEXT from the horizon-detrended calendar — an indicator, not a price modulator.

is_edge rows (near-snapshot artifacts, uplift up to +0.22) are hard-filtered out. event_uplift is a
LOWER BOUND: far-horizon peaks (Réveillon) hit the 0.699 availability ceiling, so the true premium is
larger. A future multi-snapshot pull would de-saturate these (path to a v2 seasonal model).
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    return md >= lo if lo[0] == 12 else (md >= lo and md <= hi)


def seasonal_context(detrended: pd.DataFrame, top_n: int = 10) -> DemandContext:
    clean = detrended.loc[~detrended["is_edge"]].copy()
    top = clean.nlargest(top_n, "event_uplift")[["date", "dow", "horizon_days", "event_uplift"]]
    events: dict[str, float] = {}
    for name, (lo, hi) in _EVENT_WINDOWS.items():
        hit = clean[clean["date"].apply(lambda d: _in_window(d, lo, hi))]
        if not hit.empty:
            events[name] = float(hit["event_uplift"].max())
    return DemandContext(top.reset_index(drop=True), events,
                         dropped_edge=int(detrended["is_edge"].sum()))
```

- [ ] **Step 4: Run → expect PASS.** `./.venv/Scripts/python.exe -m pytest tests/test_demand_context.py -v`
- [ ] **Step 5: Commit.** `git add src/model/demand_context.py tests/test_demand_context.py && git commit -m "feat: seasonal demand context (edge-filtered, lower-bound magnitudes)"`

---

## Task 5: `validation.py` — honest occupancy agreement

**Files:**
- Create: `src/model/validation.py`
- Test: `tests/test_validation.py`

Compare the author's `occupancy_est` proxy against the reviews-benchmark **without calling either a
ground truth**. Report Pearson/Spearman/MAE/bias, the structural-zero fraction, the censoring cap, and a
**shared-input warning** (both consume `reviews_ltm`, so agreement is partly mechanical).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_validation.py
import numpy as np
import pandas as pd
from src.model.validation import occupancy_agreement

def test_perfect_agreement_zero_error():
    x = pd.Series(np.linspace(0.05, 0.6, 100))
    rep = occupancy_agreement(proxy=x, benchmark=x.copy())
    assert rep.mae < 1e-9 and abs(rep.pearson - 1.0) < 1e-9

def test_known_offset_and_structural_zeros():
    proxy = pd.Series([0.3] * 80 + [0.0] * 20)
    bench = pd.Series([0.2] * 80 + [0.0] * 20)
    rep = occupancy_agreement(proxy, bench)
    assert abs(rep.bias - 0.08) < 1e-6           # mean(proxy-bench) over all 100
    assert abs(rep.structural_zero_frac - 0.20) < 1e-6
    assert rep.shared_input_warning is True
```

- [ ] **Step 2: Run → expect FAIL.** `./.venv/Scripts/python.exe -m pytest tests/test_validation.py -v`

- [ ] **Step 3: Implement `src/model/validation.py`**

```python
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


def occupancy_agreement(proxy: pd.Series, benchmark: pd.Series,
                        censor_cap: float = 0.699) -> OccupancyAgreement:
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
```

- [ ] **Step 4: Run → expect PASS.** `./.venv/Scripts/python.exe -m pytest tests/test_validation.py -v`
- [ ] **Step 5: Commit.** `git add src/model/validation.py tests/test_validation.py && git commit -m "feat: honest occupancy agreement report (shared-input + structural-zero caveats)"`

---

## Task 6: `recommender.py` ⭐ AUTHOR CONTRIBUTION

**Files:**
- Create: `src/model/recommender.py`
- Test: `tests/test_recommender.py`

The assistant scaffolds the dataclass, the wiring of hedonic + comparables + demand context, and the
structural tests. **The author writes the positioning core (~5–10 lines):** given the hedonic-predicted
price and the shrunk peer distribution, decide the recommended **range** (which percentile band to target,
how aggressive, how to weight hedonic vs peers) and assemble the top drivers. No RevPAN maximization —
the recommendation is a *position*, not an optimum.

- [ ] **Step 1: Write the failing structural tests** (these constrain the contract, not the author's policy)

```python
# tests/test_recommender.py
import numpy as np
import pandas as pd
from src.model.recommender import recommend_price, PriceRecommendation

def test_returns_valid_range_and_drivers(monkeypatch):
    rec = recommend_price(
        hedonic_point=600.0, peer_median=500.0, peer_iqr=200.0, price_percentile=0.8,
        top_drivers=[("accommodates", 0.25), ("neighbourhood=Ipanema", 0.4)],
        demand_note="Réveillon ~+9pp (lower bound)",
    )
    assert isinstance(rec, PriceRecommendation)
    assert rec.low < rec.high
    assert rec.low > 0
    assert len(rec.top_drivers) >= 1
    assert "lower bound" in rec.demand_note
    assert rec.caveats          # must carry the occupancy caveat

def test_no_revpan_optimum_field():
    rec = recommend_price(hedonic_point=600.0, peer_median=500.0, peer_iqr=200.0,
                          price_percentile=0.5, top_drivers=[], demand_note="")
    assert not hasattr(rec, "revpan_max_price")   # we deliberately do NOT expose this
```

- [ ] **Step 2: Run → expect FAIL.** `./.venv/Scripts/python.exe -m pytest tests/test_recommender.py -v`

- [ ] **Step 3: Scaffold `src/model/recommender.py` (assistant) + AUTHOR fills the core**

```python
"""Price-positioning recommendation. NOT a RevPAN optimizer (unidentifiable from this snapshot).

Composes the hedonic point estimate, the shrunk peer price distribution, and demand context into a
suggested price RANGE with the top drivers. The price-selection policy is the author's contribution.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceRecommendation:
    low: float
    high: float
    anchor: float                      # the central recommended price
    price_percentile: float            # current price's position among peers (0..1)
    position_label: str                # e.g. "below market" / "in line" / "above market"
    top_drivers: list[tuple[str, float]]
    demand_note: str
    caveats: tuple[str, ...]


_OCC_CAVEAT = ("Occupancy/RevPAN are reviews-driven estimates, not observed bookings; "
               "use this range as price positioning, not a guaranteed-revenue optimum.")


def recommend_price(hedonic_point: float, peer_median: float, peer_iqr: float,
                    price_percentile: float, top_drivers: list[tuple[str, float]],
                    demand_note: str) -> PriceRecommendation:
    # ---- AUTHOR CONTRIBUTION (spec §11): the positioning policy (~5-10 lines) ----
    # Decide `anchor`, `low`, `high`, and `position_label` from hedonic_point, peer_median,
    # peer_iqr, and price_percentile. Questions to answer in code:
    #   - How do you weight the model's hedonic_point vs the peer_median for the anchor?
    #   - How wide is the band (use peer_iqr)? Symmetric, or skewed by percentile?
    #   - What percentile thresholds map to "below"/"in line"/"above market"?
    anchor = ...        # e.g. 0.5 * hedonic_point + 0.5 * peer_median
    low = ...           # e.g. anchor - 0.5 * peer_iqr
    high = ...          # e.g. anchor + 0.5 * peer_iqr
    position_label = ...
    # ------------------------------------------------------------------------------
    return PriceRecommendation(
        low=float(low), high=float(high), anchor=float(anchor),
        price_percentile=price_percentile, position_label=position_label,
        top_drivers=top_drivers[:5], demand_note=demand_note, caveats=(_OCC_CAVEAT,),
    )
```

- [ ] **Step 4: Run → expect PASS once the author fills the `...` lines.**
  `./.venv/Scripts/python.exe -m pytest tests/test_recommender.py -v`
- [ ] **Step 5: Commit.** `git add src/model/recommender.py tests/test_recommender.py && git commit -m "feat: price-positioning recommender (author policy core)"`

---

## Task 7: Full-suite + lint gate, then CHECKPOINT

- [ ] **Step 1: Full suite.** `./.venv/Scripts/python.exe -m pytest` → expect all pass, coverage not regressed below 90%.
- [ ] **Step 2: Lint.** `./.venv/Scripts/python.exe -m ruff check src tests` → expect clean.
- [ ] **Step 3: Ultracode review.** Dispatch adversarial reviewers over `src/model/` (hedonic correctness, leakage re-check, recommender policy sanity) before Phase 3.
- [ ] **Step 4: Commit any fixes; update the project memory + plan status; CHECKPOINT before Phase 3 (delivery).**

---

## Self-Review (run against the spec + the locked decisions)

- **Spec coverage:** §2 (re-scoped to positioning, RevPAN demoted to caveated context — Tasks 3/5/6) ·
  §5 (recommender composes comparables + hedonic + context — Task 6) · §6 (log-price, FE, VIF,
  association-not-cause — Tasks 1/2) · §7 (occupancy agreement prep — Task 5) · §11 (author's
  price-selection core — Task 6). The original §2 "RevPAN three sub-questions" is **intentionally
  not built** as an optimizer; the re-scope rationale documents why.
- **Leakage:** `beds`, `availability_365`, `estimated_occupancy_l365d`, `estimated_revenue_l365d`, and the
  4 all-null cols are blocked in Task 0/1 and asserted absent in `test_leakage_and_collinear_columns_absent`.
- **Type consistency:** `FeatureMeta.neighbourhood` (Task 1) feeds `fit_hedonic(..., neighbourhood)` (Task 2);
  `PeerPosition.shrunk_median`/`iqr`/`price_percentile` (Task 3) feed `recommend_price(...)` (Task 6);
  `DemandContext.events` (Task 4) feeds the `demand_note`. Names checked end-to-end.
- **Open authored decisions (not placeholders — deliberate §11 contribution):** the `recommend_price`
  core (Task 6) and, if revisited, the `estimate_occupancy` blend in `src/transform/occupancy.py`.
