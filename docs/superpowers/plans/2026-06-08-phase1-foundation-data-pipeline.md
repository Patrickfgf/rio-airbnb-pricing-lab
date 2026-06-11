# Phase 1 — Foundation + Data Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Revision note (2026-06-08):** hardened after an adversarial plan review. Key changes: pandera `coerce=True` + NA-safe contracts for **all three** curated tables; `estimate_occupancy` NaN-safe + canonical baseline (author refines later); the **raw DuckDB layer is materialized** (Task 11 is now used by Task 12); `reviews.csv` dropped from Phase-1 download (unused until Phase 2); `test_occupancy.py` TDD sequencing fixed; manifest enriched (timestamp + sha256); curated drop also removes null neighbourhood/room_type.

**Goal:** A reproducible, tested pipeline that downloads the Inside Airbnb Rio de Janeiro dump, loads it into DuckDB (raw layer), and transforms it into typed **curated** tables (listings + per-listing occupancy estimate + seasonality), with `pytest` green and GitHub Actions CI (Ruff + tests) passing.

**Architecture:** Local-first, `uv`-managed. Two explicit data layers in DuckDB: **raw** (verbatim from the dump, materialized as `raw_*` tables) → **curated** (cleaned, typed, feature-engineered, reconstructible from raw). Transform logic lives in small **pure functions** (`src/transform/`) that take/return DataFrames and know nothing about I/O, the model, or the UI. The ~13M-row `calendar` file is aggregated in **DuckDB SQL**, never loaded whole into pandas. The pipeline is **idempotent** (re-run → same curated output) and records the resolved snapshot in a versioned `manifest.json`.

**Tech Stack:** Python 3.12 · `uv` · pandas 2.x (copy-on-write) · DuckDB · pandera (schema contracts) · requests (download) · pytest + pytest-cov · Ruff · GitHub Actions.

**Data reality (confirmed via recon — see `docs/superpowers/specs/`):**
- Detailed files: `https://data.insideairbnb.com/brazil/rj/rio-de-janeiro/<YYYY-MM-DD>/data/{listings,calendar,reviews}.csv.gz`
- Host `data.insideairbnb.com` returns **HTTP 403** to non-browser clients → must send `User-Agent` (browser) + `Referer: https://insideairbnb.com/get-the-data/`.
- `price` is a **string** `"$1,200.00"` (US glyph, value is BRL) → strip `$`/`,`, cast float.
- Booleans are `'t'`/`'f'` strings; `host_response_rate`/`host_acceptance_rate` are `'95%'` strings.
- `bathrooms` is empty → real value in `bathrooms_text` (`"1.5 baths"`, `"Half-bath"`).
- `neighbourhood_group_cleansed` is **all-null** for Rio → use `neighbourhood_cleansed`.
- `cancellation_policy` **does not exist** anymore → flexibility dimension = `instant_bookable` + `minimum_nights` + `host_response_time`/`host_acceptance_rate`.
- `estimated_occupancy_l365d` / `estimated_revenue_l365d` **may** be present (Dec-2024 schema) → ingest schema-flexibly; use as occupancy **benchmark** when present.

---

## File Structure

```
pyproject.toml                      # uv project, deps, ruff + pytest config
.python-version                     # 3.12 (local dev; project supports >=3.11)
.gitignore                          # data/, .venv/, *.duckdb, __pycache__/, .pytest_cache/
LICENSE                             # MIT
README.md                           # one-line stub (insight-first README is Phase 3)
.github/workflows/ci.yml            # Ruff + pytest on a Python matrix
src/__init__.py
src/config.py                       # paths, URL pattern, candidate dates, winsor thresholds
src/data/__init__.py
src/data/download.py                # resolve snapshot date + download .gz (browser headers)
src/data/ingest.py                  # load raw csv.gz into DuckDB raw tables (header-flexible)
src/transform/__init__.py
src/transform/clean_price.py        # "$1,200.00" -> float
src/transform/parse_fields.py       # 't'/'f' -> bool ; "95%" -> 0.95 ; bathrooms_text -> float
src/transform/listings.py           # raw listings -> curated listings (typed + features)
src/transform/calendar.py           # DuckDB SQL: calendar -> seasonality agg
src/transform/occupancy.py          # occupancy proxy (SF model + blend) ⭐ author refines blend
src/schemas.py                      # pandera contracts for the 3 curated tables
src/pipeline.py                     # orchestrate raw -> curated (idempotent + manifest)
tests/__init__.py
tests/conftest.py                   # fixtures: tiny DataFrames mimicking the raw schema
tests/test_clean_price.py
tests/test_parse_fields.py
tests/test_listings.py
tests/test_calendar.py
tests/test_occupancy.py
tests/test_schemas.py
tests/test_ingest.py
tests/test_download.py
tests/test_pipeline.py
data/                               # gitignored; raw/ + curated/ created at runtime
```

---

### Task 1: Project scaffolding (uv) + tooling config

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `LICENSE`, `README.md`
- Create: `src/__init__.py`, `src/config.py`, `src/data/__init__.py`, `src/transform/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "rio-airbnb-pricing-lab"
version = "0.1.0"
description = "Pricing decision lab for Airbnb hosts in Rio de Janeiro"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "duckdb>=1.1",
    "pandera>=0.22",
    "requests>=2.32",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --cov=src --cov-report=term-missing"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

- [ ] **Step 2: Create `.python-version`**

```
3.12
```

> Note: the local pin is 3.12, while `requires-python = ">=3.11"` and the CI matrix test 3.11 + 3.12. This is intentional (develop on 3.12, support 3.11), not a mistake.

- [ ] **Step 3: Create `.gitignore`**

```gitignore
# Data (reconstructible from the dump; never commit)
data/
*.duckdb
*.duckdb.wal
*.csv.gz

# Python
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/

# Notebooks
.ipynb_checkpoints/

# OS / IDE
.DS_Store
.vscode/
.idea/
```

- [ ] **Step 4: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Patrick Fernandes Godinho Filho

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Create `README.md` (stub)**

```markdown
# Rio Airbnb Pricing Lab

Pricing decision tool for Airbnb hosts in Rio de Janeiro, built on open Inside Airbnb data.
Insight-first README and live dashboard land in Phase 3. See `docs/superpowers/`.

**Data snapshot:** resolved at runtime (recorded in `data/curated/manifest.json`).
```

- [ ] **Step 6: Create empty package markers**

Create `src/__init__.py`, `src/data/__init__.py`, `src/transform/__init__.py`, `tests/__init__.py` — each an empty file.

- [ ] **Step 7: Create `src/config.py`**

```python
"""Central configuration: paths, data-source URL pattern, and documented thresholds.

All paths are relative to the project root so the project is portable.
No absolute paths, no hardcoded secrets (the data source is public).
"""
from __future__ import annotations

