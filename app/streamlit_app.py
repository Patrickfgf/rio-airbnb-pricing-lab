"""Rio Airbnb Pricing Lab — a thin Streamlit UI over ``src.model.service``.

Every number on screen comes from ``recommend()`` / ``fit_advisor()``; this file holds ZERO business
logic (spec section 4). Its only jobs are: load the curated parquets, fit the advisor once, collect
host input, and render the service's honest output (a price RANGE, peer position, drivers, demand
context, and caveats) plus a few market-context charts straight off the curated data.

Run with::

    uv run --extra app streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# The app lives in app/; the package lives at the repo root. Make ``src`` importable when Streamlit
# launches this file directly (its cwd/argv[0] is the file, not the project root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import CURATED_DIR  # noqa: E402
from src.model.service import (  # noqa: E402
    FittedAdvisor,
    HostInput,
    ListingAdvice,
    fit_advisor,
    recommend,
)

# --- Snapshot facts (display only; the model derives every number itself) ---
SNAPSHOT_DATE = "2026-03-30"
ADJ_R2 = 0.52
CURRENCY = "BRL"

# Real top neighbourhoods by listing count (drives the selectbox; free-text fallback below).
TOP_NEIGHBOURHOODS = (
    "Copacabana",
    "Ipanema",
    "Barra da Tijuca",
    "Centro",
    "Recreio dos Bandeirantes",
    "Botafogo",
)
ROOM_TYPES = ("Entire home/apt", "Private room", "Shared room", "Hotel room")
# Common Rio property types; the model collapses anything outside its top-K to "Other" internally.
PROPERTY_TYPES = (
    "Entire rental unit",
    "Entire condo",
    "Entire serviced apartment",
    "Private room in rental unit",
    "Entire home",
    "Entire loft",
    "Room in hotel",
    "Other",
)

# Friendly labels for raw hedonic feature names (one-hot dummies + numeric columns). Anything not
# mapped falls back to a title-cased, de-underscored version, so a new feature never renders as a
# raw key — it just looks slightly less polished.
_DRIVER_LABELS = {
    "bathrooms_num": "Bathrooms",
    "bedrooms": "Bedrooms",
    "beds": "Beds",
    "accommodates": "Guests it sleeps",
    "min_nights": "Minimum nights",
    "number_of_reviews": "Number of reviews",
    "host_is_superhost": "Superhost status",
    "superhost_missing": "Superhost field missing",
    "no_review_history": "No review history (new listing)",
    "room_type_Private room": "Private room",
    "room_type_Shared room": "Shared room",
    "room_type_Hotel room": "Hotel room",
    "room_type_Entire home/apt": "Entire home/apt",
}

_FREE_TEXT_OPTION = "Other (type below)…"

st.set_page_config(
    page_title="Rio Airbnb Pricing Lab",
    page_icon="🏖️",
    layout="wide",
)


# --------------------------------------------------------------------------------------------------
# Data loading & fit (cached). The advisor is fit ONCE per process and reused for every recommend().
# --------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_curated() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three curated parquets the UI needs. Cached so the app reads disk once."""
    listings = pd.read_parquet(CURATED_DIR / "listings.parquet")
    detrended = pd.read_parquet(CURATED_DIR / "calendar_seasonality_detrended.parquet")
    occupancy = pd.read_parquet(CURATED_DIR / "occupancy.parquet")
    return listings, detrended, occupancy


@st.cache_resource(show_spinner="Fitting the hedonic model over the Rio market…")
def get_advisor(listings: pd.DataFrame) -> FittedAdvisor:
    """Fit the advisor once (cache_resource: a non-serializable object shared across reruns)."""
    return fit_advisor(listings)


def _stop_with_pipeline_error(detail: str) -> None:
    """Show a clear 'run the pipeline' error and halt — the app is useless without curated data."""
    st.error(
        f"Curated data is missing or unreadable: {detail}\n\n"
        f"Expected parquet files under `{CURATED_DIR}`. "
        "Run the data pipeline first (see the project README), then reload this app."
    )
    st.stop()


# --------------------------------------------------------------------------------------------------
# Presentation helpers (formatting only — no business logic).
# --------------------------------------------------------------------------------------------------
def _money(value: float) -> str:
    return f"{CURRENCY} {value:,.0f}"


def _friendly_driver(raw_name: str) -> str:
    return _DRIVER_LABELS.get(raw_name, raw_name.replace("_", " ").strip().capitalize())


