import pandas as pd
import pytest


@pytest.fixture
def raw_listings() -> pd.DataFrame:
    """Tiny raw-listings sample reproducing Inside Airbnb encoding quirks."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "neighbourhood_cleansed": ["Copacabana", "Copacabana", "Leblon", "Centro"],
            "neighbourhood_group_cleansed": [None, None, None, None],
            "latitude": [-22.97, -22.98, -22.98, -22.90],
            "longitude": [-43.18, -43.19, -43.22, -43.18],
            "room_type": ["Entire home/apt", "Private room", "Entire home/apt", "Entire home/apt"],
            "property_type": [
                "Entire rental unit",
                "Private room in home",
                "Entire condo",
                "Entire rental unit",
            ],
            "accommodates": [4, 2, 6, 3],
            "bedrooms": [2, 1, 3, 1],
            "beds": [2, 1, 4, 2],
            "bathrooms": [None, None, None, None],
            "bathrooms_text": ["1 bath", "1 shared bath", "2.5 baths", "Half-bath"],
            "price": ["$500.00", "$150.00", "$1,200.00", None],
            "minimum_nights": [2, 1, 3, 1],
            "host_is_superhost": ["t", "f", "t", None],
            "instant_bookable": ["f", "t", "t", "f"],
            "host_response_time": ["within an hour", "within a day", None, "within a few hours"],
            "host_response_rate": ["100%", "90%", "N/A", None],
            "host_acceptance_rate": ["95%", "80%", "100%", None],
            "number_of_reviews": [120, 10, 45, 0],
            "number_of_reviews_ltm": [30, 4, 12, 0],
            "reviews_per_month": [2.5, 0.3, 1.1, None],
            "review_scores_rating": [4.9, 4.2, 4.7, None],
            "availability_365": [120, 300, 60, 365],
            "last_review": ["2026-05-01", "2026-01-15", "2026-04-20", None],
            "first_review": ["2019-01-01", "2024-06-01", "2021-03-01", None],
        }
    )


@pytest.fixture
def raw_calendar() -> pd.DataFrame:
    """Tiny raw-calendar sample (grain = 1 row per listing-day)."""
    dates = pd.date_range("2026-01-01", periods=5, freq="D").strftime("%Y-%m-%d")
    rows = []
    for lid, avails in [(1, ["t", "f", "f", "t", "f"]), (2, ["t", "t", "t", "f", "t"])]:
        for d, a in zip(dates, avails, strict=True):
            rows.append(
                {
                    "listing_id": lid,
                    "date": d,
                    "available": a,
                    "price": "$500.00",
                    "minimum_nights": 2,
                    "maximum_nights": 365,
                }
            )
    return pd.DataFrame(rows)
