"""Run the end-to-end pipeline on the 16-listing active set (10 gold + 6 ranking).

Vision phase is on by default; turn off with --no-vision for a pure deterministic run.
Output ranking is filtered to the 6 ranking listings.
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

from ci.config import EVAL_DIR, RUNS_DIR
from ci.pipeline import run_pipeline
from ci.report import render_chart


def _load_active_listings() -> tuple[list[tuple[str, str]], set[str]]:
    """Return (16-listing union, set of ranking listing ids)."""
    gold_rows = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking_rows = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    listings = (
        [(g["platform"], g["listing_id"]) for g in gold_rows]
        + [(r["platform"], r["listing_id"]) for r in ranking_rows]
    )
    ranking_ids = {r["listing_id"] for r in ranking_rows}
    return listings, ranking_ids


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-vision", action="store_true",
                   help="Skip the vision agent; pipeline runs deterministically.")
    p.add_argument("--vision-no-cache", action="store_true",
                   help="Bypass inner inspector cache (E5 cold-cache runs).")
    p.add_argument("--vision-listings", default=None,
                   help="Comma-separated listing-id subset for vision (debug / cost-cap).")
    p.add_argument("--vision-budget", type=int, default=10,
                   help="Max inspect_photo calls per listing (default 10).")
    p.add_argument("--alpha", type=float, default=None,
                   help="Override default composite alpha (0.7).")
    args = p.parse_args()

    listings, ranking_ids = _load_active_listings()

    vision_subset = None
    if args.vision_listings:
        vision_subset = set(s.strip() for s in args.vision_listings.split(",") if s.strip())

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-" + uuid.uuid4().hex[:6]
    )
    run_dir = RUNS_DIR / run_id

    from ci.vision.composite import DEFAULT_ALPHA
    alpha = args.alpha if args.alpha is not None else DEFAULT_ALPHA

    rows = run_pipeline(
        listings=listings,
        ranking_listing_ids=ranking_ids,
        run_dir=run_dir,
        enable_vision=not args.no_vision,
        vision_no_cache=args.vision_no_cache,
        vision_listings_subset=vision_subset,
        vision_max_inspects=args.vision_budget,
        alpha=alpha,
    )
    out = run_dir / "ranking.json"
    out.write_text(json.dumps([r.model_dump() for r in rows], indent=2))
    print(f"wrote {out}")

    chart_out = run_dir / "ranking_chart.png"
    render_chart(rows, chart_out)
    print(f"wrote {chart_out}")


if __name__ == "__main__":
    main()
