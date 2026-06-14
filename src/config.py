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
# 2026-03-30 confirmed live on insideairbnb.com/get-the-data (HTTP 200). The
# data.insideairbnb.com S3 bucket returns 403 (AccessDenied), not 404, for keys
# that don't exist, so unverified guesses below are harmless fallbacks only.
CANDIDATE_SNAPSHOT_DATES: tuple[str, ...] = (
    "2026-03-30",
    "2025-12-20",
    "2025-09-29",
    "2025-06-23",
)

# --- Documented analysis thresholds (see spec section 6: bias mitigation) ---
PRICE_WINSOR_LOWER_Q = 0.01  # clip extreme low prices (data-entry noise)
PRICE_WINSOR_UPPER_Q = 0.99  # clip extreme high prices (luxury outliers)

# --- Occupancy proxy (San Francisco Model) constants (see occupancy.py) ---
SF_REVIEW_RATE = 0.5  # fraction of stays that leave a review (Inside Airbnb assumption)
SF_AVG_LENGTH_OF_STAY = 4.0  # nights; Rio-tunable in Phase 2 from data
SF_MAX_OCCUPANCY = 0.70  # cap to avoid implausible >70% annual occupancy

# --- Phase 2: model feature governance (see docs/.../2026-06-12-phase2-positioning-advisor.md) ---
# Columns excluded from the hedonic feature matrix.
MODEL_DROP_ALL_NULL = (  # 100% null in the Rio 2026-03-30 dump (source reality)
    "instant_bookable",
    "host_response_time",
    "host_response_rate",
    "host_acceptance_rate",
)
MODEL_DROP_LEAKAGE = (  # outcomes / forward-looking -- never predict price with these
    "availability_365",
    "estimated_occupancy_l365d",
    "estimated_revenue_l365d",
)
MODEL_DROP_COLLINEAR = ("beds",)  # net coef sign-flips (-0.025, p~0); +0.002 adjR2 only
MIN_NEIGHBOURHOOD_N = 30  # neighbourhoods with fewer listings are pooled to "Other"
PROPERTY_TYPE_TOP_K = 8  # keep top-K property_type levels, collapse the rest to "Other"
# Comparable-set hierarchy, widest-last; each tier is a tuple of grouping columns.
COMPARABLE_TIERS = (
    ("neighbourhood", "room_type", "cap_bucket"),
    ("neighbourhood", "room_type"),
    ("room_type", "cap_bucket"),
    ("room_type",),
)
SHRINKAGE_PRIOR_STRENGTH = 30.0  # pseudo-count m: slice mean shrinks toward parent by n/(n+m)
MIN_TIER_N = 30  # min peers to accept a comparable tier before widening (distinct from m above)
CAP_BUCKET_EDGES = (0, 2, 4, 6, 999)  # accommodates -> 1-2, 3-4, 5-6, 7+
CAP_BUCKET_LABELS = ("1-2", "3-4", "5-6", "7+")

# --- Phase 2: positioning policy (recommender.py) — author-tunable knobs ---
HEDONIC_MARKET_BLEND_WEIGHT = 0.5  # anchor = w*hedonic_point + (1-w)*peer_median
BAND_IQR_FRACTION = 0.5  # half-band width as a fraction of the peer IQR
ANCHOR_FLOOR_FRACTION = 0.5  # never let `low` fall below this fraction of the anchor
POSITION_BELOW_PCTL = 0.33  # price_percentile < this -> "below market"
POSITION_ABOVE_PCTL = 0.66  # price_percentile > this -> "above market"