from pathlib import Path

# --- Paths (relative; resolved from this file's location) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CURATED_DIR = DATA_DIR / "curated"
DUCKDB_PATH = DATA_DIR / "rio.duckdb"
MANIFEST_PATH = CURATED_DIR / "manifest.json"

# --- Inside Airbnb data source ---
CITY_PATH = "brazil/rj/rio-de-janeiro"
URL_TEMPLATE = "https://data.insideairbnb.com/{city}/{date}/data/{file}.csv.gz"
DATA_REFERER = "https://insideairbnb.com/get-the-data/"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Phase 1 uses listings + calendar only. reviews.csv (per-review-date cadence) is
# downloaded and used in Phase 2 for the occupancy cross-check — not needed yet.
DUMP_FILES = ("listings", "calendar")

# Snapshot resolution: try an explicit override first, else probe these
# end-of-quarter-ish candidates (descending) and take the first HTTP 200.
# Inside Airbnb publishes ~quarterly; update this list as new dumps appear.
SNAPSHOT_DATE_OVERRIDE: str | None = None
CANDIDATE_SNAPSHOT_DATES: tuple[str, ...] = (
    "2026-06-30", "2026-03-31", "2025-12-20", "2025-09-29", "2025-06-23",
)

# --- Documented analysis thresholds (see spec section 6: bias mitigation) ---
PRICE_WINSOR_LOWER_Q = 0.01   # clip extreme low prices (data-entry noise)
PRICE_WINSOR_UPPER_Q = 0.99   # clip extreme high prices (luxury outliers)

# --- Occupancy proxy (San Francisco Model) constants (see occupancy.py) ---
SF_REVIEW_RATE = 0.5          # fraction of stays that leave a review (Inside Airbnb assumption)
SF_AVG_LENGTH_OF_STAY = 4.0   # nights; Rio-tunable in Phase 2 from data
SF_MAX_OCCUPANCY = 0.70       # cap to avoid implausible >70% annual occupancy
```

- [ ] **Step 8: Initialize uv environment and verify it resolves**

Run:
```bash
uv sync
```
Expected: creates `.venv/`, installs deps + dev group, prints a resolution summary with no errors.

- [ ] **Step 9: Run Ruff to confirm config is valid**

Run:
```bash
uv run ruff check .
```
Expected: `All checks passed!` (no files to lint yet beyond config/stubs).

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .python-version .gitignore LICENSE README.md src tests
git commit -m "chore: scaffold uv project with ruff and pytest config"
```

---

### Task 2: CI workflow (Ruff + pytest)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint (Ruff)
        run: uv run ruff check .

      - name: Test (pytest)
        run: uv run pytest
```

- [ ] **Step 2: Generate the lockfile referenced by `--frozen`**

Run:
```bash
uv lock
```
Expected: creates/updates `uv.lock`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml uv.lock
git commit -m "ci: add Ruff + pytest workflow on Python 3.11/3.12 matrix"
```

---

### Task 3: `clean_price` — currency string to float

**Files:**
- Create: `src/transform/clean_price.py`
- Test: `tests/test_clean_price.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clean_price.py
import numpy as np
import pandas as pd

from src.transform.clean_price import clean_price


def test_strips_dollar_and_thousands_comma():
    s = pd.Series(["$1,200.00", "$75.00", "$0.00"])
    result = clean_price(s)
    assert result.tolist() == [1200.0, 75.0, 0.0]


def test_handles_missing_and_blank_as_nan():
    s = pd.Series(["$50.00", None, "", np.nan])
    result = clean_price(s)
    assert result[0] == 50.0
    assert result[1:].isna().all()


def test_returns_float_dtype():
    result = clean_price(pd.Series(["$10.00"]))
    assert result.dtype == np.float64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_clean_price.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.clean_price'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform/clean_price.py
"""Parse Inside Airbnb price strings ("$1,200.00") into floats.

The '$' glyph is a display artifact in the export; the value is BRL for Rio.
We only strip formatting and cast — no currency conversion. Note: pd.NA from
None/np.nan propagates through the str methods automatically; the .replace("", pd.NA)
only handles the bare empty-string case, and pd.to_numeric coerces both to NaN.
"""
from __future__ import annotations

import pandas as pd


def clean_price(prices: pd.Series) -> pd.Series:
    """Convert a Series of price strings like "$1,200.00" to float (NaN if blank/missing)."""
    cleaned = (
        prices.astype("string")
        .str.replace(r"[$,]", "", regex=True)
        .str.strip()
        .replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_clean_price.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/transform/clean_price.py tests/test_clean_price.py
git commit -m "feat: add clean_price transform for currency strings"
```

---

### Task 4: `parse_fields` — booleans, percents, bathrooms

**Files:**
- Create: `src/transform/parse_fields.py`
- Test: `tests/test_parse_fields.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parse_fields.py
import pandas as pd

from src.transform.parse_fields import parse_tf_bool, parse_percent, parse_bathrooms


def test_parse_tf_bool_maps_t_f_and_null():
    s = pd.Series(["t", "f", None, "t"])
    result = parse_tf_bool(s)
    assert result.tolist()[:2] == [True, False]
    assert pd.isna(result[2])
    assert bool(result[3]) is True


def test_parse_percent_strips_sign_and_scales():
    s = pd.Series(["100%", "90%", "N/A", None])
    result = parse_percent(s)
    assert result[0] == 1.0
    assert result[1] == 0.9
    assert result[2:].isna().all()


def test_parse_bathrooms_extracts_leading_number():
    s = pd.Series(["1 bath", "1.5 shared baths", "2 baths", "0 baths"])
    result = parse_bathrooms(s)
    assert result.tolist() == [1.0, 1.5, 2.0, 0.0]


def test_parse_bathrooms_handles_half_bath_and_null():
    s = pd.Series(["Half-bath", "Shared half-bath", None, ""])
    result = parse_bathrooms(s)
    assert result[0] == 0.5
    assert result[1] == 0.5
    assert result[2:].isna().all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_parse_fields.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.parse_fields'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform/parse_fields.py
"""Parse Inside Airbnb's quirky encodings: 't'/'f' booleans, '95%' strings,
and free-text bathrooms ('1.5 shared baths', 'Half-bath')."""
from __future__ import annotations

import pandas as pd


def parse_tf_bool(series: pd.Series) -> pd.Series:
    """Map 't'/'f' strings to nullable boolean (pd.NA for anything else)."""
    return series.map({"t": True, "f": False}).astype("boolean")


def parse_percent(series: pd.Series) -> pd.Series:
    """Convert '95%' strings to 0.95 floats; 'N/A'/blank/None -> NaN."""
    cleaned = (
        series.astype("string")
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return (numeric / 100.0).astype("float64")


def parse_bathrooms(series: pd.Series) -> pd.Series:
    """Extract numeric bathroom count from bathrooms_text.

    'Half-bath' / 'Shared half-bath' -> 0.5; otherwise the leading float.
    Assumes (true for real Inside Airbnb data) that 'half' strings carry no
    numeric prefix, so the half-mask override never clobbers a real count.
    """
    text = series.astype("string").str.strip()
    half_mask = text.str.contains("half", case=False, na=False)
    extracted = text.str.extract(r"(\d+\.?\d*)", expand=False)
    result = pd.to_numeric(extracted, errors="coerce")
    result = result.mask(half_mask, 0.5)
    return result.astype("float64")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_parse_fields.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/transform/parse_fields.py tests/test_parse_fields.py
git commit -m "feat: add parse_fields for booleans, percents, and bathrooms_text"
```

