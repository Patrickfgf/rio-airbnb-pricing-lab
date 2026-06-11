"""End-to-end pipeline: download -> raw layer -> curated -> validate -> write.

Idempotent: same dump in -> identical curated out. Records the resolved snapshot,
a run timestamp, and per-file checksums in a versioned manifest.json.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
            "generated_at": datetime.now(UTC).isoformat(),
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
