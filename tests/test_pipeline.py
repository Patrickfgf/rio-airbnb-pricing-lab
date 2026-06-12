import gzip
from pathlib import Path

import pandas as pd

import src.pipeline as pipeline


def _gz(path: Path, df: pd.DataFrame) -> None:
    # newline="" stops the text layer from translating the csv module's \r\n into
    # \r\r\n on Windows (which would inject blank lines and break DuckDB's reader).
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
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
    assert {"listing_id", "month", "dow", "median_cal_price", "booked_rate"}.issubset(
        season.columns
    )

    assert curated["manifest"]["snapshot_date"] == "2026-03-31"
    assert curated["manifest"]["n_listings"] == 3  # id=4 dropped (no price)
    assert "generated_at" in curated["manifest"]
    assert "listings.csv.gz" in curated["manifest"]["raw_files"]


def test_idempotent_curated(tmp_path, raw_listings, raw_calendar):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _gz(raw_dir / "listings.csv.gz", raw_listings)
    _gz(raw_dir / "calendar.csv.gz", raw_calendar)
    a = pipeline.build_curated(
        raw_dir=raw_dir, curated_dir=tmp_path / "c1", snapshot_date="2026-03-31"
    )
    b = pipeline.build_curated(
        raw_dir=raw_dir, curated_dir=tmp_path / "c2", snapshot_date="2026-03-31"
    )
    df_a = pd.read_parquet(tmp_path / "c1" / "listings.parquet")
    df_b = pd.read_parquet(tmp_path / "c2" / "listings.parquet")
    pd.testing.assert_frame_equal(df_a, df_b)
    assert a["manifest"]["n_listings"] == b["manifest"]["n_listings"]


def test_build_curated_writes_detrended_seasonality(tmp_path, raw_listings, raw_calendar):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _gz(raw_dir / "listings.csv.gz", raw_listings)
    _gz(raw_dir / "calendar.csv.gz", raw_calendar)

    curated = pipeline.build_curated(
        raw_dir=raw_dir, curated_dir=tmp_path / "curated", snapshot_date="2026-03-31"
    )
    parquet = tmp_path / "curated" / "calendar_seasonality_detrended.parquet"
    assert parquet.exists()

    detrended = pd.read_parquet(parquet)
    expected_cols = {
        "date",
        "dow",
        "horizon_days",
        "unavail_rate",
        "baseline",
        "event_uplift",
        "is_edge",
    }
    assert expected_cols.issubset(detrended.columns)
    # raw_calendar fixture has 5 distinct dates; grain collapses to 1 row/date.
    assert len(detrended) == detrended["date"].nunique() == 5
    assert curated["manifest"]["n_seasonality_detrended_rows"] == 5


def test_idempotent_detrended_seasonality(tmp_path, raw_listings, raw_calendar):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _gz(raw_dir / "listings.csv.gz", raw_listings)
    _gz(raw_dir / "calendar.csv.gz", raw_calendar)
    pipeline.build_curated(raw_dir=raw_dir, curated_dir=tmp_path / "c1", snapshot_date="2026-03-31")
    pipeline.build_curated(raw_dir=raw_dir, curated_dir=tmp_path / "c2", snapshot_date="2026-03-31")
    df_a = pd.read_parquet(tmp_path / "c1" / "calendar_seasonality_detrended.parquet")
    df_b = pd.read_parquet(tmp_path / "c2" / "calendar_seasonality_detrended.parquet")
    pd.testing.assert_frame_equal(df_a, df_b)