---

### Task 5: Shared test fixtures (raw-schema samples)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

This fixture mimics the **raw** Inside Airbnb listings schema (only the columns the pipeline touches) so downstream tests never need the real ~200MB dump. It deliberately includes the quirks: `'t'/'f'`, `"$..."`, `bathrooms` empty + `bathrooms_text` populated, an all-null `neighbourhood_group_cleansed`, and no `estimated_occupancy_l365d` column (to prove header-flexible handling).

```python
# tests/conftest.py
import pandas as pd
import pytest


@pytest.fixture
def raw_listings() -> pd.DataFrame:
    """Tiny raw-listings sample reproducing Inside Airbnb encoding quirks."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "neighbourhood_cleansed": ["Copacabana", "Copacabana", "Leblon", "Centro"],
            "neighbourhood_group_cleansed": [None, None, None, None],
            "latitude": [-22.97, -22.98, -22.98, -22.90],
            "longitude": [-43.18, -43.19, -43.22, -43.18],
            "room_type": ["Entire home/apt", "Private room", "Entire home/apt", "Entire home/apt"],
            "property_type": ["Entire rental unit", "Private room in home",
                              "Entire condo", "Entire rental unit"],
            "accommodates": [4, 2, 6, 3],
            "bedrooms": [2, 1, 3, 1],
            "beds": [2, 1, 4, 2],
            "bathrooms": [None, None, None, None],
            "bathrooms_text": ["1 bath", "1 shared bath", "2.5 baths", "Half-bath"],
            "price": ["$500.00", "$150.00", "$1,200.00", None],
            "minimum_nights": [2, 1, 3, 1],
            "host_is_superhost": ["t", "f", "t", None],
            "instant_bookable": ["f", "t", "t", "f"],
            "host_response_time": ["within an hour", "within a day", None, "within a few hours"],
            "host_response_rate": ["100%", "90%", "N/A", None],
            "host_acceptance_rate": ["95%", "80%", "100%", None],
            "number_of_reviews": [120, 10, 45, 0],
            "number_of_reviews_ltm": [30, 4, 12, 0],
            "reviews_per_month": [2.5, 0.3, 1.1, None],
            "review_scores_rating": [4.9, 4.2, 4.7, None],
            "availability_365": [120, 300, 60, 365],
            "last_review": ["2026-05-01", "2026-01-15", "2026-04-20", None],
            "first_review": ["2019-01-01", "2024-06-01", "2021-03-01", None],
        }
    )


@pytest.fixture
def raw_calendar() -> pd.DataFrame:
    """Tiny raw-calendar sample (grain = 1 row per listing-day)."""
    dates = pd.date_range("2026-01-01", periods=5, freq="D").strftime("%Y-%m-%d")
    rows = []
    for lid, avails in [(1, ["t", "f", "f", "t", "f"]), (2, ["t", "t", "t", "f", "t"])]:
        for d, a in zip(dates, avails, strict=True):
            rows.append({"listing_id": lid, "date": d, "available": a,
                         "price": "$500.00", "minimum_nights": 2, "maximum_nights": 365})
    return pd.DataFrame(rows)
```

- [ ] **Step 2: Verify the fixtures import cleanly**

