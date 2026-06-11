import pandas as pd

from src.transform.parse_fields import parse_bathrooms, parse_percent, parse_tf_bool


def test_parse_tf_bool_maps_t_f_and_null():
    s = pd.Series(["t", "f", None, "t"])
    result = parse_tf_bool(s)
    assert result.tolist()[:2] == [True, False]
    assert pd.isna(result[2])
    assert bool(result[3]) is True


def test_parse_percent_strips_sign_and_scales():
    s = pd.Series(["100%", "90%", "N/A", None])
    result = parse_percent(s)
    assert result[0] == 1.0
    assert result[1] == 0.9
    assert result[2:].isna().all()


def test_parse_bathrooms_extracts_leading_number():
    s = pd.Series(["1 bath", "1.5 shared baths", "2 baths", "0 baths"])
    result = parse_bathrooms(s)
    assert result.tolist() == [1.0, 1.5, 2.0, 0.0]


def test_parse_bathrooms_handles_half_bath_and_null():
    s = pd.Series(["Half-bath", "Shared half-bath", None, ""])
    result = parse_bathrooms(s)
    assert result[0] == 0.5
    assert result[1] == 0.5
    assert result[2:].isna().all()
