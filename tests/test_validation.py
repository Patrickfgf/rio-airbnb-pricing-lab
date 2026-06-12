import numpy as np
import pandas as pd

from src.model.validation import occupancy_agreement


def test_perfect_agreement_zero_error():
    x = pd.Series(np.linspace(0.05, 0.6, 100))
    rep = occupancy_agreement(proxy=x, benchmark=x.copy())
    assert rep.mae < 1e-9 and abs(rep.pearson - 1.0) < 1e-9


def test_known_offset_and_structural_zeros():
    proxy = pd.Series([0.3] * 80 + [0.0] * 20)
    bench = pd.Series([0.2] * 80 + [0.0] * 20)
    rep = occupancy_agreement(proxy, bench)
    assert abs(rep.bias - 0.08) < 1e-6  # mean(proxy-bench) over all 100
    assert abs(rep.structural_zero_frac - 0.20) < 1e-6
    assert rep.shared_input_warning is True
