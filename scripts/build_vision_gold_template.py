"""Generate eval/vision_gold.jsonl template (16 listings × 5 aspects, all nulls).

Also generates eval/vision_gold.anchors.md — a calibration doc that points the
hand-labeller at example photos for each severity level. Anchors are picked as
the first inspectable photo per listing/aspect; the human still does the rating.

Usage:
  uv run python -m scripts.build_vision_gold_template
"""
from __future__ import annotations

import json
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR

ASPECTS = ("exterior_panels", "interior_cabin",
           "dashboard_console", "tyres", "engine_bay")


def _active_listings() -> list[dict]:
    """16-listing union: 10 gold + 6 ranking."""
    gold = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    return [{"platform": g["platform"], "listing_id": g["listing_id"]} for g in gold] \
         + [{"platform": r["platform"], "listing_id": r["listing_id"]} for r in ranking]


def build_template_rows(listings: list[dict]) -> list[dict]:
    return [
        {
            "listing_id": l["listing_id"],
            "platform": l["platform"],
            "vision_gold": {a: None for a in ASPECTS},
            "notes": {},
        }
        for l in listings
    ]


def _write_anchors_doc(listings: list[dict], out_path: Path) -> None:
    """Reference doc with the first photo per listing for the labeler's eye."""
    lines = [
        "# Vision Gold Anchors\n",
        "Reference photos for severity calibration. Open these before labeling so",
        "your `pristine`/`light_wear`/`moderate`/`heavy`/`defect` calls are consistent",
        "across the session.\n",
        "## Severity definitions\n",
        "- **pristine**: no visible wear. Looks new.",
        "- **light_wear**: minor scuffs, light usage marks. Normal aging.",
        "- **moderate**: visible wear. Multiple small dents/scratches OR significant fade.",
        "- **heavy**: prominent damage. Multiple large dings, deep scratches, severe fade.",
        "- **defect**: structural / functional fault visible (cracked panel, missing trim).",
        "- **not_visible**: no photo evidences this aspect.\n",
        "## Per-listing photo index\n",
    ]
    for l in listings:
        lid, plat = l["listing_id"], l["platform"]
        manifest_path = FIXTURES_DIR / plat / lid / "photos.json"
        if not manifest_path.exists():
            lines.append(f"### {plat}/{lid} — NO PHOTOS CAPTURED\n")
            continue
        manifest = json.loads(manifest_path.read_text())
        photos = manifest.get("photos", [])
        lines.append(f"### {plat}/{lid} ({len(photos)} photos)\n")
        for p in photos[:8]:  # cap at 8 per listing in the anchor doc
            hint = p.get("hint") or "?"
            lines.append(f"- idx {p['idx']:>3} ({hint:<10}) `{p['source_url']}`")
        if len(photos) > 8:
            lines.append(f"- ... +{len(photos) - 8} more")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    listings = _active_listings()
    rows = build_template_rows(listings)
    out_jsonl = EVAL_DIR / "vision_gold.jsonl"
    header = (
        "# severity ∈ {pristine, light_wear, moderate, heavy, defect, not_visible}\n"
        "# notes: optional per-aspect comment, e.g. {\"tyres\": \"rear-left tread visibly low\"}\n"
    )
    out_jsonl.write_text(header + "\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} template rows to {out_jsonl}")

    anchors = EVAL_DIR / "vision_gold.anchors.md"
    _write_anchors_doc(listings, anchors)
    print(f"Wrote anchors doc to {anchors}")


if __name__ == "__main__":
    main()