def _driver_direction(effect: float) -> tuple[str, str]:
    """Return (arrow, plain-language phrase) for a log-price coefficient."""
    if effect >= 0:
        return "▲", f"pushes price up (~+{effect * 100:.0f}%)"
    return "▼", f"pulls price down (~{effect * 100:.0f}%)"


def render_header() -> None:
    st.title("🏖️ Rio Airbnb Pricing Lab")
    st.markdown(
        "A **price-positioning advisor** for Airbnb hosts in Rio de Janeiro. Describe a listing "
        "and it returns an honest price **range** — where comparable listings sit and what the "
        "model expects — never a single guaranteed number."
    )
    left, right = st.columns([3, 2])
    with left:
        st.caption(
            f"Market snapshot: **{SNAPSHOT_DATE}** · 39,816 active listings · "
            f"median price **{_money(500)}** (IQR {_money(330)}–{_money(827)})."
        )
    with right:
        st.caption(
            f"Hedonic model adjusted R² = **{ADJ_R2:.2f}** — it explains about half the price "
            "variation, so recommendations blend the model 50/50 with live peer prices. Treat them "
            "as positioning, not a forecast."
        )


# --------------------------------------------------------------------------------------------------
# Recommend tab.
# --------------------------------------------------------------------------------------------------
def _collect_input() -> HostInput | None:
    """Render the input form; return a HostInput on submit, else None."""
    with st.form("listing_form"):
        st.subheader("Describe the listing")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            nb_choice = st.selectbox(
                "Neighbourhood",
                options=[*TOP_NEIGHBOURHOODS, _FREE_TEXT_OPTION],
                help="Top neighbourhoods are individually modelled. Pick 'Other' for elsewhere.",
            )
            nb_free = ""
            if nb_choice == _FREE_TEXT_OPTION:
                nb_free = st.text_input("…neighbourhood name", placeholder="e.g. Leblon")
            room_type = st.selectbox("Room type", options=ROOM_TYPES)
            property_type = st.selectbox("Property type", options=PROPERTY_TYPES)
        with col_b:
            accommodates = st.number_input("Guests it sleeps", min_value=1, max_value=20, value=2)
            bedrooms = st.number_input(
                "Bedrooms", min_value=0.0, max_value=15.0, value=1.0, step=1.0
            )
            bathrooms_num = st.number_input(
                "Bathrooms", min_value=0.0, max_value=10.0, value=1.0, step=0.5
            )
        with col_c:
            min_nights = st.number_input("Minimum nights", min_value=1, max_value=365, value=2)
            number_of_reviews = st.number_input(
                "Number of reviews", min_value=0, max_value=2000, value=10
            )
            host_is_superhost = st.checkbox("Host is a Superhost", value=False)

        current_price = st.number_input(
            f"Current nightly price ({CURRENCY}) — optional",
            min_value=0.0,
            max_value=100_000.0,
            value=0.0,
            step=10.0,
            help=(
                "Leave at 0 if you don't have one yet. If set, it's used to place you among peers "
                "(percentile); otherwise the model's own estimate is used."
            ),
        )
        submitted = st.form_submit_button("Get price positioning", type="primary")

    if not submitted:
        return None

    neighbourhood = (nb_free.strip() if nb_choice == _FREE_TEXT_OPTION else nb_choice).strip()
    if not neighbourhood:
        st.warning("Please enter a neighbourhood name.")
        return None

    return HostInput(
        neighbourhood=neighbourhood,
        room_type=room_type,
        property_type=property_type,
        accommodates=int(accommodates),
        bedrooms=float(bedrooms),
        bathrooms_num=float(bathrooms_num),
        min_nights=int(min_nights),
        host_is_superhost=bool(host_is_superhost),
        number_of_reviews=int(number_of_reviews),
        current_price=float(current_price) if current_price > 0 else None,
    )


def _render_range_card(advice: ListingAdvice) -> None:
    rec = advice.recommendation
    st.subheader("Recommended price range")
    low, anchor, high = st.columns(3)
    low.metric("Low end", _money(rec.low))
    anchor.metric("Anchor (central)", _money(rec.anchor))
    high.metric("High end", _money(rec.high))
    st.caption(
        f"Suggested nightly range: **{_money(rec.low)} – {_money(rec.high)}**, centred on "
        f"{_money(rec.anchor)}. A range, never a single guaranteed price."
    )


