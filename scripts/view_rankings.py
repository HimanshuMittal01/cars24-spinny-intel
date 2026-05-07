"""Streamlit single-page leaderboard for ranked car listings.

Usage:
    uv run streamlit run scripts/view_rankings.py
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ci.config import FIXTURES_DIR, RUNS_DIR
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.snapshot import load_snapshot

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ranking Leaderboard",
    page_icon="🏆",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def load_ranking() -> list[dict]:
    path = RUNS_DIR / "latest_ranking" / "ranking.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def load_photos(platform: str, listing_id: str) -> list[dict]:
    manifest_path = FIXTURES_DIR / platform / listing_id / "photos.json"
    if not manifest_path.exists():
        return []
    return json.loads(manifest_path.read_text()).get("photos", [])


@st.cache_data
def get_descriptive(platform: str, listing_id: str) -> dict:
    snap = load_snapshot(platform, listing_id)
    raw = extract_cars24(snap) if platform == "cars24" else extract_spinny(snap)
    f = raw.fields
    if platform == "cars24":
        return {
            "make": f.get("make"),
            "model": f.get("model"),
            "variant": f.get("variant") or f.get("variantName"),
            "year": f.get("year"),
            "fuel": f.get("fuelType"),
            "transmission": f.get("transmissionType"),
        }
    variant = f.get("variant")
    if isinstance(variant, dict):
        variant = variant.get("full_name") or variant.get("display_name")
    return {
        "make": f.get("make"),
        "model": f.get("model"),
        "variant": variant,
        "year": f.get("make_year"),
        "fuel": f.get("fuel_type"),
        "transmission": f.get("transmission"),
    }


@st.cache_data
def get_normalized(platform: str, listing_id: str) -> dict:
    snap = load_snapshot(platform, listing_id)
    raw = extract_cars24(snap) if platform == "cars24" else extract_spinny(snap)
    norm = normalize(raw, today_year=2026)
    return {
        "km_driven": norm.km_driven,
        "age_years": norm.age_years,
        "owners": norm.owners,
        "accident_disclosed": norm.accident_disclosed or "—",
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt_price(price_rupees: int | float | None) -> str:
    if price_rupees is None:
        return "—"
    lakhs = price_rupees / 100_000
    return f"₹{lakhs:.2f} L"


def fmt_km(km: int | None) -> str:
    if km is None:
        return "—"
    return f"{km:,}"


def fmt_score(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:.2f}"


def val_or_dash(v) -> str:
    if v is None:
        return "—"
    return str(v)


# ---------------------------------------------------------------------------
# Load ranking data
# ---------------------------------------------------------------------------

ranking_path = RUNS_DIR / "latest_ranking" / "ranking.json"
ranking = load_ranking()

if not ranking:
    st.error("No ranking data found at `runs/latest_ranking/ranking.json`.")
    st.stop()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("Ranking Leaderboard")
st.caption(f"Source: `{ranking_path}`")
st.markdown(
    "**Score formula:** `composite = α × rule + (1 − α) × visual,  α = 0.7`"
)
st.divider()

# ---------------------------------------------------------------------------
# Card grid — 2 columns
# ---------------------------------------------------------------------------

COLS = 2
rows = [ranking[i : i + COLS] for i in range(0, len(ranking), COLS)]

for row_entries in rows:
    col_widgets = st.columns(COLS)
    for col_widget, entry in zip(col_widgets, row_entries):
        rank_num = ranking.index(entry) + 1
        platform = entry["platform"]
        listing_id = entry["listing_id"]
        composite = entry.get("composite_score")
        rule = entry.get("rule_score")
        visual = entry.get("visual_score")
        price = entry.get("price")
        imputed = entry.get("imputed_aspects", [])

        # Fetch descriptive + normalized data
        desc = get_descriptive(platform, listing_id)
        norm = get_normalized(platform, listing_id)
        photos = load_photos(platform, listing_id)

        with col_widget:
            try:
                card = st.container(border=True)
            except TypeError:
                # Streamlit < 1.29 fallback
                card = st.container()

            with card:
                # --- Header row ---
                h_left, h_right = st.columns([1, 2])
                with h_left:
                    st.markdown(f"## #{rank_num}")
                with h_right:
                    st.markdown(
                        f"### composite {fmt_score(composite)}"
                    )
                    st.markdown(
                        f"<small>rule {fmt_score(rule)} &nbsp;·&nbsp; visual {fmt_score(visual)}</small>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<small>{listing_id} &nbsp;·&nbsp; {platform}</small>",
                        unsafe_allow_html=True,
                    )

                # --- Hero photo ---
                if photos:
                    hero = photos[0]
                    hero_sha = hero.get("sha256", "")
                    hero_path = (
                        FIXTURES_DIR / platform / listing_id / "photos" / f"{hero_sha}.jpg"
                    )
                    if hero_path.exists():
                        st.image(str(hero_path), use_container_width=True)
                    else:
                        st.markdown("_hero photo not found_")
                else:
                    st.markdown("_no photos_")

                # --- Spec table ---
                make = val_or_dash(desc.get("make"))
                model = val_or_dash(desc.get("model"))
                make_model = f"{make} {model}".strip() if make != "—" or model != "—" else "—"

                spec_rows = [
                    ("Make / Model", make_model),
                    ("Variant", val_or_dash(desc.get("variant"))),
                    ("Year", val_or_dash(desc.get("year"))),
                    ("Fuel", val_or_dash(desc.get("fuel"))),
                    ("Transmission", val_or_dash(desc.get("transmission"))),
                    ("Price", fmt_price(price)),
                    ("KM driven", fmt_km(norm.get("km_driven"))),
                    ("Age", f"{norm.get('age_years')} yrs" if norm.get("age_years") is not None else "—"),
                    ("Owners", val_or_dash(norm.get("owners"))),
                    ("Accident", val_or_dash(norm.get("accident_disclosed"))),
                ]

                spec_col1, spec_col2 = st.columns(2)
                half = len(spec_rows) // 2 + len(spec_rows) % 2
                left_rows = spec_rows[:half]
                right_rows = spec_rows[half:]

                with spec_col1:
                    for label, value in left_rows:
                        st.markdown(f"**{label}**  \n{value}")

                with spec_col2:
                    for label, value in right_rows:
                        st.markdown(f"**{label}**  \n{value}")

                # --- Imputed caption ---
                if imputed:
                    st.markdown(
                        f":orange[imputed: {', '.join(imputed)}]",
                    )

                # --- All photos expander ---
                valid_photos = [
                    p for p in photos
                    if (
                        FIXTURES_DIR / platform / listing_id / "photos" / f"{p.get('sha256', '')}.jpg"
                    ).exists()
                ]
                with st.expander(f"All photos ({len(valid_photos)})"):
                    if valid_photos:
                        PHOTO_COLS = 4
                        photo_rows = [
                            valid_photos[i : i + PHOTO_COLS]
                            for i in range(0, len(valid_photos), PHOTO_COLS)
                        ]
                        for photo_row in photo_rows:
                            img_cols = st.columns(PHOTO_COLS)
                            for img_col, photo in zip(img_cols, photo_row):
                                sha = photo.get("sha256", "")
                                hint = photo.get("hint", "")
                                idx = photo.get("idx", "?")
                                img_path = (
                                    FIXTURES_DIR
                                    / platform
                                    / listing_id
                                    / "photos"
                                    / f"{sha}.jpg"
                                )
                                with img_col:
                                    st.image(str(img_path), use_container_width=True)
                                    st.caption(f"idx {idx} · {hint}")
                    else:
                        st.markdown("_no photos available_")

    # Spacer between grid rows
    st.write("")

# ---------------------------------------------------------------------------
# Bottom ledger table
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Ledger")

# Build rows for all 6 listings
table_rows = []
for i, entry in enumerate(ranking):
    lid = entry["listing_id"]
    plat = entry["platform"]
    desc = get_descriptive(plat, lid)
    make = val_or_dash(desc.get("make"))
    model = val_or_dash(desc.get("model"))
    make_model = f"{make} {model}".strip() if make != "—" or model != "—" else "—"
    table_rows.append(
        {
            "Rank": i + 1,
            "Listing": lid,
            "Platform": plat,
            "Make / Model": make_model,
            "Variant": val_or_dash(desc.get("variant")),
            "Year": val_or_dash(desc.get("year")),
            "Price": fmt_price(entry.get("price")),
            "Rule": fmt_score(entry.get("rule_score")),
            "Visual": fmt_score(entry.get("visual_score")),
            "Composite": fmt_score(entry.get("composite_score")),
        }
    )

# Render as markdown table
header_cols = list(table_rows[0].keys())
md_header = "| " + " | ".join(header_cols) + " |"
md_sep = "| " + " | ".join("---" for _ in header_cols) + " |"
md_rows = [
    "| " + " | ".join(str(row[c]) for c in header_cols) + " |"
    for row in table_rows
]
st.markdown("\n".join([md_header, md_sep] + md_rows))
