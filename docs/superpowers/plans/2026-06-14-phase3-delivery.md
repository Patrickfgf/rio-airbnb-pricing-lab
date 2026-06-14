# Phase 3 — Delivery (predict · EDA · Dashboard · Validation · README) — Full Plan

> **STATUS: ACTIVE.** Supersedes the `2026-06-08-phase3-delivery.md` outline, which was written
> before the Phase-2 re-scope and still assumes a RevPAN-maximizer. This plan reflects the **price-
> positioning advisor** that Phase 2 actually shipped (no RevPAN frontier, no "expected RevPAN";
> occupancy is a caveated proxy). For agentic workers: REQUIRED SUB-SKILL
> `superpowers:subagent-driven-development`.

**Goal:** Turn the tested pipeline (`src/transform`) + model (`src/model`) into portfolio
deliverables: a per-listing prediction entry point, a narrated EDA notebook, a live Streamlit
dashboard, an honest ground-truth validation, an insight-first README, and a 1–2 page decision
report — then deploy.

**Architecture contract (spec §4):** the Streamlit app is a **thin UI** over `src/transform` +
`src/model`. **Zero business logic in the app layer** — every number it shows comes from a tested
`src/` function. Honesty is built in: the recommender renders a *range* + the occupancy-proxy caveat,
and `n_effective == 0` peer results are shown as "no comparable signal", not a fake 0.5 position.

**Tech additions:** Streamlit + Plotly (dashboard) · matplotlib (notebook figures) ·
jupyter/nbconvert (rendered notebook) · Streamlit Community Cloud (deploy).

---

## Step 0 — `predict()` price-space contract  ⭐ (the audit's one modelling finding)

The hedonic targets `log(price)`, so `model.predict(...)` is in log-BRL. The app needs a per-listing
**price** estimate, and `recommend_price` already documents that `hedonic_point` must be price-space.

- Expose `predict_listing_price(result, X_row, fe_row) -> float` (or a method on a fitted model
  wrapper) in `src/model/hedonic.py` that returns a **price-space** point estimate.
- Back-transform with **Duan's smearing estimator**: `price_hat = exp(log_pred) * mean(exp(resid))`,
  where `resid` are the in-sample OLS residuals. Naive `exp(mean log)` underestimates the mean by the
  Jensen gap; smearing is the standard non-parametric correction and needs no normality assumption.
  - Store the smearing factor on `HedonicResult` (computed once at fit time).
- TDD: assert (a) on synthetic log-normal data the smeared prediction is closer to the true mean
  price than naive `exp`; (b) the value is finite and positive; (c) feeding it into
  `recommend_price` produces a coherent anchor in BRL (no log/price unit mix).
- This closes the audit's CRITICAL→MEDIUM unit-contract finding end to end.

## Step 1 — Narrated EDA notebook (`notebooks/eda.ipynb`)

Story arc, heavy logic imported from `src/` (never redefined): market shape (price/occupancy-proxy
distributions, winsorization) → neighbourhood price map → seasonality curve (Réveillon/Carnaval
spikes, lower-bound caveat) → hedonic coefficient story (top price drivers; superhost coef is
**negative** — caveat, not a lever) → **the re-scope story** (why RevPAN-max is unidentifiable here:
the 73% circularity, occupancy≈reviews, no price variation). Enforce Restart & Run All clean, fixed
seeds, no hidden state; strip outputs before commit (nbstripout).

## Step 2 — Streamlit app: input + recommendation card (`app/streamlit_app.py`)

Host input form → `src/model` → a card showing the suggested price **range**, the peer percentile
position + label, top drivers, the demand note (lower-bound), and the **occupancy-proxy caveat**
inline. When `n_effective == 0`, show "not enough comparable listings" instead of a number.

## Step 3 — Streamlit app: market explore tab

Filterable Plotly views: price by neighbourhood, seasonality curve, occupancy-proxy benchmark
(own proxy vs `estimated_occupancy_l365d` agreement, with the shared-input warning surfaced).

## Step 4 — Ground-truth validation (`docs/ground_truth_validation.md`)  ⭐ AUTHOR NARRATIVE

Confront the author's real Superhost playbook (fast response, flexible policy, own photos, seasonal
pricing) with the drivers that emerge from Rio data. Framed honestly: the operated market was
**Pirenópolis-GO**, so this is *transferable principles vs the Rio market*, not "my own data".
**→ USER DECISION REQUIRED:** this is the author's personal story; cannot be fabricated.

## Step 5 — Insight-first README

Rewrite: story + key findings (top drivers, the re-scope lesson) on top; "how to run" below; badges
(CI, license); links to the live dashboard, the rendered notebook (nbviewer), and the caderno de bordo.

## Step 6 — Decision report (`reports/decision_report.md`)

1–2 pages, per-persona ("if you host an Entire/apt in Copacabana, position at X because Y"). Built
from the actual hedonic drivers + peer percentiles. No revenue guarantees (proxy caveat).

## Step 7 — Deploy (Streamlit Community Cloud)

Verify the live app loads and the recommender works end to end; add the link to the README.
**→ USER DECISION REQUIRED — deploy data strategy:** Streamlit Cloud has no persistent disk.
Option A: commit a small pre-computed curated parquet (listings + seasonality, NOT the 13M-row
calendar) as a release artifact and load it at startup (fast, but ships a data snapshot in git).
Option B: run the pipeline at app startup (no committed data, but slow cold start + needs the dump
reachable). Decide based on the curated file sizes.

## Step 8 — Final pass

Full `pytest` + Ruff green; notebook Restart & Run All; visual check of the deployed app.

---

## Open decisions (flagged for the user, resolved at their step)
1. **Recommender policy tuning** (Step 0/2): the default policy (50/50 blend, ±0.5·IQR band,
   0.33/0.66 thresholds) is now in `config.py` — author may tune before/after seeing real outputs.
2. **Ground-truth narrative** (Step 4): the author's Superhost story — user-authored.
3. **Deploy data strategy** (Step 7): committed parquet vs startup pipeline.

## Execution order
Step 0 (predict, unblocks the app) → Steps 1–3 (notebook + app, parallelizable) → Step 4 (user) →
Steps 5–6 (README + report, from real outputs) → Step 7 (user decision + deploy) → Step 8 (final).

## Spec coverage
§5 (recommender UI + honesty) · §7 (ground-truth validation) · §8 (README, notebook, dashboard,
decision report) · §10 (proxy caveat surfaced in UI/README).
