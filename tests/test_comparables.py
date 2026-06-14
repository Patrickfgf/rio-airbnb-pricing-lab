import numpy as np
import pandas as pd

from src.model.comparables import peer_positioning


def _market(n_dense=200):

    rng = np.random.default_rng(7)
    dense = pd.DataFrame(
        {
            "listing_id": range(n_dense),
            "price": rng.normal(500, 100, n_dense).clip(50),
            "neighbourhood": "Copacabana",
            "room_type": "Entire home/apt",
            "cap_bucket": "3-4",
        }
    )
    thin = pd.DataFrame(
        {
            "listing_id": [9001, 9002],
            "price": [3000.0, 50.0],
            "neighbourhood": "Copacabana",
            "room_type": "Entire home/apt",
            "cap_bucket": "7+",
        }
    )
    return pd.concat([dense, thin], ignore_index=True)


def test_percentile_in_dense_slice():
    m = _market()
    target = m.iloc[0]
    out = peer_positioning(target, m)
    assert 0.0 <= out.price_percentile <= 1.0
    assert out.tier_used == ("neighbourhood", "room_type", "cap_bucket")
    assert out.n_effective >= 100


def test_thin_slice_shrinks_toward_parent():
    m = _market()
    thin_target = m[m["listing_id"] == 9001].iloc[0]  # price 3000 in a 2-row slice
    out = peer_positioning(thin_target, m)
    # raw slice median would be 1525; shrunk toward the ~500 parent median must be far lower
    assert out.shrunk_median < 1200
    assert out.cv is not None


def test_single_row_final_tier_cv_is_none():
    # a listing whose room_type is unique market-wide: every tier has n<=1 and the final
    # (room_type,) tier has exactly 1 row, so std() is NaN -> cv must be None (float|None contract).
    m = _market()
    solo = pd.DataFrame(
        {
            "listing_id": [7777],
            "price": [800.0],
            "neighbourhood": "Lapa",
            "room_type": "Shared room",
            "cap_bucket": "5-6",
        }
    )
    m2 = pd.concat([m, solo], ignore_index=True)
    out = peer_positioning(m2[m2["listing_id"] == 7777].iloc[0], m2)
    assert out.n_effective == 1
    assert out.cv is None
    assert out.tier_used == ("room_type",)


def test_unseen_keys_fall_through_to_zero_peer_sentinel():
    # an unseen room_type at predict time matches no tier -> the structural no-signal sentinel
    m = _market()
    target = pd.Series(
        {
            "listing_id": 8888,
            "price": 600.0,
            "neighbourhood": "Nowhere",
            "room_type": "Castle",
            "cap_bucket": "9-10",
        }
    )
    out = peer_positioning(target, m)
    assert out.n_effective == 0
    assert out.cv is None
    assert out.price_percentile == 0.5  # neutral placeholder, NOT a real position


def test_nan_target_key_coarsens_observably():
    # a NaN tier key (cap_bucket) empties the finest slices (NaN != NaN); the answer comes from a
    # coarser tier, observable via tier_used rather than silently wrong.
    m = _market()
    target = m.iloc[0].copy()
    target["cap_bucket"] = np.nan
    out = peer_positioning(target, m)
    assert "cap_bucket" not in out.tier_used
    assert out.n_effective >= 1