Run: `uv run pytest tests/ --collect-only`
Expected: collects with no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add raw-schema fixtures for listings and calendar"
```

---

### Task 6: `transform/listings` — raw listings to curated

**Files:**
- Create: `src/transform/listings.py`
- Test: `tests/test_listings.py`

The curated listings table is the analysis backbone. Grain: **1 row = 1 analyzable listing** (has a positive price, a neighbourhood, and a room_type). It applies the field parsers, derives the flexibility proxies (replacing the removed `cancellation_policy`), winsorizes price, and keeps `estimated_occupancy_l365d`/`estimated_revenue_l365d` **only if present** (header-flexible).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_listings.py
import pandas as pd

from src.transform.listings import build_curated_listings


def test_types_and_core_columns(raw_listings):
    out = build_curated_listings(raw_listings)
    assert out["price"].dtype.kind == "f"
    assert out["host_is_superhost"].dtype == "boolean"
    assert out["bathrooms_num"].tolist()[:3] == [1.0, 1.0, 2.5]
    assert {"listing_id", "neighbourhood", "room_type", "accommodates",
            "price", "host_is_superhost", "instant_bookable",
            "min_nights", "bathrooms_num", "number_of_reviews_ltm"}.issubset(out.columns)


def test_drops_rows_without_usable_price(raw_listings):
    # id=4 has price None -> dropped. The filter also drops price <= 0 and rows
    # with null neighbourhood/room_type (can't place them in a comparable set).
    out = build_curated_listings(raw_listings)
    assert 4 not in out["listing_id"].tolist()
    assert len(out) == 3


def test_percent_columns_scaled(raw_listings):
    out = build_curated_listings(raw_listings)
    row = out.loc[out["listing_id"] == 1].iloc[0]
    assert row["host_response_rate"] == 1.0
    assert row["host_acceptance_rate"] == 0.95


def test_winsorize_is_noop_on_small_sample(raw_listings):
    # With 3 priced rows and q=[0.01,0.99], clip bounds ~= min/max -> values unchanged
    out = build_curated_listings(raw_listings)
    assert sorted(out["price"].tolist()) == [150.0, 500.0, 1200.0]


def test_estimated_columns_passthrough_when_present(raw_listings):
    df = raw_listings.copy()
    df["estimated_occupancy_l365d"] = [200, 50, 150, 0]
    out = build_curated_listings(df)
    assert "estimated_occupancy_l365d" in out.columns


def test_no_estimated_columns_when_absent(raw_listings):
    out = build_curated_listings(raw_listings)
    assert "estimated_occupancy_l365d" not in out.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_listings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.listings'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform/listings.py
"""Build the curated listings table (grain: 1 row = 1 analyzable listing).

Pure function: raw DataFrame in, typed curated DataFrame out. No I/O.
Replaces the removed `cancellation_policy` with operational flexibility proxies.
Works whether the raw frame comes from pandas (native dtypes) or from DuckDB
read with all_varchar=true (everything arrives as strings) — all casts below
tolerate string inputs.
"""
from __future__ import annotations

import pandas as pd

from src.config import PRICE_WINSOR_LOWER_Q, PRICE_WINSOR_UPPER_Q
from src.transform.clean_price import clean_price
from src.transform.parse_fields import parse_bathrooms, parse_percent, parse_tf_bool

# Optional columns kept only if the dump provides them (schema-flexible).
OPTIONAL_PASSTHROUGH = ("estimated_occupancy_l365d", "estimated_revenue_l365d")


def _winsorize(s: pd.Series, lower_q: float, upper_q: float) -> pd.Series:
    lo, hi = s.quantile(lower_q), s.quantile(upper_q)
    return s.clip(lower=lo, upper=hi)


def build_curated_listings(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean, type, and feature-engineer raw listings into the curated table."""
    df = pd.DataFrame(
        {
            "listing_id": pd.to_numeric(raw["id"], errors="coerce").astype("int64"),
            "neighbourhood": raw["neighbourhood_cleansed"].astype("string"),
            "room_type": raw["room_type"].astype("string"),
            "property_type": raw["property_type"].astype("string"),
            "accommodates": pd.to_numeric(raw["accommodates"], errors="coerce").astype("Int64"),
            "bedrooms": pd.to_numeric(raw["bedrooms"], errors="coerce").astype("Int64"),
            "beds": pd.to_numeric(raw["beds"], errors="coerce").astype("Int64"),
            "bathrooms_num": parse_bathrooms(raw["bathrooms_text"]),
            "price": clean_price(raw["price"]),
            "min_nights": pd.to_numeric(raw["minimum_nights"], errors="coerce").astype("Int64"),
            "host_is_superhost": parse_tf_bool(raw["host_is_superhost"]),
            "instant_bookable": parse_tf_bool(raw["instant_bookable"]),
            "host_response_time": raw["host_response_time"].astype("string"),
            "host_response_rate": parse_percent(raw["host_response_rate"]),
            "host_acceptance_rate": parse_percent(raw["host_acceptance_rate"]),
            "number_of_reviews": pd.to_numeric(raw["number_of_reviews"], errors="coerce").astype("Int64"),
            "number_of_reviews_ltm": pd.to_numeric(raw["number_of_reviews_ltm"], errors="coerce").astype("Int64"),
            "reviews_per_month": pd.to_numeric(raw["reviews_per_month"], errors="coerce").astype("float64"),
            "review_scores_rating": pd.to_numeric(raw["review_scores_rating"], errors="coerce").astype("float64"),
            "availability_365": pd.to_numeric(raw["availability_365"], errors="coerce").astype("Int64"),
            "last_review": pd.to_datetime(raw["last_review"], errors="coerce"),
            "first_review": pd.to_datetime(raw["first_review"], errors="coerce"),
        }
    )

    for col in OPTIONAL_PASSTHROUGH:
        if col in raw.columns:
            df[col] = pd.to_numeric(raw[col], errors="coerce")

    # Treat empty strings (from CSV reads) as missing for the analysis keys.
    for key in ("neighbourhood", "room_type"):
        df[key] = df[key].replace("", pd.NA)

    # Keep only analyzable listings: positive price + neighbourhood + room_type.
    # price > 0 is deliberate — a free listing has no RevPAN to optimize.
    keep = (
        df["price"].notna()
        & (df["price"] > 0)
        & df["neighbourhood"].notna()
        & df["room_type"].notna()
    )
    df = df.loc[keep].reset_index(drop=True)

    # Winsorize price to documented quantiles (spec section 6: outlier handling).
    df["price"] = _winsorize(df["price"], PRICE_WINSOR_LOWER_Q, PRICE_WINSOR_UPPER_Q)

    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_listings.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/transform/listings.py tests/test_listings.py
git commit -m "feat: build curated listings with flexibility proxies and winsorized price"
```

---

### Task 7: `transform/calendar` — DuckDB seasonality aggregation

**Files:**
- Create: `src/transform/calendar.py`
- Test: `tests/test_calendar.py`

The calendar file has ~13M rows, so we aggregate it in **DuckDB SQL**. Two entry points share one SQL builder: `aggregate_calendar` (registers an in-memory frame — used in tests) and `aggregate_calendar_table` (aggregates an already-loaded raw table — used by the pipeline). Output grain: **1 row = listing_id × month × day-of-week**, with median calendar price and a naive `booked_rate` (= share of `available='f'`). `booked_rate` is the **raw, naive** occupancy signal; `occupancy.py` (Task 8) refines it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_calendar.py
import duckdb

from src.transform.calendar import aggregate_calendar


def test_booked_rate_from_availability(raw_calendar):
    con = duckdb.connect()
    out = aggregate_calendar(con, raw_calendar)
    # 5 dates 2026-01-01..05 each fall on a DISTINCT day-of-week, so each
    # (listing, month, dow) group has 1 row (booked_rate 0.0 or 1.0). Averaging
    # those per-listing => listing 1: 3 unavailable / 5 = 0.6 ; listing 2: 1/5 = 0.2.
    by_listing = out.groupby("listing_id")["booked_rate"].mean().round(3).to_dict()
    assert by_listing[1] == 0.6
    assert by_listing[2] == 0.2


def test_has_calendar_price_and_keys(raw_calendar):
    con = duckdb.connect()
    out = aggregate_calendar(con, raw_calendar)
    assert {"listing_id", "month", "dow", "median_cal_price", "booked_rate"}.issubset(out.columns)
    assert (out["median_cal_price"] == 500.0).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.calendar'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform/calendar.py
"""Aggregate the large calendar file in DuckDB (never load 13M rows into pandas).

Grain of the output: listing_id x month x day-of-week, with median calendar
price and a naive booked_rate (= share of days marked unavailable).
The booked_rate is a NAIVE signal; occupancy.py refines it (see spec section 6).
"""
from __future__ import annotations

import re

