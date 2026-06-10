# Phase 2 — Hedonic Model + Recommender — Plan Outline

> **STATUS: OUTLINE.** This is the scope + task skeleton. It will be expanded into a full
> placeholder-free, step-by-step plan (like Phase 1) **at the Phase-2 checkpoint**, once the
> Phase-1 curated tables exist and their real distributions can be inspected. The concrete
> code (which features survive VIF, recommender thresholds, comparable-set size `k`) depends
> on the actual data and must not be invented before we can see it.
>
> **For agentic workers (after expansion):** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** On top of the Phase-1 curated tables, build (1) an interpretable **hedonic price model** (log-price regression with neighbourhood fixed effects) and (2) the **rules + statistics recommender** that returns a suggested price *range*, expected occupancy, expected RevPAN, and the top drivers — all from pure, tested functions in `src/model/`.

**Architecture:** `src/model/` consumes curated parquet, returns coefficients + a recommender function. Knows nothing about the UI. Comparable-set logic (peers by neighbourhood × room_type × season) is separate from the hedonic adjustment, which is separate from the price×occupancy curve — three composable units, each independently testable.

**Tech Stack (additions):** statsmodels (OLS with fixed effects, returns interpretable coefficients + p-values) · scikit-learn (VIF helper, scaling) · numpy. Seeds fixed (`np.random.seed`, `random_state`).

> **Why statsmodels over scikit-learn LinearRegression for the hedonic model:** statsmodels gives
> coefficients, std errors, p-values, and R² out of the box — the spec needs *interpretable
> association* ("Superhost adds ~X%"), not prediction accuracy. Discarded alternative: a gradient
> boosting model — higher fit, but a black box that defeats the "explain why" requirement and the
> §9 "regras > ML" scope decision.

---

## File Structure (planned)

```
src/model/__init__.py
src/model/features.py        # curated -> model matrix (log price, dummies, FE, flexibility proxies)
src/model/hedonic.py         # fit log-price OLS w/ neighbourhood FE; VIF check; coef table
src/model/comparables.py     # peer set by neighbourhood x room_type x season; price distribution
src/model/price_occupancy.py # occupancy as f(relative price); RevPAN curve
src/model/recommender.py     # orchestrates comparables + hedonic + curve -> recommendation
src/model/validation.py      # compare own occupancy_est vs estimated_occupancy_l365d (benchmark)
tests/test_features.py
tests/test_hedonic.py
tests/test_comparables.py
tests/test_price_occupancy.py
tests/test_recommender.py
tests/test_validation.py
```

---

## Task Skeleton (to be expanded with full TDD steps at checkpoint)

1. **`features.py`** — build the model matrix from curated: `log_price` target; one-hot `room_type`/`property_type`; neighbourhood as fixed effect; numeric `accommodates`/`bedrooms`/`bathrooms_num`; flexibility proxies (`instant_bookable`, `min_nights`, `host_response_rate`); `host_is_superhost`. Drop/flag leakage columns. Test: shape, no NaN in target, dummies sum correctly.
2. **`hedonic.py`** — fit OLS `log_price ~ features + C(neighbourhood)`; return a tidy coefficient table (effect, std err, p-value); compute **VIF** and flag multicollinearity (> threshold). Test: known synthetic relationship recovers expected sign/magnitude; VIF flags a deliberately collinear pair.
3. **`comparables.py`** — given (neighbourhood, room_type, season, capacity), return the peer price distribution (median, IQR, n). Handle thin slices (fallback to wider neighbourhood/season when `n < k_min`). Test: peer filter correctness; fallback triggers on thin slice.
4. **`price_occupancy.py`** — estimate occupancy as a function of price *relative to comparables*; produce the RevPAN curve (price × occupancy). Test: monotonic occupancy↓ as relative price↑; RevPAN has an interior max on synthetic data.
5. **`recommender.py`** ⭐ **AUTHOR CONTRIBUTION** — the optimal-price selection logic (spec §11): how to weight the RevPAN curve to pick the recommended *range* (not a point), and how to surface the top drivers. Assistant scaffolds signature + comparables/hedonic wiring + tests; author writes the price-selection core (≈5–10 lines).
6. **`validation.py`** — when `estimated_occupancy_l365d` is present, compare the author's `occupancy_est` against it (MAE / correlation / bias) and emit a short agreement report. Test: perfect agreement → ~0 error; known offset → expected MAE.
7. **Full-suite + lint gate**, then **CHECKPOINT** before Phase 3.

---

## Open questions to resolve at checkpoint (need real data)

- **Season definition:** discrete bins (Réveillon / Carnaval / high / low) vs month dummies — decide from the calendar seasonality curve.
- **`k_min` comparable-set size** and the fallback ladder (neighbourhood → adjacent → city).
- **Which features survive VIF** (e.g. `accommodates` vs `beds` vs `bedrooms` likely collinear).
- **RevPAN occupancy curve form:** empirical bins vs a fitted monotonic function — depends on how clean the price↔occupancy relationship looks.

## Spec coverage targeted by Phase 2
§2 (RevPAN, three sub-questions) · §5 (recommender: comparables + hedonic + curve) · §6 (log-price, FE, VIF, association-not-cause) · §7 (ground-truth validation prep) · §11 (author's price-selection contribution).
