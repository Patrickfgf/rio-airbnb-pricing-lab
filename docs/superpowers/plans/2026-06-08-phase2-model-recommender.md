# Phase 2 — Hedonic Model + Recommender — Plan Outline

> **STATUS: OUTLINE.** This is the scope + task skeleton. It will be expanded into a full
> placeholder-free, step-by-step plan (like Phase 1) **at the Phase-2 checkpoint**, once the
> Phase-1 curated tables exist and their real distributions can be inspected. The concrete
> code (which features survive VIF, recommender thresholds, comparable-set size `k`) depends
> on the actual data and must not be invented before we can see it.
>
> **For agentic workers (after expansion):** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
>
> **Phase-1 data reality (confirmed by the 2026-06-11 smoke run on snapshot `2026-03-30`):**
> - **39,816** analyzable curated listings; **3,424,596** seasonality rows (listing × month × dow).
> - `listings.csv` **does** carry `estimated_occupancy_l365d` / `estimated_revenue_l365d` → use as the occupancy **benchmark** to validate the SF-model proxy.
> - ⚠️ **The Rio `calendar.csv` dump has NO `price` column** (only `listing_id,date,available,minimum_nights,maximum_nights`). So `median_cal_price` is NULL and there is **no per-date dynamic price** to mine. The price anchor is `listings.price`; calendar seasonality is a **pure availability (booked_rate)** signal. Any Phase-2 "dynamic price by date/season" idea must be re-scoped around this.

> **EDA findings (defensive EDA on curated snapshot `2026-03-30`, run 2026-06-12) — quantified, with decisions locked:**
> - **Grain & referential integrity are clean.** All three curated tables have unique keys (0 dup). `occupancy` ↔ `listings` is a **perfect 1:1**. Every curated listing has seasonality. **But 953 listings exist only in the calendar** (40,769 calendar listings vs 39,816 curated — the 953 were dropped by the curation filter for null price/neighbourhood/room_type), accounting for **80,052 rows = 2.34%** of seasonality. → **Always `INNER JOIN` seasonality↔listings** so these price-anchorless listings drop out.
> - 🔴 **Four curated columns are 100% NULL** — `instant_bookable`, `host_response_time`, `host_response_rate`, `host_acceptance_rate`. Verified against the raw dump: they ship **empty from Inside Airbnb Rio** (0 filled in 40,769 rows), so this is a **source reality, not a pipeline bug** (`host_is_superhost`, same `t/f` parser, is 99.9% filled). → **Remove them from the hedonic feature set** (they are dead weight; ideally drop from the curated schema).
> - **17.38% no-review cohort:** `review_scores_rating` / `reviews_per_month` / `first_review` / `last_review` are jointly null for the same ~6,920 listings with zero reviews (MNAR). → Encode as an explicit "no-history" category, **not** zero. Also `review_scores_rating` is ceiling-saturated (p25 4.77, median 4.92, on 0–5) → weak discriminator.
> - **Occupancy benchmark (proxy vs Inside Airbnb):** `occupancy_est` mean **0.307** (~112 nights/yr) vs `estimated_occupancy_l365d/365` mean **0.161** (~59 nights/yr). **Pearson 0.675**, MAE 0.169. The SF-model proxy **ranks listings well but has a ~2× level bias** (capped at 0.7 by design). → `validation.py` must **recalibrate** (scale/regress against the benchmark), not just report; for RevPAN, prefer `estimated_occupancy_l365d` as the occupancy ground-truth.
> - 🚩 **Seasonality `booked_rate` is confounded by calendar horizon.** The calendar is a **single forward snapshot** (`2026-03-30` → `2027-04-01`), so `MONTH(date)` ≈ one specific future horizon (Jan–Mar = 2027, the far horizon; May–Jun = next weeks). `unavail_rate` **rises with horizon** (0–30d 0.37; 30–90d 0.22; 90–180d 0.34; 180–270d 0.47; 270–365d 0.61). Real season (winter trough May/Jun, summer/Réveillon/Carnaval peak Dec–Mar) is **mixed with not-yet-opened far-future calendars**; the near-term (0–30d) bump shows the seasonal signal is *directionally real* but the far-horizon level is *inflated*. **Do not read `booked_rate` as literal occupancy.**
>
> **Decisions taken at this checkpoint (2026-06-12):**
> - **Target = RevPAN** (`listings.price` × *recalibrated* occupancy) is the central Phase-2 objective.
> - **Seasonality must be re-aggregated by real date/horizon, not by `MONTH(date)`**, before use — this supersedes the "month dummies" option in the §"Open questions" Season definition below.

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

1. **`features.py`** — build the model matrix from curated: `log_price` target; one-hot `room_type`/`property_type`; neighbourhood as fixed effect; numeric `accommodates`/`bedrooms`/`bathrooms_num`; flexibility proxy `min_nights`; `host_is_superhost`; no-review-cohort flag. Drop/flag leakage columns. ⚠️ **Do NOT use `instant_bookable`/`host_response_rate`/`host_acceptance_rate`/`host_response_time` — they are 100% NULL in this snapshot (see EDA findings above).** Test: shape, no NaN in target, dummies sum correctly.
2. **`hedonic.py`** — fit OLS `log_price ~ features + C(neighbourhood)`; return a tidy coefficient table (effect, std err, p-value); compute **VIF** and flag multicollinearity (> threshold). Test: known synthetic relationship recovers expected sign/magnitude; VIF flags a deliberately collinear pair.
3. **`comparables.py`** — given (neighbourhood, room_type, season, capacity), return the peer price distribution (median, IQR, n). Handle thin slices (fallback to wider neighbourhood/season when `n < k_min`). Test: peer filter correctness; fallback triggers on thin slice.
4. **`price_occupancy.py`** — estimate occupancy as a function of price *relative to comparables*; produce the RevPAN curve (price × occupancy). Test: monotonic occupancy↓ as relative price↑; RevPAN has an interior max on synthetic data.
5. **`recommender.py`** ⭐ **AUTHOR CONTRIBUTION** — the optimal-price selection logic (spec §11): how to weight the RevPAN curve to pick the recommended *range* (not a point), and how to surface the top drivers. Assistant scaffolds signature + comparables/hedonic wiring + tests; author writes the price-selection core (≈5–10 lines).
6. **`validation.py`** — when `estimated_occupancy_l365d` is present, compare the author's `occupancy_est` against it (MAE / correlation / bias) and emit a short agreement report. Test: perfect agreement → ~0 error; known offset → expected MAE.
7. **Full-suite + lint gate**, then **CHECKPOINT** before Phase 3.

---

## Open questions to resolve at checkpoint (need real data)

- **Season definition:** discrete bins (Réveillon / Carnaval / high / low) vs month dummies — decide from the calendar seasonality curve. ⚠️ **Resolved (2026-06-12): re-aggregate by real date/horizon first** (raw `MONTH(date)` is confounded with calendar horizon — see EDA findings). Build season bins from horizon-adjusted availability, not raw month means.
- **`k_min` comparable-set size** and the fallback ladder (neighbourhood → adjacent → city).
- **Which features survive VIF** (e.g. `accommodates` vs `beds` vs `bedrooms` likely collinear).
- **RevPAN occupancy curve form:** empirical bins vs a fitted monotonic function — depends on how clean the price↔occupancy relationship looks.

## Spec coverage targeted by Phase 2
§2 (RevPAN, three sub-questions) · §5 (recommender: comparables + hedonic + curve) · §6 (log-price, FE, VIF, association-not-cause) · §7 (ground-truth validation prep) · §11 (author's price-selection contribution).