def _render_peer_position(advice: ListingAdvice) -> None:
    rec = advice.recommendation
    peer = advice.peer
    st.subheader("Where this sits in the market")
    if not advice.has_peer_signal:
        st.warning(
            "**Not enough comparable listings** to position this against peers. The range above "
            "leans on the hedonic estimate alone — treat the percentile as unknown, not 50th."
        )
        return

    pctl_col, pos_col, n_col = st.columns(3)
    pctl_col.metric("Price percentile", f"{rec.price_percentile * 100:.0f}th")
    pos_col.metric("Position", rec.position_label.title())
    n_col.metric("Comparable listings", f"{peer.n_effective:,}")
    tier = " · ".join(peer.tier_used)
    st.caption(
        f"Compared against **{peer.n_effective:,}** peers (tier: {tier}); their shrunk median is "
        f"{_money(peer.shrunk_median)} with an IQR of {_money(peer.iqr)}."
    )


def _render_drivers(advice: ListingAdvice) -> None:
    drivers = advice.recommendation.top_drivers
    if not drivers:
        return
    st.subheader("What moves this price most")
    st.caption("Top hedonic drivers (effect on log price). ▲ pushes price up, ▼ pulls it down.")
    for raw_name, effect in drivers:
        arrow, phrase = _driver_direction(effect)
        st.markdown(f"- {arrow} **{_friendly_driver(raw_name)}** — {phrase}")
    if any(name == "host_is_superhost" and eff < 0 for name, eff in drivers):
        st.info(
            "Heads up: in this market the **Superhost** coefficient is *negative* — Superhosts "
            "tend to sit slightly below comparable non-Superhosts. Becoming a Superhost is not a "
            "lever to charge more; it's a caveat, not a price boost."
        )


def _render_context(advice: ListingAdvice) -> None:
    st.subheader("Demand & honesty checks")
    st.markdown(f"**Demand:** {advice.recommendation.demand_note}")
    if advice.demand.magnitudes_are_lower_bounds:
        st.caption(
            "Seasonal uplift magnitudes are **lower bounds** — far-horizon peaks (Réveillon, "
            "Carnaval) hit a measurement ceiling, so the real premium is at least this large."
        )
    if not advice.neighbourhood_in_model:
        st.info(
            "**Neighbourhood not individually modelled.** This area was pooled into the baseline "
            "(too few listings or unseen in the snapshot), so its price estimate is a baseline "
            "approximation — less precise than for a top neighbourhood."
        )
    for caveat in advice.recommendation.caveats:
        st.warning(caveat)


def render_recommend_tab(advisor: FittedAdvisor, detrended: pd.DataFrame) -> None:
    st.markdown(
        "Fill in the listing, then read the **range** — not a single price — that comes back."
    )
    host_input = _collect_input()
    if host_input is None:
        st.info("Enter a listing above and submit to see its price positioning.")
        return

    advice = recommend(advisor, host_input, detrended)
    st.divider()
    _render_range_card(advice)
    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        _render_peer_position(advice)
        _render_drivers(advice)
    with col_right:
        _render_context(advice)


# --------------------------------------------------------------------------------------------------
# Explore tab — Plotly charts straight off the curated data (descriptive, not modelled).
# --------------------------------------------------------------------------------------------------
def _chart_median_by_neighbourhood(listings: pd.DataFrame, top_n: int = 12) -> None:
    counts = listings["neighbourhood"].value_counts().head(top_n).index
    summary = (
        listings[listings["neighbourhood"].isin(counts)]
        .groupby("neighbourhood", observed=True)["price"]
        .median()
        .sort_values(ascending=True)
        .reset_index()
    )
    fig = px.bar(
        summary,
        x="price",
        y="neighbourhood",
        orientation="h",
        title=f"Median nightly price — top {top_n} neighbourhoods by listing count",
        labels={"price": f"Median price ({CURRENCY})", "neighbourhood": "Neighbourhood"},
        color="price",
        color_continuous_scale="Tealgrn",
    )
    fig.update_layout(coloraxis_showscale=False, height=460)
    st.plotly_chart(fig, width="stretch")


def _chart_price_distribution(listings: pd.DataFrame) -> None:
    prices = listings["price"].dropna()
    lo, hi = prices.quantile([0.01, 0.99])
    clipped = prices.clip(lo, hi)
    fig = px.histogram(
        clipped,
        nbins=60,
        title="Nightly price distribution (winsorized at 1st/99th percentile)",
        labels={"value": f"Nightly price ({CURRENCY})"},
        color_discrete_sequence=["#1f9e89"],
    )
    fig.update_layout(showlegend=False, height=420, bargap=0.02)
    fig.update_xaxes(title=f"Nightly price ({CURRENCY})")
    fig.update_yaxes(title="Listings")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Prices are winsorized at the 1st/99th percentile to keep data-entry noise and luxury "
        f"outliers from dominating the view (clipped to {_money(lo)}–{_money(hi)})."
    )


