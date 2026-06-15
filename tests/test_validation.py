import warnings

import numpy as np
import pandas as pd
import pytest

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


def test_length_mismatch_raises():
    with pytest.raises(ValueError, match="length mismatch"):
        occupancy_agreement(pd.Series([0.1, 0.2]), pd.Series([0.1]))


def test_structural_zero_cohort_reports_none_pearson():
    # an all-zero (constant) cohort has undefined correlation; report None deliberately, not a NaN
    # that reads like a real coefficient (and emit no ConstantInputWarning).
    z = pd.Series([0.0] * 50)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any numpy correlation warning would fail the test
        rep = occupancy_agreement(proxy=z, benchmark=z.copy())
    assert rep.structural_zero_frac == 1.0
    assert rep.pearson is None and rep.spearman is None
    assert rep.mae == 0.0
