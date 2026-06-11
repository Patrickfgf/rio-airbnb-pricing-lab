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
        prices.astype("string").str.replace(r"[$,]", "", regex=True).str.strip().replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")