import duckdb
import pandas as pd

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _agg_sql(src: str) -> str:
    """Build the aggregation SQL over relation `src` (an internal, allow-listed name)."""
    return f"""
    WITH parsed AS (
        SELECT
            CAST(listing_id AS BIGINT)                                   AS listing_id,
            CAST(date AS DATE)                                           AS d,
            (available = 'f')                                            AS is_unavailable,
            CAST(REPLACE(REPLACE(price, '$', ''), ',', '') AS DOUBLE)   AS cal_price
        FROM {src}
        WHERE price IS NOT NULL
    )
    SELECT
        listing_id,
        MONTH(d)                                            AS month,
        DAYOFWEEK(d)                                        AS dow,  -- 0=Sunday .. 6=Saturday
        MEDIAN(cal_price)                                   AS median_cal_price,
        AVG(CASE WHEN is_unavailable THEN 1.0 ELSE 0.0 END) AS booked_rate
    FROM parsed
    GROUP BY listing_id, MONTH(d), DAYOFWEEK(d)
    ORDER BY listing_id, month, dow
    """


def aggregate_calendar(con: duckdb.DuckDBPyConnection, calendar: pd.DataFrame) -> pd.DataFrame:
    """Aggregate an in-memory calendar frame (used in tests)."""
    con.register("cal", calendar)
    try:
        return con.execute(_agg_sql("cal")).df()
    finally:
        con.unregister("cal")


def aggregate_calendar_table(
    con: duckdb.DuckDBPyConnection, table: str = "raw_calendar"
) -> pd.DataFrame:
    """Aggregate an already-loaded raw calendar table (used by the pipeline)."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return con.execute(_agg_sql(table)).df()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/transform/calendar.py tests/test_calendar.py
git commit -m "feat: aggregate calendar seasonality in DuckDB"
```

---

### Task 8: `transform/occupancy` — occupancy proxy ⭐ AUTHOR REFINES BLEND

**Files:**
- Create: `src/transform/occupancy.py`
- Test: `tests/test_occupancy.py`

> **★ Author domain-judgment point (spec §11, §6).** The assistant commits a **canonical, deterministic baseline** so the pipeline runs end-to-end without human input: the reviews-based **San Francisco Model** plus a 50/50 blend with the calendar `booked_rate`. **The author's contribution (Step 5, optional, can happen any time) is to refine the blend** — how to weight a noisy-but-direct signal (calendar) against an indirect-but-robust one (reviews). The whole test file is written up front so there is no TDD collection-order trap.

- [ ] **Step 1: Write the full failing test file**

```python
# tests/test_occupancy.py
import pandas as pd

from src.config import SF_AVG_LENGTH_OF_STAY, SF_MAX_OCCUPANCY, SF_REVIEW_RATE
from src.transform.occupancy import estimate_occupancy, sf_model_occupancy


def test_sf_model_basic():
    # reviews_ltm=12 -> stays = 12 / 0.5 = 24 -> nights = 24*4 = 96 -> /365
    out = sf_model_occupancy(pd.Series([12.0]))
    expected = min((12 / SF_REVIEW_RATE) * SF_AVG_LENGTH_OF_STAY / 365.0, SF_MAX_OCCUPANCY)
    assert round(out.iloc[0], 4) == round(expected, 4)


def test_sf_model_caps_at_max():
    out = sf_model_occupancy(pd.Series([1000.0]))
    assert out.iloc[0] == SF_MAX_OCCUPANCY


def test_sf_model_zero_reviews_is_zero():
    out = sf_model_occupancy(pd.Series([0.0, None]))
    assert out.iloc[0] == 0.0
    assert out.iloc[1] == 0.0


def test_estimate_occupancy_blends_signals():
    listings = pd.DataFrame({"listing_id": [1, 2], "number_of_reviews_ltm": [12.0, 0.0]})
    cal_booked = pd.Series([0.6, 0.2], index=[1, 2])  # booked_rate per listing_id
    out = estimate_occupancy(listings, cal_booked)
    assert {"listing_id", "occupancy_est"}.issubset(out.columns)
    assert out["occupancy_est"].between(0, 1).all()
    occ = out.set_index("listing_id")["occupancy_est"]
    assert round(occ[2], 4) == 0.1     # sf=0.0, cal=0.2 -> mean = 0.1
    assert round(occ[1], 2) == 0.43    # sf~0.263, cal=0.6 -> mean ~0.4315


def test_estimate_occupancy_missing_calendar_is_finite():
    # listing 2 absent from cal_booked and has no reviews -> must not be NaN.
    listings = pd.DataFrame({"listing_id": [1, 2], "number_of_reviews_ltm": [12.0, None]})
    cal_booked = pd.Series([0.6], index=[1])
    out = estimate_occupancy(listings, cal_booked)
    occ = out.set_index("listing_id")["occupancy_est"]
    assert occ.notna().all()
    assert occ[2] == 0.0
    assert out["occupancy_est"].between(0, 1).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_occupancy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.occupancy'`

- [ ] **Step 3: Write the canonical implementation (SF model + baseline blend)**

```python
# src/transform/occupancy.py
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
```

> Note: `np.nanmean` over two all-NaN entries warns and yields NaN; the trailing
> `.fillna(0.0)` makes that case deterministic and keeps `occupancy_est` in range.

- [ ] **Step 4: Run the full occupancy test file to verify it passes**

Run: `uv run pytest tests/test_occupancy.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: ⭐ AUTHOR (optional, non-blocking) — refine the blend**

When ready, edit `estimate_occupancy` (the blend) and tighten `test_estimate_occupancy_blends_signals` to assert your chosen weighting. The committed baseline already keeps the pipeline green, so this can happen during or after Phase 1 without blocking Task 12.

- [ ] **Step 6: Commit**

```bash
git add src/transform/occupancy.py tests/test_occupancy.py
git commit -m "feat: add occupancy estimation (SF model + NaN-safe baseline blend)"
```

---

### Task 9: `schemas` — pandera contracts for the curated tables

**Files:**
- Create: `src/schemas.py`
- Test: `tests/test_schemas.py`

Enforce contracts for **all three** curated tables: key uniqueness/non-null (the **grain**), value ranges, and types. `coerce=True` normalizes pandas nullable ExtensionDtypes (`Int64`/`boolean`/`string`) before checking — without it, dtype-string validation against nullable columns is version-fragile. pandera's checks skip NA on nullable columns by default (`ignore_na=True`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
import pandas as pd
import pytest

from src.schemas import (
    validate_curated_listings,
    validate_curated_occupancy,
    validate_curated_seasonality,
)
from src.transform.listings import build_curated_listings


def test_valid_curated_listings_passes(raw_listings):
    out = build_curated_listings(raw_listings)
    validate_curated_listings(out)  # should not raise


def test_duplicate_listing_id_fails(raw_listings):
    out = build_curated_listings(raw_listings)
    dup = pd.concat([out, out.iloc[[0]]], ignore_index=True)
    with pytest.raises(Exception):
        validate_curated_listings(dup)


def test_negative_price_fails(raw_listings):
    out = build_curated_listings(raw_listings).copy()
    out.loc[0, "price"] = -10.0
    with pytest.raises(Exception):
        validate_curated_listings(out)


def test_valid_curated_occupancy():
    df = pd.DataFrame({"listing_id": [1, 2], "occupancy_est": [0.3, 0.5]})
    validate_curated_occupancy(df)


def test_occupancy_out_of_range_fails():
    df = pd.DataFrame({"listing_id": [1], "occupancy_est": [1.5]})
    with pytest.raises(Exception):
        validate_curated_occupancy(df)


def test_valid_curated_seasonality():
    df = pd.DataFrame(
        {"listing_id": [1, 1], "month": [1, 2], "dow": [3, 4],
         "median_cal_price": [500.0, 500.0], "booked_rate": [0.6, 0.2]}
    )
    validate_curated_seasonality(df)


def test_seasonality_duplicate_key_fails():
    df = pd.DataFrame(
        {"listing_id": [1, 1], "month": [1, 1], "dow": [3, 3],
         "median_cal_price": [500.0, 500.0], "booked_rate": [0.6, 0.2]}
    )
    with pytest.raises(Exception):
        validate_curated_seasonality(df)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.schemas'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/schemas.py
"""Pandera contracts for the curated tables.

