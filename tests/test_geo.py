import numpy as np
from src.transform.geo import distance_to_nearest_beach_km, haversine_km

from src.config import RIO_BEACHES


def test_haversine_zero_distance_for_same_point():
    assert haversine_km(-22.97, -43.18, -22.97, -43.18) == 0.0


def test_haversine_known_distance_ipanema_to_copacabana():
    # Ipanema -> Copacabana centroid is roughly 2-3 km.
    d = haversine_km(-22.9869, -43.2045, -22.9711, -43.1822)
    assert 1.5 < d < 4.0


def test_distance_to_nearest_beach_zero_on_a_beach_point():
    # A point on Copacabana's centroid is ~0 km from the nearest beach.
    d = distance_to_nearest_beach_km([-22.9711], [-43.1822], RIO_BEACHES)
    assert d[0] < 0.5


def test_distance_to_nearest_beach_grows_inland():
    # Tijuca forest interior (~ -22.95, -43.28) is several km from any beach.
    near = distance_to_nearest_beach_km([-22.9711], [-43.1822], RIO_BEACHES)[0]
    inland = distance_to_nearest_beach_km([-22.9500], [-43.2800], RIO_BEACHES)[0]
    assert inland > near


def test_distance_is_nan_when_coords_missing():
    d = distance_to_nearest_beach_km([np.nan], [np.nan], RIO_BEACHES)
    assert np.isnan(d[0])
