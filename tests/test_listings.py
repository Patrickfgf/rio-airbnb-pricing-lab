from src.transform.listings import build_curated_listings


def test_types_and_core_columns(raw_listings):
    out = build_curated_listings(raw_listings)
    assert out["price"].dtype.kind == "f"
    assert out["host_is_superhost"].dtype == "boolean"
    assert out["bathrooms_num"].tolist()[:3] == [1.0, 1.0, 2.5]
    assert {
        "listing_id",
        "neighbourhood",
        "room_type",
        "accommodates",
        "price",
        "host_is_superhost",
        "instant_bookable",
        "min_nights",
        "bathrooms_num",
        "number_of_reviews_ltm",
    }.issubset(out.columns)


def test_drops_rows_without_usable_price(raw_listings):
    # id=4 has price None -> dropped. The filter also drops price <= 0 and rows
    # with null neighbourhood/room_type (can't place them in a comparable set).
    out = build_curated_listings(raw_listings)
    assert 4 not in out["listing_id"].tolist()
    assert len(out) == 3


def test_percent_columns_scaled(raw_listings):
    out = build_curated_listings(raw_listings)
    row = out.loc[out["listing_id"] == 1].iloc[0]
    assert row["host_response_rate"] == 1.0
    assert row["host_acceptance_rate"] == 0.95


def test_winsorize_clips_extremes_to_quantile_bounds(raw_listings):
    # On the 3 priced rows [150, 500, 1200], winsorize at q=[0.01, 0.99] is NOT a
    # no-op: pandas' linear interpolation puts the 1st pct at 150+0.02*(500-150)=157
    # and the 99th at 500+0.98*(1200-500)=1186. So the extremes are pulled in and the
    # median is untouched. On the real (n=thousands) dataset this barely moves values.
    out = build_curated_listings(raw_listings)
    prices = sorted(out["price"].tolist())
    assert prices[1] == 500.0  # median untouched
    assert prices == [157.0, 500.0, 1186.0]


def test_estimated_columns_passthrough_when_present(raw_listings):
    df = raw_listings.copy()
    df["estimated_occupancy_l365d"] = [200, 50, 150, 0]
    out = build_curated_listings(df)
    assert "estimated_occupancy_l365d" in out.columns


def test_no_estimated_columns_when_absent(raw_listings):
    out = build_curated_listings(raw_listings)
    assert "estimated_occupancy_l365d" not in out.columns
