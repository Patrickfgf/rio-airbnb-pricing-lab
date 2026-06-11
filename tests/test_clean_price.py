import numpy as np
import pandas as pd

from src.transform.clean_price import clean_price


def test_strips_dollar_and_thousands_comma():
    s = pd.Series(["$1,200.00", "$75.00", "$0.00"])
    result = clean_price(s)
    assert result.tolist() == [1200.0, 75.0, 0.0]


def test_handles_missing_and_blank_as_nan():
    s = pd.Series(["$50.00", None, "", np.nan])
    result = clean_price(s)
    assert result[0] == 50.0
    assert result[1:].isna().all()


def test_returns_float_dtype():
    result = clean_price(pd.Series(["$10.00"]))
    assert result.dtype == np.float64