def _chart_seasonality(detrended: pd.DataFrame) -> None:
    clean = detrended[~detrended["is_edge"].fillna(False).astype(bool)].copy()
    clean = clean.sort_values("date")
    fig = px.line(
        clean,
        x="date",
        y="event_uplift",
        title="Detrended demand seasonality — event uplift over the booking horizon",
        labels={"date": "Date", "event_uplift": "Event uplift (share of nights unavailable)"},
        color_discrete_sequence=["#3b528b"],
    )
    # Highlight the two dated peaks. Windows mirror demand_context._EVENT_WINDOWS.
    for label, color in (("Réveillon", "#d62728"), ("Carnaval", "#ff7f0e")):
        peak = _event_peak(clean, label)
        if peak is not None:
            fig.add_scatter(
                x=[peak["date"]],
                y=[peak["event_uplift"]],
                mode="markers+text",
                marker={"size": 12, "color": color},
                text=[label],
                textposition="top center",
                name=label,
            )
    fig.update_layout(height=440)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Edge rows (near-snapshot artifacts) are filtered out. Uplift magnitudes are **lower "
        "bounds**: far-horizon peaks hit a measurement ceiling (~0.70), so the real premium for "
        "Réveillon and Carnaval is larger than shown."
    )


def _event_peak(clean: pd.DataFrame, label: str) -> pd.Series | None:
    """Find the max-uplift date inside an event window (year-wrap aware), or None if absent."""
    windows = {"Réveillon": ((12, 28), (1, 2)), "Carnaval": ((2, 6), (2, 12))}
    lo, hi = windows[label]
    md = clean["date"].dt.month * 100 + clean["date"].dt.day
    lo_ord, hi_ord = lo[0] * 100 + lo[1], hi[0] * 100 + hi[1]
    mask = (md >= lo_ord) | (md <= hi_ord) if lo[0] > hi[0] else (md >= lo_ord) & (md <= hi_ord)
    hit = clean[mask]
    if hit.empty:
        return None
    return hit.loc[hit["event_uplift"].idxmax()]


def _chart_occupancy(occupancy: pd.DataFrame) -> None:
    occ = occupancy["occupancy_est"].dropna()
    fig = px.histogram(
        occ,
        nbins=50,
        title="Occupancy-proxy distribution across listings",
        labels={"value": "Estimated occupancy (proxy)"},
        color_discrete_sequence=["#5ec962"],
    )
    fig.update_layout(showlegend=False, height=420, bargap=0.02)
    fig.update_xaxes(title="Estimated occupancy (proxy, 0–1)")
    fig.update_yaxes(title="Listings")
    st.plotly_chart(fig, width="stretch")
    st.warning(
        "This occupancy is a **reviews-driven proxy** (San Francisco model), not observed "
        "bookings, and is capped at 0.70. Read it as relative demand pressure, not booked nights."
    )


def render_explore_tab(
    listings: pd.DataFrame, detrended: pd.DataFrame, occupancy: pd.DataFrame
) -> None:
    st.markdown(
        "Descriptive views of the curated 2026-03-30 snapshot. These are raw market facts — the "
        "Recommend tab is where the model turns them into a positioning range."
    )
    col_left, col_right = st.columns(2)
    with col_left:
        _chart_median_by_neighbourhood(listings)
        _chart_seasonality(detrended)
    with col_right:
        _chart_price_distribution(listings)
        _chart_occupancy(occupancy)


# --------------------------------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------------------------------
def main() -> None:
    render_header()
    try:
        listings, detrended, occupancy = load_curated()
    except FileNotFoundError as exc:
        _stop_with_pipeline_error(str(exc))
        return
    except (OSError, ValueError) as exc:  # corrupt/unreadable parquet
        _stop_with_pipeline_error(str(exc))
        return

    advisor = get_advisor(listings)

    recommend_tab, explore_tab = st.tabs(["💡 Recommend", "📊 Explore the market"])
    with recommend_tab:
        render_recommend_tab(advisor, detrended)
    with explore_tab:
        render_explore_tab(listings, detrended, occupancy)


if __name__ == "__main__":
    main()
