"""Parse Inside Airbnb's quirky encodings: 't'/'f' booleans, '95%' strings,
and free-text bathrooms ('1.5 shared baths', 'Half-bath')."""

from __future__ import annotations

import pandas as pd


def parse_tf_bool(series: pd.Series) -> pd.Series:
    """Map 't'/'f' strings to nullable boolean (pd.NA for anything else)."""
    return series.map({"t": True, "f": False}).astype("boolean")


def parse_percent(series: pd.Series) -> pd.Series:
    """Convert '95%' strings to 0.95 floats; 'N/A'/blank/None -> NaN."""
    cleaned = series.astype("string").str.replace("%", "", regex=False).str.strip()
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