Grains:
  - curated_listings: 1 row = 1 listing (listing_id unique)
  - curated_occupancy: 1 row = 1 listing (listing_id unique)
  - curated_seasonality: 1 row = (listing_id, month, dow)

Note: on pandera >= 0.23 the import is `import pandera.pandas as pa`; the guard
below keeps both new and old installs working. coerce=True normalizes nullable
ExtensionDtypes before checking.
"""
from __future__ import annotations

try:  # pandera >= 0.23 split the pandas API into a submodule
    from pandera.pandas import Check, Column, DataFrameSchema
except ImportError:  # pragma: no cover
    from pandera import Check, Column, DataFrameSchema

import pandas as pd

CURATED_LISTINGS_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", unique=True, nullable=False),
        "neighbourhood": Column("string", nullable=False),
        "room_type": Column("string", nullable=False),
        "price": Column("float64", Check.gt(0), nullable=False),
        "accommodates": Column("Int64", Check.ge(0), nullable=True),
        "min_nights": Column("Int64", Check.ge(0), nullable=True),
        "number_of_reviews_ltm": Column("Int64", Check.ge(0), nullable=True),
        "host_is_superhost": Column("boolean", nullable=True),
        "instant_bookable": Column("boolean", nullable=True),
        "host_response_rate": Column("float64", Check.in_range(0, 1), nullable=True),
        "host_acceptance_rate": Column("float64", Check.in_range(0, 1), nullable=True),
        "review_scores_rating": Column("float64", Check.in_range(0, 5), nullable=True),
    },
    strict=False,  # allow extra columns (optional passthrough, derived features)
    coerce=True,
)

CURATED_OCCUPANCY_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", unique=True, nullable=False),
        "occupancy_est": Column("float64", Check.in_range(0, 1), nullable=False),
    },
    strict=False,
    coerce=True,
)

CURATED_SEASONALITY_SCHEMA = DataFrameSchema(
    {
        "listing_id": Column("int64", nullable=False),
        "month": Column("int64", Check.in_range(1, 12), nullable=False),
        "dow": Column("int64", Check.in_range(0, 6), nullable=False),
        "median_cal_price": Column("float64", Check.ge(0), nullable=True),
        "booked_rate": Column("float64", Check.in_range(0, 1), nullable=False),
    },
    strict=False,
    coerce=True,
    unique=["listing_id", "month", "dow"],
)


def validate_curated_listings(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated listings table against its contract. Raises on violation."""
    return CURATED_LISTINGS_SCHEMA.validate(df, lazy=False)


