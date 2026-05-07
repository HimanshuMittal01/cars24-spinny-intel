"""Streamlit app for labeling eval/vision_gold.jsonl.

Run:
  uv run streamlit run scripts/label_vision_gold.py

What it does:
  - Loads the 10 gold listings from eval/vision_gold.jsonl.
  - Renders each listing's photos in a grid with platform-supplied hints.
  - Provides 5 dropdowns (one per aspect) for severity selection.
  - Auto-saves on every change. Closing the browser is safe.
  - Sidebar shows progress and lets you jump between listings.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ci.config import EVAL_DIR, FIXTURES_DIR

ASPECTS = ("exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay")
SEVERITIES = ["", "pristine", "light_wear", "moderate", "heavy", "defect", "not_visible"]
GOLD_PATH = EVAL_DIR / "vision_gold.jsonl"


def load_rows() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    headers: list[str] = []
    for line in GOLD_PATH.read_text().splitlines():
        if line.startswith("#"):
            headers.append(line)
        elif line.strip():
            rows.append(json.loads(line))
    return rows, headers


def save_rows(rows: list[dict], headers: list[str]) -> None:
    body = "\n".join(headers + [json.dumps(r) for r in rows])
    GOLD_PATH.write_text(body + "\n")


def is_done(row: dict) -> bool:
    return all(row["vision_gold"].get(a) for a in ASPECTS)


def main() -> None:
    st.set_page_config(page_title="Vision Gold Labeler", layout="wide")

    rows, headers = load_rows()

    with st.sidebar:
        st.title("Vision Gold")
        st.caption(f"Source: `eval/vision_gold.jsonl` ({len(rows)} listings)")

        labeled = sum(1 for r in rows if is_done(r))
        st.metric("Progress", f"{labeled} / {len(rows)}")
        st.progress(labeled / len(rows) if rows else 0)

        labels = []
        for i, r in enumerate(rows):
            mark = "✅" if is_done(r) else "⬜"
            labels.append(f"{mark} {i + 1}. {r['platform']}/{r['listing_id']}")

        idx = st.radio(
            "Listing",
            range(len(rows)),
            format_func=lambda i: labels[i],
            index=0,
        )

        st.divider()
        st.markdown("**Severity scale**")
        st.markdown(
            "- `pristine` — no visible wear\n"
            "- `light_wear` — minor scuffs / normal aging\n"
            "- `moderate` — visible wear, multiple small dings or fade\n"
            "- `heavy` — prominent damage, deep scratches\n"
            "- `defect` — structural / functional fault\n"
            "- `not_visible` — no photo evidences this aspect"
        )

    row = rows[idx]
    plat, lid = row["platform"], row["listing_id"]

    st.header(f"{plat} / {lid}")

    manifest_path = FIXTURES_DIR / plat / lid / "photos.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        photos = manifest["photos"]
        st.caption(f"{len(photos)} photos captured")

        cols_per_row = 4
        cols = st.columns(cols_per_row)
        for i, p in enumerate(photos):
            photo_path = FIXTURES_DIR / plat / lid / "photos" / f"{p['sha256']}.jpg"
            if not photo_path.exists():
                continue
            hint = p.get("hint") or "?"
            cols[i % cols_per_row].image(
                str(photo_path),
                caption=f"#{p['idx']:>2} · {hint}",
                use_container_width=True,
            )
    else:
        st.error(f"No manifest at {manifest_path}")

    st.divider()
    st.subheader("Severities")

    sev_cols = st.columns(5)
    for i, aspect in enumerate(ASPECTS):
        current = row["vision_gold"].get(aspect)
        default_idx = SEVERITIES.index(current) if current in SEVERITIES else 0
        chosen = sev_cols[i].selectbox(
            aspect,
            SEVERITIES,
            index=default_idx,
            key=f"sev_{idx}_{aspect}",
        )
        new_val = chosen if chosen else None
        if new_val != row["vision_gold"][aspect]:
            row["vision_gold"][aspect] = new_val
            save_rows(rows, headers)
            st.toast(f"{aspect} = {chosen or 'null'}")

    with st.expander("Notes (optional, per aspect)"):
        notes = row.get("notes", {})
        new_notes = {}
        for aspect in ASPECTS:
            val = st.text_input(
                aspect,
                value=notes.get(aspect, ""),
                key=f"note_{idx}_{aspect}",
            )
            if val:
                new_notes[aspect] = val
        if new_notes != notes:
            row["notes"] = new_notes
            save_rows(rows, headers)


if __name__ == "__main__":
    main()
