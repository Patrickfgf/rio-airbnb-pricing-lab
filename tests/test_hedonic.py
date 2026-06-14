import numpy as np
import pandas as pd

from src.model.hedonic import compute_vif, fit_hedonic


def test_recovers_known_relationship():
    rng = np.random.default_rng(1)
    n = 500
    accommodates = rng.integers(1, 8, n)
    nb = rng.choice(["A", "B"], n)
    y = 5.0 + 0.25 * accommodates + (nb == "B") * 0.4 + rng.normal(0, 0.1, n)
    X = pd.DataFrame({"accommodates": accommodates})
    res = fit_hedonic(X, pd.Series(y, name="log_price"), pd.Series(nb, name="nb"))
    assert abs(res.coefs.loc["accommodates", "effect"] - 0.25) < 0.05
    assert res.coefs.loc["accommodates", "p_value"] < 0.01
    assert res.adj_r2 > 0.9


def test_beats_trivial_baseline():
    rng = np.random.default_rng(2)
    n = 400
    acc = rng.integers(1, 8, n)
    nb = rng.choice(["A", "B"], n)
    # real neighbourhood effect AND accommodates effect; the FE-only median baseline ignores
    # accommodates, so a useful model must beat it — not just the weak global median.
    y = 5 + 0.3 * acc + (nb == "B") * 0.5 + rng.normal(0, 0.2, n)
    res = fit_hedonic(
        pd.DataFrame({"accommodates": acc}),
        pd.Series(y, name="log_price"),
        pd.Series(nb, name="nb"),
    )
    assert res.model_mae < res.baseline_median_mae
    assert res.model_mae < res.baseline_nb_median_mae  # must beat the per-neighbourhood median too


def test_vif_flags_collinear_pair():
    rng = np.random.default_rng(3)
    a = rng.normal(0, 1, 300)
    X = pd.DataFrame({"a": a, "a_copy": a + rng.normal(0, 1e-3, 300), "b": rng.normal(0, 1, 300)})
    vif = compute_vif(X)
    assert vif.loc["a"] > 10 and vif.loc["b"] < 5


def test_neighbourhood_series_name_agnostic():
    # production passes a Series named "neighbourhood", not "nb"; the FE encoder must not care
    rng = np.random.default_rng(4)
    n = 200
    acc = rng.integers(1, 6, n)
    nb = pd.Series(rng.choice(["X", "Y", "Z"], n), name="neighbourhood")
    y = pd.Series(5 + 0.2 * acc + rng.normal(0, 0.1, n), name="log_price")
    res = fit_hedonic(pd.DataFrame({"accommodates": acc}), y, nb)
    assert "accommodates" in res.coefs.index
    assert res.adj_r2 > 0.0
