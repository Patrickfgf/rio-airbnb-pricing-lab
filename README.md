# Rio Airbnb Pricing Lab

[![CI](https://github.com/Patrickfgf/rio-airbnb-pricing-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Patrickfgf/rio-airbnb-pricing-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

An **honest price-positioning advisor** for Airbnb hosts in Rio de Janeiro, built on open
[Inside Airbnb](https://insideairbnb.com/) data. You describe a listing; it returns a price **range**
— where comparable listings sit and what a hedonic model expects — never a single guaranteed number.

> **Why "positioning" and not "revenue maximization"?** The original plan was a RevPAN (revenue per
> available night) maximizer. The Phase-2 EDA killed it: occupancy is estimated *from review counts*,
> RevPAN is then *price × that estimate*, and there's no within-listing price variation in a single
> snapshot — so a "revenue-optimal price" is **unidentifiable** here. Chasing it would have produced
> confident, circular nonsense. The honest product is positioning: where does this listing sit, and
> what moves its price? That re-scope **is** the headline finding.

## Key findings (from 39,816 real listings, snapshot 2026-03-30)

- **Physical space sets the price, not amenities.** The biggest hedonic levers are **bathrooms
  (~+15%)** and **bedrooms (~+14%)**; room type dominates the downside (**private room ~−24%**,
  **shared room ~−69%** vs an entire place).
- **Being a Superhost is *not* a price lever.** The Superhost coefficient is **negative (~−10%)** —
  Superhosts sit slightly *below* comparable non-Superhosts. The badge drives occupancy and
  reputation, not a price premium. (The author's own Superhost experience confirms this — see the
  [ground-truth validation](docs/ground_truth_validation.md).)
- **Demand is datable.** **Réveillon** and **Carnaval** are the dated peaks; the detrended-calendar
  magnitudes are **lower bounds** (far-horizon peaks hit a measurement ceiling).
- **The model is honest about its limits.** Adjusted **R² ≈ 0.52**, so a recommendation **blends the
  model 50/50 with live peer prices** — neither alone is decisive.

## Honest by design

This is the whole point of the project, enforced in tested `src/` code (the UI carries zero business
logic):

- A **range**, never a single guaranteed price.
- When there are no comparable listings, it says **"not enough comparable signal"** — it does **not**
  fake a 50th-percentile position.
- Occupancy is a **reviews-driven proxy**, surfaced as a caveat everywhere — never sold as booked nights.
- Unseen neighbourhoods are **flagged** as baseline estimates, not presented as precise.

## See it

- 🖥️ **Live dashboard:** _deploy pending_ — run locally (below) or deploy to Streamlit Community
  Cloud in two clicks (see [Deploy](#deploy)).
- 📓 **Narrated EDA notebook:** [`notebooks/eda.ipynb`](notebooks/eda.ipynb) — the full story
  (market shape → neighbourhood map → seasonality → hedonic drivers → the re-scope). Outputs are
  stripped for a clean diff; run it locally for the figures.
- 📊 **Decision report (PT-BR):** [`reports/decision_report.md`](reports/decision_report.md) —
  per-persona positioning for Rio hosts.
- 📒 **Caderno de bordo (PT-BR study log):** the living [GitHub Pages site](https://patrickfgf.github.io/rio-airbnb-pricing-lab/)
  (architecture, ADRs, glossary, build timeline — rebuilt from repo state by CI).

## Quickstart

```bash
uv sync                                              # core pipeline + model deps
uv run pytest                                        # 91 tests, ~96% coverage on src/

# The small curated snapshot (2026-03-30) is committed, so the app/notebook run immediately:
uv run --extra app streamlit run app/streamlit_app.py        # the dashboard
uv run --extra notebook jupyter lab notebooks/eda.ipynb      # the notebook
```

Rebuilding the curated data from the source dump (optional — regenerates `data/curated/`):

```bash
uv run python -m src.pipeline
```

## Deploy

The dashboard is a thin [Streamlit](https://streamlit.io/) UI; the committed curated snapshot lets it
boot with no database. To publish on **Streamlit Community Cloud**:

1. Push this repo to GitHub (or use the existing remote).
2. On [share.streamlit.io](https://share.streamlit.io/), **New app** → pick this repo/branch →
   main file `app/streamlit_app.py`.
3. It installs from [`requirements.txt`](requirements.txt) and reads the committed
   `data/curated/*.parquet`. No secrets needed (the data source is public).

## Project structure

```
src/
  data/        download + ingest the Inside Airbnb dump into DuckDB
  transform/   curated tables (listings, calendar seasonality, occupancy) — explicit grain + pandera
  model/       hedonic OLS, shrunk peer positioning, demand context, recommender, and the
               service.py orchestration the app calls (host input -> recommendation)
  pipeline.py  idempotent raw -> curated build, with a sha256 manifest
app/           Streamlit dashboard (thin UI over src/model/service)
notebooks/     narrated EDA (eda.ipynb), built by scripts/build_eda_notebook.py
reports/       decision report (PT-BR)
docs/          ground-truth validation, design spec & plans, living notebook (GitHub Pages)
tests/         91 tests (pytest), gated in CI on Python 3.11/3.12
```

## Data & provenance

Inside Airbnb, Rio de Janeiro, snapshot **2026-03-30**. The Phase-1 pipeline produces **39,816
analyzable listings** plus seasonality and occupancy tables, with per-file `sha256` recorded in
`data/curated/manifest.json`. The raw dump and the 3.4M-row calendar are **not** committed
(reconstructible); only the small curated tables the app needs are versioned, for deploy.

## License

[MIT](LICENSE).
