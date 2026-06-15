"""Great-circle distance helpers for the beach-proximity feature. Pure functions, no I/O."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Inputs are degrees; accept scalars or numpy arrays.

    NaN inputs propagate to NaN outputs (no special-casing needed)."""
    lat1, lon1, lat2, lon2 = (
        np.radians(np.asarray(v, dtype="float64")) for v in (lat1, lon1, lat2, lon2)
    )
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
    per_beach = np.stack([haversine_km(lat, lon, blat, blon) for _, blat, blon in beaches], axis=0)
    return np.nanmin(per_beach, axis=0)
