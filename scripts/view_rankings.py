"""Streamlit viewer for ranked car listings.

Usage:
    uv run streamlit run scripts/view_rankings.py
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ci.config import EVAL_DIR, FIXTURES_DIR, RUNS_DIR
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.snapshot import load_snapshot

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
def get_features(platform: str, listing_id: str) -> dict:
    snap = load_snapshot(platform, listing_id)
    raw = extract_cars24(snap) if platform == "cars24" else extract_spinny(snap)
    norm = normalize(raw, today_year=2026)
    return {
        "price": norm.price,
        "km_driven": norm.km_driven,
        "age_years": norm.age_years,
        "owners": norm.owners,
        "certification_flag": norm.certification_flag,
        "accident_disclosed": norm.accident_disclosed,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_price(price_rupees: int | float | None) -> str:
    if price_rupees is None:
        return "—"
    lakhs = price_rupees / 100_000
    return f"₹ {lakhs:.2f}L"


def fmt_km(km: int | None) -> str:
    if km is None:
        return "—"
    return f"{km:,} km"


def fmt_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    return f"₹ {ratio:,.0f} / pt"


def fmt_score(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:.2f}"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ranking Viewer",
    page_icon="🚗",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

ranking = load_ranking()
ranking_path = RUNS_DIR / "latest_ranking" / "ranking.json"

if not ranking:
    st.error("No ranking data found at `runs/latest_ranking/ranking.json`.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Ranking Viewer")
    st.caption(f"Source: `{ranking_path}`")
    st.divider()

    radio_labels = [
        f"#{i+1}  {row['platform']} / {row['listing_id']}      composite={row['composite_score']:.2f}"
        for i, row in enumerate(ranking)
    ]
    selected_label = st.radio(
        "Select listing to inspect",
        options=radio_labels,
        index=0,
    )
    selected_idx = radio_labels.index(selected_label)
    selected = ranking[selected_idx]

    st.divider()
    st.markdown("**Score formula**")
    st.markdown("```\ncomposite = α × rule + (1-α) × visual\nα = 0.7\n```")

# ---------------------------------------------------------------------------
# Main pane
# ---------------------------------------------------------------------------

platform = selected["platform"]
listing_id = selected["listing_id"]
rank = selected_idx + 1

st.header(f"{platform} / {listing_id}  —  Rank #{rank}")

# --- Top row: score cards ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Composite Score", fmt_score(selected.get("composite_score")))
with col2:
    st.metric("Rule Score", fmt_score(selected.get("rule_score")))
with col3:
    vis = selected.get("visual_score")
    st.metric("Visual Score", fmt_score(vis) if vis is not None else "—")
with col4:
    st.metric("Price", fmt_price(selected.get("price")))

st.divider()

# --- Second row: feature cards (from extractor) ---
feats = get_features(platform, listing_id)

col_km, col_age, col_owners, col_ratio = st.columns(4)
with col_km:
    st.metric("KM Driven", fmt_km(feats.get("km_driven")))
with col_age:
    age = feats.get("age_years")
    st.metric("Age (years)", str(age) if age is not None else "—")
with col_owners:
    owners = feats.get("owners")
    st.metric("Owners", str(owners) if owners is not None else "—")
with col_ratio:
    st.metric("Price / Score (ratio)", fmt_ratio(selected.get("ratio")))

st.divider()

# --- Third section: disclosure & imputation ---
st.subheader("Disclosure & Imputation")

dcol1, dcol2, dcol3 = st.columns(3)

with dcol1:
    dc = selected.get("disclosure_count", 0)
    st.metric("Disclosure Count", str(dc))

with dcol2:
    imp_dims = selected.get("imputed_dims", [])
    if imp_dims:
        st.markdown(f"**Imputed Dims** — :red[{', '.join(imp_dims)}]")
    else:
        st.markdown("**Imputed Dims** — :green[none]")

with dcol3:
    imp_asp = selected.get("imputed_aspects", [])
    if imp_asp:
        st.markdown(f"**Imputed Aspects** — :red[{', '.join(imp_asp)}]")
    else:
        st.markdown("**Imputed Aspects** — :green[none]")

st.divider()

# --- Photo grid ---
photos = load_photos(platform, listing_id)

if photos:
    st.subheader(f"Photos ({len(photos)} total)")
    cols_per_row = 4
    rows = [photos[i : i + cols_per_row] for i in range(0, len(photos), cols_per_row)]
    for row_photos in rows:
        img_cols = st.columns(cols_per_row)
        for col, photo in zip(img_cols, row_photos):
            sha = photo.get("sha256", "")
            hint = photo.get("hint", "")
            idx = photo.get("idx", "?")
            img_path = FIXTURES_DIR / platform / listing_id / "photos" / f"{sha}.jpg"
            with col:
                if img_path.exists():
                    st.image(str(img_path), use_container_width=True)
                else:
                    st.markdown("_(image not found)_")
                st.caption(f"idx {idx} · {hint}")
else:
    st.info("No photos available for this listing.")

st.divider()

# --- Comparison strip (leaderboard table) ---
st.subheader("Full Leaderboard")

header = "| Rank | Listing | Platform | Composite | Rule | Visual | Ratio |"
sep    = "|------|---------|----------|-----------|------|--------|-------|"
rows_md = [header, sep]

for i, row in enumerate(ranking):
    r_rank = i + 1
    r_lid = row["listing_id"]
    r_plat = row["platform"]
    r_comp = fmt_score(row.get("composite_score"))
    r_rule = fmt_score(row.get("rule_score"))
    r_vis  = fmt_score(row.get("visual_score")) if row.get("visual_score") is not None else "—"
    r_ratio = fmt_ratio(row.get("ratio"))

    line = f"| {r_rank} | {r_lid} | {r_plat} | {r_comp} | {r_rule} | {r_vis} | {r_ratio} |"
    if i == selected_idx:
        # Highlight selected row with bold
        line = f"| **{r_rank}** | **{r_lid}** | **{r_plat}** | **{r_comp}** | **{r_rule}** | **{r_vis}** | **{r_ratio}** |"
    rows_md.append(line)

st.markdown("\n".join(rows_md))
