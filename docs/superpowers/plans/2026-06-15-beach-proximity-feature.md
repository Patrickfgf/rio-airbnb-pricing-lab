# Beach-Proximity Feature (Level 1 — offline model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a continuous `distance_to_beach_km` feature to the hedonic model so it captures the *within-neighbourhood* beach-distance price gradient that neighbourhood fixed effects miss.

**Architecture:** Inside Airbnb's raw `latitude`/`longitude` already reach `build_curated_listings` (the ingest does `SELECT *`). We compute `distance_to_beach_km` = haversine distance to the nearest of ~12 Rio beach centroids **in the transform layer**, store only the derived distance in the curated table (lat/long stay in raw/duckdb — curated stays clean), then expose it as one more numeric column in the hedonic design matrix. This is "Level 1" only: it improves the *offline* fit. It does **not** add a location picker to the Streamlit UI (that is Level 2 — deliberately out of scope). The recommender keeps working because `build_model_matrix` median-imputes the new column for user inputs that have no coordinates.

**Tech Stack:** Python · pandas · numpy (haversine, vectorized) · statsmodels (measurement) · pytest · DuckDB-backed pipeline (`python -m src.pipeline`).

**Scope decision (deliberate):** distance is partly collinear with neighbourhood. With `C(neighbourhood)` fixed effects already absorbing the *between*-neighbourhood signal, the new column should carry the *within*-neighbourhood gradient. Task 5 measures the adj-R² delta and the column's VIF so the keep/drop decision is data-driven, not assumed.

**Prerequisites already verified (2026-06-15):** raw dump present (`data/raw/listings.csv.gz`, `data/rio.duckdb`); `src/data/ingest.py` loads all columns as VARCHAR; `src/pipeline.py:62` does `SELECT * FROM raw_listings`, so `raw["latitude"]`/`raw["longitude"]` are available to the transform.

---

## File Structure

- **Create** `src/transform/geo.py` — pure haversine + nearest-beach distance (no I/O).
- **Create** `tests/test_geo.py` — unit tests for the geo helpers.
- **Modify** `src/config.py` — add `RIO_BEACHES` reference coordinates.
- **Modify** `src/transform/listings.py` — add `distance_to_beach_km` to the curated projection.
- **Modify** `src/schemas.py` — add the column to `CURATED_LISTINGS_SCHEMA` (validated-if-present).
- **Modify** `src/model/features.py` — add `distance_to_beach_km` to the numeric block (guarded).
- **Modify** `tests/test_listings.py`, `tests/test_features.py` — cover the new behaviour.
- **Create + delete** `scripts/_measure_beach.py` — throwaway measurement harness (Task 5).
- **Regenerate** `data/curated/listings.parquet` (+ manifest) via the pipeline (Task 5).

---

### Task 1: Beach reference coordinates + haversine distance util

**Files:**
- Modify: `src/config.py` (append after the Phase-2 block, ~line 88)
- Create: `src/transform/geo.py`
- Test: `tests/test_geo.py`

- [ ] **Step 1: Add the beach reference coordinates to config**

Append to `src/config.py`:

```python
# --- Beach-proximity feature (see docs/.../2026-06-15-beach-proximity-feature.md) ---
# Approximate centroids of Rio's main beaches (decimal degrees; lat, lon are negative).
# Precision is not critical: the feature is the haversine distance to the NEAREST of these,
# which is robust to small centroid errors. Refine/add points if a beach is under-covered.
RIO_BEACHES: tuple[tuple[str, float, float], ...] = (
    ("Flamengo", -22.9329, -43.1738),
    ("Botafogo", -22.9530, -43.1810),
    ("Praia Vermelha (Urca)", -22.9555, -43.1650),
    ("Leme", -22.9630, -43.1670),
    ("Copacabana", -22.9711, -43.1822),
    ("Arpoador", -22.9886, -43.1936),
    ("Ipanema", -22.9869, -43.2045),
    ("Leblon", -22.9874, -43.2230),
    ("São Conrado", -23.0106, -43.2680),
    ("Barra da Tijuca", -23.0100, -43.3650),
    ("Recreio dos Bandeirantes", -23.0250, -43.4650),
    ("Grumari", -23.0480, -43.5170),
)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_geo.py`:

```python
import numpy as np

from src.config import RIO_BEACHES
from src.transform.geo import distance_to_nearest_beach_km, haversine_km


def test_haversine_zero_distance_for_same_point():
    assert haversine_km(-22.97, -43.18, -22.97, -43.18) == 0.0


def test_haversine_known_distance_ipanema_to_copacabana():
    # Ipanema -> Copacabana centroid is roughly 2-3 km.
    d = haversine_km(-22.9869, -43.2045, -22.9711, -43.1822)
    assert 1.5 < d < 4.0


def test_distance_to_nearest_beach_zero_on_a_beach_point():
    # A point on Copacabana's centroid is ~0 km from the nearest beach.
    d = distance_to_nearest_beach_km([-22.9711], [-43.1822], RIO_BEACHES)
    assert d[0] < 0.5


def test_distance_to_nearest_beach_grows_inland():
    # Tijuca forest interior (~ -22.95, -43.28) is several km from any beach.
    near = distance_to_nearest_beach_km([-22.9711], [-43.1822], RIO_BEACHES)[0]
    inland = distance_to_nearest_beach_km([-22.9500, ], [-43.2800], RIO_BEACHES)[0]
    assert inland > near


def test_distance_is_nan_when_coords_missing():
    d = distance_to_nearest_beach_km([np.nan], [np.nan], RIO_BEACHES)
    assert np.isnan(d[0])
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_geo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.transform.geo'`.

- [ ] **Step 4: Implement the geo util**

Create `src/transform/geo.py`:

```python
"""Great-circle distance helpers for the beach-proximity feature. Pure functions, no I/O."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Inputs are degrees; accept scalars or numpy arrays.

    NaN inputs propagate to NaN outputs (no special-casing needed)."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype="float64")) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def distance_to_nearest_beach_km(
    lat, lon, beaches: Sequence[tuple[str, float, float]]
) -> np.ndarray:
    """Min haversine distance (km) from each (lat, lon) to any beach centroid.

    `lat`/`lon` are array-like (degrees); `beaches` is a sequence of (name, lat, lon).
    Returns a float64 numpy array aligned to the inputs. NaN coords -> NaN distance."""
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    per_beach = np.stack(
        [haversine_km(lat, lon, blat, blon) for _, blat, blon in beaches], axis=0
    )
    return np.nanmin(per_beach, axis=0)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_geo.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/transform/geo.py tests/test_geo.py
git commit -m "feat(model): add haversine nearest-beach distance util + Rio beach coords"
```

---

### Task 2: Add `distance_to_beach_km` to the curated transform