def validate_curated_occupancy(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated occupancy table. Raises on violation."""
    return CURATED_OCCUPANCY_SCHEMA.validate(df, lazy=False)


def validate_curated_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the curated seasonality table. Raises on violation."""
    return CURATED_SEASONALITY_SCHEMA.validate(df, lazy=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/schemas.py tests/test_schemas.py
git commit -m "feat: add pandera contracts for the three curated tables"
```

---

### Task 10: `data/download` — resolve snapshot + fetch dump

**Files:**
- Create: `src/data/download.py`
- Test: `tests/test_download.py`

Download must defeat the **403 anti-hotlinking** (browser UA + Referer) and **resolve the snapshot date at runtime** (no hardcoded date). The `override` default is read from config **at call time** (sentinel pattern), not import time. Tests mock HTTP with `monkeypatch` — no network in CI.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_download.py
import src.data.download as dl


class _FakeResp:
    def __init__(self, status, content=b"data"):
        self.status_code = status
        self.content = content

    def iter_content(self, chunk_size):
        yield self.content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_resolve_snapshot_picks_first_200(monkeypatch):
    def fake_head(url, *, headers, timeout):
        return _FakeResp(200 if "2026-03-31" in url else 404)

    monkeypatch.setattr(dl.requests, "head", fake_head)
    date = dl.resolve_snapshot_date(["2026-06-30", "2026-03-31"])
    assert date == "2026-03-31"


def test_resolve_honors_override(monkeypatch):
    monkeypatch.setattr(dl.requests, "head", lambda *a, **k: _FakeResp(200))
    assert dl.resolve_snapshot_date(["2099-01-01"], override="2025-12-20") == "2025-12-20"


def test_download_file_writes_with_browser_headers(monkeypatch, tmp_path):
    seen = {}

    def fake_get(url, *, headers, timeout, stream):
        seen["headers"] = headers
        return _FakeResp(200, content=b"gzipped-bytes")

    monkeypatch.setattr(dl.requests, "get", fake_get)
    dest = tmp_path / "listings.csv.gz"
    dl.download_file("http://x/listings.csv.gz", dest)
    assert dest.read_bytes() == b"gzipped-bytes"
    assert "Mozilla" in seen["headers"]["User-Agent"]
    assert seen["headers"]["Referer"].startswith("https://insideairbnb.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_download.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.download'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/data/download.py
"""Resolve the latest Inside Airbnb Rio snapshot and download the dump files.

Defeats data.insideairbnb.com's 403 anti-hotlinking with a browser User-Agent
and a Referer header. The snapshot date is resolved at runtime (no hardcoding).
"""
from __future__ import annotations

from pathlib import Path

import requests

from src import config

_HEADERS = {"User-Agent": config.BROWSER_USER_AGENT, "Referer": config.DATA_REFERER}


def build_url(date: str, file: str) -> str:
    return config.URL_TEMPLATE.format(city=config.CITY_PATH, date=date, file=file)


def resolve_snapshot_date(
    candidates: list[str] | None = None,
    override: str | None = None,
) -> str:
    """Return the first candidate date whose listings file exists (HTTP 200)."""
    override = override if override is not None else config.SNAPSHOT_DATE_OVERRIDE
    if override:
        return override
    candidates = candidates or list(config.CANDIDATE_SNAPSHOT_DATES)
    for date in candidates:
        resp = requests.head(build_url(date, "listings"), headers=_HEADERS, timeout=30)
        if resp.status_code == 200:
            return date
    raise RuntimeError(f"No available snapshot among candidates: {candidates}")


def download_file(url: str, dest: Path) -> Path:
    """Stream a file to disk using browser headers (avoids 403)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, headers=_HEADERS, timeout=120, stream=True)
    resp.raise_for_status()
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_download.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/data/download.py tests/test_download.py
git commit -m "feat: add snapshot resolver and dump downloader with browser headers"
```

---

### Task 11: `data/ingest` — load raw csv.gz into DuckDB (header-flexible)

**Files:**
- Create: `src/data/ingest.py`
- Test: `tests/test_ingest.py`

Load each `.csv.gz` into a DuckDB **raw** table verbatim, reading all columns as text (`all_varchar=true`) so unexpected/added columns (e.g. `estimated_occupancy_l365d`) never break ingestion. The table name is allow-listed (it is interpolated into SQL; DuckDB has no parameterized identifiers). The file path is passed as a bound parameter — important on Windows, where backslashes in an interpolated path would break the SQL string.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
import gzip
from pathlib import Path

import duckdb

from src.data.ingest import load_csv_to_duckdb


def _write_csv_gz(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)


def test_loads_csv_gz_as_raw_table(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id,price\n1,$10.00\n2,$20.00\n")
    con = duckdb.connect()
    n = load_csv_to_duckdb(con, csv, "raw_listings")
    assert n == 2
    cols = [r[0] for r in con.execute("DESCRIBE raw_listings").fetchall()]
    assert cols == ["id", "price"]


def test_extra_columns_do_not_break(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id,price,estimated_occupancy_l365d\n1,$10.00,200\n")
    con = duckdb.connect()
    load_csv_to_duckdb(con, csv, "raw_listings")
    cols = [r[0] for r in con.execute("DESCRIBE raw_listings").fetchall()]
    assert "estimated_occupancy_l365d" in cols


def test_rejects_bad_table_name(tmp_path):
    csv = tmp_path / "listings.csv.gz"
    _write_csv_gz(csv, "id\n1\n")
    con = duckdb.connect()
    import pytest

    with pytest.raises(ValueError):
        load_csv_to_duckdb(con, csv, "raw; DROP TABLE x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.ingest'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/data/ingest.py
"""Load raw Inside Airbnb csv.gz files into DuckDB raw tables (verbatim, text-typed)."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_csv_to_duckdb(
    con: duckdb.DuckDBPyConnection, csv_gz_path: Path, table: str
) -> int:
    """Create/replace `table` from the csv.gz, all columns as VARCHAR. Returns row count."""
    if not _VALID_IDENT.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        "SELECT * FROM read_csv_auto(?, header=true, all_varchar=true)",
        [str(csv_gz_path)],
    )
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/data/ingest.py tests/test_ingest.py
git commit -m "feat: load raw csv.gz into DuckDB with text-typed columns"
```

---

### Task 12: `pipeline` — orchestrate raw → curated (idempotent + manifest)

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

Wire it together: resolve date → download (skip if present) → **materialize raw_* tables** → build curated listings + seasonality + occupancy → **validate all three** → write curated parquet → write enriched `manifest.json`. Idempotent: a second run reproduces identical curated output. The real run persists raw tables to `DUCKDB_PATH`; tests use an in-memory DB.

- [ ] **Step 1: Write the failing test (integration, local I/O)**

```python
# tests/test_pipeline.py
import gzip
from pathlib import Path

import pandas as pd

import src.pipeline as pipeline


def _gz(path: Path, df: pd.DataFrame) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        df.to_csv(fh, index=False)


def test_build_curated_writes_all_tables_and_manifest(tmp_path, raw_listings, raw_calendar):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _gz(raw_dir / "listings.csv.gz", raw_listings)
    _gz(raw_dir / "calendar.csv.gz", raw_calendar)

    curated = pipeline.build_curated(
        raw_dir=raw_dir, curated_dir=tmp_path / "curated", snapshot_date="2026-03-31"
    )
    cdir = tmp_path / "curated"
    assert (cdir / "listings.parquet").exists()
    assert (cdir / "occupancy.parquet").exists()
    assert (cdir / "calendar_seasonality.parquet").exists()

    season = pd.read_parquet(cdir / "calendar_seasonality.parquet")
    assert {"listing_id", "month", "dow", "median_cal_price", "booked_rate"}.issubset(season.columns)

    assert curated["manifest"]["snapshot_date"] == "2026-03-31"
    assert curated["manifest"]["n_listings"] == 3  # id=4 dropped (no price)
    assert "generated_at" in curated["manifest"]
    assert "listings.csv.gz" in curated["manifest"]["raw_files"]


def test_idempotent_curated(tmp_path, raw_listings, raw_calendar):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _gz(raw_dir / "listings.csv.gz", raw_listings)
    _gz(raw_dir / "calendar.csv.gz", raw_calendar)
    a = pipeline.build_curated(raw_dir=raw_dir, curated_dir=tmp_path / "c1", snapshot_date="2026-03-31")
    b = pipeline.build_curated(raw_dir=raw_dir, curated_dir=tmp_path / "c2", snapshot_date="2026-03-31")
    df_a = pd.read_parquet(tmp_path / "c1" / "listings.parquet")
    df_b = pd.read_parquet(tmp_path / "c2" / "listings.parquet")
    pd.testing.assert_frame_equal(df_a, df_b)
    assert a["manifest"]["n_listings"] == b["manifest"]["n_listings"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — `AttributeError: module 'src.pipeline' has no attribute 'build_curated'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/pipeline.py
"""End-to-end pipeline: download -> raw layer -> curated -> validate -> write.

Idempotent: same dump in -> identical curated out. Records the resolved snapshot,
a run timestamp, and per-file checksums in a versioned manifest.json.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from src import config
from src.data.download import build_url, download_file, resolve_snapshot_date
from src.data.ingest import load_csv_to_duckdb
from src.schemas import (
    validate_curated_listings,
    validate_curated_occupancy,
    validate_curated_seasonality,
)
from src.transform.calendar import aggregate_calendar_table
from src.transform.listings import build_curated_listings
from src.transform.occupancy import estimate_occupancy


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_dump(raw_dir: Path, snapshot_date: str | None = None) -> str:
    """Resolve the snapshot and download any missing dump files into raw_dir."""
    date = snapshot_date or resolve_snapshot_date()
    raw_dir.mkdir(parents=True, exist_ok=True)
    for file in config.DUMP_FILES:
        dest = raw_dir / f"{file}.csv.gz"
        if not dest.exists():
            download_file(build_url(date, file), dest)
    return date


def build_curated(
    raw_dir: Path, curated_dir: Path, snapshot_date: str, db_path: str = ":memory:"
) -> dict:
    """Materialize the raw layer, then transform into curated parquet + a manifest."""
    curated_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        # --- raw layer (reconstructible source of truth) ---
        load_csv_to_duckdb(con, raw_dir / "listings.csv.gz", "raw_listings")
        load_csv_to_duckdb(con, raw_dir / "calendar.csv.gz", "raw_calendar")

        # --- curated ---
        raw_listings = con.execute("SELECT * FROM raw_listings").df()
        listings = build_curated_listings(raw_listings)
        validate_curated_listings(listings)

        seasonality = aggregate_calendar_table(con, "raw_calendar")
        validate_curated_seasonality(seasonality)

        booked = seasonality.groupby("listing_id")["booked_rate"].mean()
        occupancy = estimate_occupancy(listings, booked)
        validate_curated_occupancy(occupancy)

        listings.to_parquet(curated_dir / "listings.parquet", index=False)
        seasonality.to_parquet(curated_dir / "calendar_seasonality.parquet", index=False)
        occupancy.to_parquet(curated_dir / "occupancy.parquet", index=False)

        manifest = {
            "snapshot_date": snapshot_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": build_url(snapshot_date, "listings"),
            "n_listings": int(len(listings)),
            "n_seasonality_rows": int(len(seasonality)),
            "has_estimated_occupancy": "estimated_occupancy_l365d" in listings.columns,
            "raw_files": {
                f"{name}.csv.gz": {
                    "sha256": _sha256(raw_dir / f"{name}.csv.gz"),
                    "bytes": (raw_dir / f"{name}.csv.gz").stat().st_size,
                }
                for name in config.DUMP_FILES
            },
        }
        (curated_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return {
            "listings": listings,
            "occupancy": occupancy,
            "seasonality": seasonality,
            "manifest": manifest,
        }
    finally:
        con.close()


def run(snapshot_date: str | None = None) -> dict:
    """Full pipeline entry point used from the CLI / app."""
    date = fetch_dump(config.RAW_DIR, snapshot_date)
    return build_curated(config.RAW_DIR, config.CURATED_DIR, date, db_path=str(config.DUCKDB_PATH))


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["manifest"], indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the FULL suite + lint**

Run:
```bash
uv run ruff check .
uv run pytest
```
Expected: Ruff clean; all tests pass; coverage printed for `src/`.

- [ ] **Step 6: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: orchestrate idempotent raw->curated pipeline with validated outputs"
```

---

### Task 13: Live smoke run (real download) — manual checkpoint

**Files:** none (operational verification)

- [ ] **Step 1: Run the real pipeline once**

Run:
```bash
uv run python -m src.pipeline
```
Expected: resolves a real snapshot date, downloads `listings.csv.gz` + `calendar.csv.gz` into `data/raw/`, materializes `raw_*` tables in `data/rio.duckdb`, writes `data/curated/*.parquet` + `manifest.json`, and prints the manifest. If every candidate 404s, update `CANDIDATE_SNAPSHOT_DATES` in `src/config.py` with the date shown for Rio de Janeiro on `https://insideairbnb.com/get-the-data/` and re-run.

- [ ] **Step 2: Sanity-check the curated output in DuckDB**

Run:
```bash
uv run python -c "import duckdb; print(duckdb.sql(\"SELECT neighbourhood, COUNT(*) n, MEDIAN(price) med FROM 'data/curated/listings.parquet' GROUP BY 1 ORDER BY n DESC LIMIT 10\"))"
```
Expected: a sane top-neighbourhoods table (Copacabana / Barra da Tijuca / etc. with plausible median prices).

- [ ] **Step 3: Record the resolved snapshot date**

Read `snapshot_date` from `data/curated/manifest.json` and put it in the README's "Data snapshot" line and the Phase-2 plan header so the analysis is pinned. **Do not commit `data/`** (gitignored); the manifest (with snapshot_date + sha256) is the reproducibility anchor.

> **CHECKPOINT:** Phase 1 is done when CI is green, the live smoke run produces sane curated tables, and (optionally) the author has refined `estimate_occupancy()`. Proceed to detailing Phase 2.

---

## Self-Review (against the spec + plan review)

- **§3 Data source** → Tasks 10–11 (download + materialized raw tables), header-flexible. ✅
- **§4 Architecture (raw→curated, pure transforms, idempotent)** → Tasks 6–9, 11–12; raw layer now persisted via `load_csv_to_duckdb`. ✅
- **§4 calendar in DuckDB** → Task 7 (no 13M-row pandas load). ✅
- **§6 Rigor (winsorize, documented thresholds, occupancy caveat)** → Tasks 6, 8 + `config.py`. ✅
- **§6 schema/grain validation for all curated tables** → Task 9 (listings + occupancy + seasonality contracts), enforced in Task 12. ✅
- **§6/§7 occupancy proxy + estimated_* benchmark** → Task 8 (proxy) + passthrough in Task 6; benchmark comparison lands in Phase 2. ✅
- **§11 author contribution (occupancy blend)** → Task 8 Step 5 (non-blocking refinement over a committed baseline). ✅
- **§8 deliverables (pytest + GitHub Actions)** → Tasks 1–2 + per-task tests. ✅
- **Flexibility proxies replacing cancellation_policy** → Task 6. ✅
- **Reproducibility (manifest: snapshot + timestamp + sha256)** → Tasks 12–13. ✅

Review fixes folded in: pandera `coerce=True` + NA-safe contracts; `estimate_occupancy` NaN-safe + deterministic; raw layer materialized; `reviews` dropped from Phase-1 download; `test_occupancy.py` written up front (no collection-order trap); curated drop removes null neighbourhood/room_type; `download` reads config at call time; `ingest`/`calendar` allow-list table names; CoW-safe test mutation.

Deferred to later phases (correctly out of Phase 1 scope): hedonic model, recommender, EDA notebook, Streamlit app, ground-truth validation narrative, insight-first README, decision report, and `reviews.csv` per-review-date cadence.
