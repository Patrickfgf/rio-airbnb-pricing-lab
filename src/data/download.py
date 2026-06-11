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