**Files:**
- Modify: `src/transform/listings.py:27-64` (the curated projection dict)
- Test: `tests/test_listings.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_listings.py` (reuse the module's existing raw-row builder if present; otherwise this self-contained minimal raw row works — it includes every column `build_curated_listings` reads):

```python
import pandas as pd

from src.transform.listings import build_curated_listings


def _raw_row(**overrides):
    base = {
        "id": "1", "neighbourhood_cleansed": "Copacabana", "room_type": "Entire home/apt",
        "property_type": "Entire rental unit", "accommodates": "2", "bedrooms": "1", "beds": "1",
        "bathrooms_text": "1 bath", "price": "$500.00", "minimum_nights": "2",
        "host_is_superhost": "t", "instant_bookable": "f", "host_response_time": "within an hour",
        "host_response_rate": "100%", "host_acceptance_rate": "90%", "number_of_reviews": "10",
        "number_of_reviews_ltm": "5", "reviews_per_month": "1.0", "review_scores_rating": "4.8",
        "availability_365": "100", "last_review": "2026-01-01", "first_review": "2024-01-01",
        "latitude": "-22.9711", "longitude": "-43.1822",
    }
    base.update(overrides)
    return base


def test_curated_listings_has_distance_to_beach():
    raw = pd.DataFrame([_raw_row()])
    curated = build_curated_listings(raw)
    assert "distance_to_beach_km" in curated.columns
    # Copacabana centroid -> ~0 km from nearest beach.
    assert curated["distance_to_beach_km"].iloc[0] < 0.5


def test_curated_distance_larger_for_inland_listing():
    raw = pd.DataFrame([
        _raw_row(id="1", latitude="-22.9711", longitude="-43.1822"),          # on the beach
        _raw_row(id="2", latitude="-22.9500", longitude="-43.2800"),          # inland
    ])
    curated = build_curated_listings(raw).set_index("listing_id")
    assert curated.loc[2, "distance_to_beach_km"] > curated.loc[1, "distance_to_beach_km"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_listings.py::test_curated_listings_has_distance_to_beach -v`
Expected: FAIL — `KeyError: 'distance_to_beach_km'` (column not built yet).

- [ ] **Step 3: Implement — add the column to the projection**

In `src/transform/listings.py`, add the import at the top (after the existing `from src.transform.parse_fields import ...` line):

```python
from src import config
from src.transform.geo import distance_to_nearest_beach_km
```

Then inside `build_curated_listings`, add this key to the dict passed to `pd.DataFrame({...})` (place it right after the `"price": clean_price(raw["price"]),` line so it stays grouped with the listing attributes):

```python
            "distance_to_beach_km": pd.Series(
                distance_to_nearest_beach_km(
                    pd.to_numeric(raw["latitude"], errors="coerce").to_numpy(),
                    pd.to_numeric(raw["longitude"], errors="coerce").to_numpy(),
                    config.RIO_BEACHES,
                ),
                index=raw.index,
            ).astype("float64"),
```

> Alignment note: the array is positionally aligned to `raw` (default RangeIndex), and wrapping it in a `pd.Series(..., index=raw.index)` keeps it aligned through the later `keep` filter + `reset_index`. No separate filtering needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_listings.py -v`
Expected: PASS (existing tests + the 2 new ones).

- [ ] **Step 5: Commit**

```bash
git add src/transform/listings.py tests/test_listings.py
git commit -m "feat(transform): compute distance_to_beach_km in curated listings"
```

---

### Task 3: Add the column to the curated schema contract

**Files:**
- Modify: `src/schemas.py:23-40` (`CURATED_LISTINGS_SCHEMA`)
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_schemas.py`:

```python
import pandas as pd

from src.schemas import CURATED_LISTINGS_SCHEMA, validate_curated_listings


def test_schema_accepts_distance_to_beach_column():
    df = pd.DataFrame(
        {
            "listing_id": pd.Series([1], dtype="int64"),
            "neighbourhood": pd.Series(["Copacabana"], dtype="string"),
            "room_type": pd.Series(["Entire home/apt"], dtype="string"),
            "price": pd.Series([500.0], dtype="float64"),
            "distance_to_beach_km": pd.Series([0.2], dtype="float64"),
        }
    )
    out = validate_curated_listings(df)  # must not raise
    assert "distance_to_beach_km" in out.columns


def test_schema_rejects_negative_distance():
    df = pd.DataFrame(
        {
            "listing_id": pd.Series([1], dtype="int64"),
            "neighbourhood": pd.Series(["Copacabana"], dtype="string"),
            "room_type": pd.Series(["Entire home/apt"], dtype="string"),
            "price": pd.Series([500.0], dtype="float64"),
            "distance_to_beach_km": pd.Series([-1.0], dtype="float64"),
        }
    )
    import pytest

    with pytest.raises(Exception):
        validate_curated_listings(df)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_schemas.py::test_schema_rejects_negative_distance -v`
Expected: FAIL — no `distance_to_beach_km` rule exists yet, so the negative value is not rejected (the `pytest.raises` block fails).

- [ ] **Step 3: Implement — add the column rule**

In `src/schemas.py`, add this entry to the `CURATED_LISTINGS_SCHEMA` column dict (after the `"review_scores_rating"` line). `required=False` keeps existing fixtures/tests that omit the column valid; `nullable=True` tolerates listings with missing coords:

```python
        "distance_to_beach_km": Column(
            "float64", Check.ge(0), nullable=True, required=False
        ),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/schemas.py tests/test_schemas.py
git commit -m "feat(schema): contract distance_to_beach_km (validated-if-present, >=0)"
```

---

### Task 4: Expose the feature in the hedonic design matrix (guarded)

**Files:**
- Modify: `src/model/features.py:52-59` (the `numeric` block)
- Test: `tests/test_features.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_features.py` (reuse the module's existing curated-listings fixture if one exists — call it `listings`/`curated_listings` as that file already does; the assertion is fixture-agnostic):

```python
def test_distance_to_beach_enters_design_matrix(curated_listings):
    # curated_listings: the existing fixture in this module. Ensure it carries the column.
    df = curated_listings.assign(distance_to_beach_km=1.0)
    X, _y, _meta = build_model_matrix(df)
    assert "distance_to_beach_km" in X.columns
    assert X["distance_to_beach_km"].notna().all()  # median-imputed, never NaN in the design


def test_build_matrix_works_without_distance_column(curated_listings):
    # Guard: callers (e.g. the live recommender's user input) may lack the column.
    df = curated_listings.drop(columns=["distance_to_beach_km"], errors="ignore")
    X, _y, _meta = build_model_matrix(df)  # must not raise
    assert "distance_to_beach_km" not in X.columns
```

> If `test_features.py` has no shared fixture, copy the raw→curated construction it already uses, or build a small curated frame inline with the columns `build_model_matrix` reads (`price, room_type, property_type, accommodates, bedrooms, bathrooms_num, min_nights, host_is_superhost, number_of_reviews, neighbourhood`).

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_features.py::test_distance_to_beach_enters_design_matrix -v`
Expected: FAIL — column not added to `X` yet.

- [ ] **Step 3: Implement — add the guarded numeric column**

In `src/model/features.py`, inside `build_model_matrix`, replace the `numeric = pd.DataFrame({...})` construction (lines ~52-59) so the new column is included only when present (keeps the live recommender working for user inputs that have no coordinates — they get median-imputed):

```python
    numeric_cols = {
        "accommodates": _to_float64(df["accommodates"]),
        "bedrooms": _to_float64(df["bedrooms"]),
        "bathrooms_num": _to_float64(df["bathrooms_num"]),
        "min_nights": _to_float64(df["min_nights"]),
    }
    if "distance_to_beach_km" in df.columns:
        numeric_cols["distance_to_beach_km"] = _to_float64(df["distance_to_beach_km"])
    numeric = pd.DataFrame(numeric_cols)
```

> The existing `numeric.fillna(numeric.median(...))` line right below handles imputation, so a user input with a NaN/absent distance gets the market-median distance. The all-NULL guard below it still applies.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_features.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/model/features.py tests/test_features.py
git commit -m "feat(model): add distance_to_beach_km to hedonic design matrix (guarded)"
```

---

### Task 5: Regenerate curated data + measure the adj-R² delta and VIF (decision gate)

**Files:**
- Regenerate: `data/curated/listings.parquet`, `data/curated/manifest.json`
- Create (throwaway): `scripts/_measure_beach.py`

- [ ] **Step 1: Regenerate the curated tables from the local raw dump**

Run: `uv run python -m src.pipeline`
Expected: completes without error; `data/curated/listings.parquet` mtime updates and now contains `distance_to_beach_km`.

Verify the column landed:

```bash
uv run python -c "import pandas as pd; df=pd.read_parquet('data/curated/listings.parquet'); print(df['distance_to_beach_km'].describe())"
```
Expected: a sane distribution (min ~0, median a few km, no all-NaN).

- [ ] **Step 2: Write the throwaway measurement harness**

Create `scripts/_measure_beach.py`:

```python
"""Throwaway: quantify the beach-distance feature's lift. Delete after recording numbers."""

import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from src.model.features import build_model_matrix

listings = pd.read_parquet("data/curated/listings.parquet")
X, y, meta = build_model_matrix(listings)


def fit(design_X):
    d = design_X.copy()
    d["neighbourhood"] = meta.neighbourhood.values
    d = pd.get_dummies(d, columns=["neighbourhood"], drop_first=True).astype(float)
    d = sm.add_constant(d, has_constant="add")
    return sm.OLS(y.values, d.values).fit(), d.columns

res_with, cols = fit(X)
res_base, _ = fit(X.drop(columns=["distance_to_beach_km"], errors="ignore"))
print(f"adj R2 WITHOUT distance: {res_base.rsquared_adj:.4f}")
print(f"adj R2 WITH    distance: {res_with.rsquared_adj:.4f}")
print(f"delta adj R2           : {res_with.rsquared_adj - res_base.rsquared_adj:+.4f}")

coef = dict(zip(cols, res_with.params))
print(f"distance_to_beach_km coef (log-price/km): {coef.get('distance_to_beach_km', float('nan')):+.5f}")

num = ["accommodates", "bedrooms", "bathrooms_num", "min_nights", "distance_to_beach_km"]
vif_in = X[num].astype(float)
for i, c in enumerate(num):
    print(f"VIF {c:>22}: {variance_inflation_factor(vif_in.values, i):.2f}")
```

- [ ] **Step 3: Run the measurement and record the output**

Run: `uv run python scripts/_measure_beach.py`
Expected output shape (numbers are what you record — baseline adj-R² was ~0.52):

```
adj R2 WITHOUT distance: 0.5XXX
adj R2 WITH    distance: 0.5XXX
delta adj R2           : +0.0XXX
distance_to_beach_km coef (log-price/km): -0.0XXXX
VIF   distance_to_beach_km: X.XX
```

**Decision gate — interpret before continuing:**
- **Sign sanity:** the coefficient should be **negative** (farther from beach → lower log-price). A positive sign means the centroid set or alignment is wrong — stop and recheck Task 2.
- **VIF:** `distance_to_beach_km` VIF should be **< 5** (ideally < 3). If it is high, distance is too collinear with the neighbourhood FE to identify cleanly — note it and consider dropping (the FE already carry most of the signal).
- **Lift:** if `delta adj R2` is meaningfully positive (rule of thumb **> +0.005**), keep the feature. If it is ~0 and VIF is high, the honest outcome is "the FE already captured it" — still a valid finding; record it and proceed to Task 6 either keeping or reverting the feature based on this evidence.

- [ ] **Step 4: Delete the throwaway script**

```bash
rm scripts/_measure_beach.py
```

- [ ] **Step 5: Commit the regenerated data + the recorded numbers**

```bash
git add data/curated/listings.parquet data/curated/manifest.json
git commit -m "data: regenerate curated listings with distance_to_beach_km

adj R2: 0.52 -> 0.XX (delta +0.0XX); distance coef -0.0XX log-price/km; VIF X.X.
<one line: kept / reverted and why, per the Task 5 decision gate>"
```

---

### Task 6: Full verification + finalize

**Files:** none (verification) — plus conditional doc updates flagged below.

- [ ] **Step 1: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 2: Full test suite**

Run: `uv run pytest -q`
Expected: all green (the original 91 + the new tests), coverage still ≥ ~90%.

- [ ] **Step 3: Smoke-test the live recommender path (no UI change, must still work)**

Run: `uv run python -c "import pandas as pd; from src.model.service import recommend; print('service import OK')"`
> If the public entry point is named differently, open `tests/test_service.py` for the exact call and run that test:
Run: `uv run pytest tests/test_service.py -v`
Expected: PASS — confirms the recommender still builds a recommendation for a user input that carries **no** coordinates (distance is median-imputed).

- [ ] **Step 4: Boot the dashboard once (manual sanity)**

Run: `uv run streamlit run app/streamlit_app.py`
Expected: the Recommend tab returns a price range with no error; Ctrl-C to stop.

- [ ] **Step 5 (conditional): update the documented adj-R² if it moved**

If Task 5 changed adj-R² materially from **0.52**, update the figure wherever it is asserted as a finding:
- `README.md` and `README.pt-BR.md` — the "Adjusted R² ≈ 0.52" / "R² ajustado ≈ 0,52" bullets.
- `reports/decision_report.md` if it cites the figure.
- `notebooks/eda.ipynb` — re-run `Restart & Run All` (Task done previously) only if the notebook reports the model fit; otherwise leave it.

```bash
git add README.md README.pt-BR.md reports/decision_report.md
git commit -m "docs: update adj-R2 after adding beach-distance feature"
```

- [ ] **Step 6 (optional, recommended for the portfolio): surface the new driver**

Add one line to the README "Key findings" / "Principais achados" noting the beach-distance effect (e.g. "Each km from the nearest beach ≈ −X% within a neighbourhood"), using the coefficient from Task 5. Keep it honest (it's a within-neighbourhood gradient). Commit with the docs above.

---

## Self-Review notes (for the executor)

- **No UI/location input** is added — that is Level 2 and explicitly out of scope. The recommender keeps working via median imputation (Task 4 guard + Task 6 Step 3 verify this).
- **Collinearity is checked, not assumed** (Task 5 VIF gate). It is a legitimate outcome to *revert* the feature if the FE already absorbed it — record the numbers either way.
- **Curated parquet is committed** (the app/notebook boot from it), so Task 5 must regenerate and commit it; otherwise the live app and the fitted model disagree.
- **`required=False`** on the schema column is intentional so existing test fixtures that omit it still validate; tighten to `required=True` later once `tests/conftest.py` fixtures include the column.
