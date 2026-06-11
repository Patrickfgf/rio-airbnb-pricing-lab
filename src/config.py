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
