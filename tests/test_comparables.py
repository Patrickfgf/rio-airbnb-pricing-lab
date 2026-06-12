import pandas as pd

from src.model.comparables import peer_positioning


def _market(n_dense=200):
    import numpy as np

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
