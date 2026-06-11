"""Resolve the latest Inside Airbnb Rio snapshot and download the dump files.

Defeats data.insideairbnb.com's 403 anti-hotlinking with a browser User-Agent
and a Referer header. The snapshot date is resolved at runtime (no hardcoding).
"""

from __future__ import annotations

import re
from pathlib import Path

import requests

from src import config

_HEADERS = {"User-Agent": config.BROWSER_USER_AGENT, "Referer": config.DATA_REFERER}

# Validate inputs at the boundary: date must be an ISO YYYY-MM-DD and file must be
# one of the known dump files. build_url is the single choke point where date+file
# become a URL, so guarding here defends every caller (resolve/download/manifest)
# against SSRF or path-breakout if a future caller passes user-controlled input.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Hard ceiling on a single download so a malicious/corrupt server response cannot
# exhaust the disk. The full Rio calendar dump is ~40 MB gzipped; 2 GB is generous.
MAX_DOWNLOAD_BYTES = 2 * 1024**3


def build_url(date: str, file: str) -> str:
    if not _DATE_RE.match(date):
        raise ValueError(f"Invalid snapshot date (expected YYYY-MM-DD): {date!r}")
    if file not in config.DUMP_FILES:
        raise ValueError(f"Unknown dump file: {file!r} (allowed: {config.DUMP_FILES})")
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
    """Stream a file to disk using browser headers (avoids 403).

    Writes to a temporary sibling and renames on success so an interrupted
    download never leaves a truncated file that a later run would treat as
    complete. Aborts if the response exceeds MAX_DOWNLOAD_BYTES.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    resp = requests.get(url, headers=_HEADERS, timeout=120, stream=True)
    resp.raise_for_status()
    received = 0
    with tmp.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if not chunk:
                continue
            received += len(chunk)
            if received > MAX_DOWNLOAD_BYTES:
                fh.close()
                tmp.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Download exceeded {MAX_DOWNLOAD_BYTES} bytes — aborting: {url}"
                )
            fh.write(chunk)
    tmp.replace(dest)
    return dest
