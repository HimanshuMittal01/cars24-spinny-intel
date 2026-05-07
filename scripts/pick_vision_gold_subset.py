"""Pick 10 of the 17 gold listings (5 cars24 + 5 spinny) for the vision-agent calibration set.

Selection criteria (per docs/superpowers/specs/2026-05-07-vision-agent-design.md §12.0):
  1. Platform parity: 5 cars24 + 5 spinny.
  2. Rule-score percentile spread: prefer one pick per quintile per platform.
  3. Photo-count spread: high vs low photo coverage.
  4. Disclosure spread: high vs low full_fields count.

Outputs:
  - eval/vision_gold_subset_proposal.json  (10 picks + 7 drops + reasoning)
  - prints summary to stdout for user review
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR


def percentile_quintile(value: float, all_values: list[float]) -> int:
    """Return 0..4 quintile bucket for value within all_values."""
    sorted_vals = sorted(all_values)
    rank = sum(1 for v in sorted_vals if v <= value)
    return min(4, max(0, (rank * 5 - 1) // len(sorted_vals)))


def count_photos(platform: str, listing_id: str) -> int:
    """Count distinct listing-image URLs in the snapshot HTML.

    Uses platform-specific host filters to avoid counting CMS banners or icons.
    """
    fix = FIXTURES_DIR / platform / listing_id / "page.html"
    if not fix.exists():
        return 0
    html = fix.read_text()
    if platform == "spinny":
        urls = re.findall(r"spn-mda\.spinny\.com/img/[A-Za-z0-9%_+\-/]+", html)
    else:
        urls = re.findall(r"fastly-production\.24c\.in/india/used-cars/[A-Za-z0-9%_+\-/.]+", html)
    return len(set(urls))


def disclosure_count(platform: str, listing_id: str) -> int:
    """Use the existing label file's full_fields key count as a disclosure proxy."""
    label_path = EVAL_DIR / "labels" / platform / f"{listing_id}.json"
    if not label_path.exists():
        return 0
    fields = json.loads(label_path.read_text()).get("full_fields", {})
    return len(fields)


def load_gold() -> list[dict]:
    """Read eval/gold.jsonl and return the parsed rows."""
    return [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]


def pick_subset(gold: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pick 5 cars24 + 5 spinny preserving diversity. Returns (picked, dropped).

    Note: when all score_common values within a platform are equal, every row
    lands in quintile 4 — the algorithm still picks 5 valid rows but the
    "quintile spread" claim is degenerate. Acceptable for the real gold data we expect.
    """
    target_per_platform = 5
    picked: list[dict] = []
    dropped: list[dict] = []

    for platform in ("cars24", "spinny"):
        rows = [r for r in gold if r["platform"] == platform]
        scores = [r["score_common"] for r in rows]
        annotated = []
        for r in rows:
            annotated.append({
                **r,
                "_quintile": percentile_quintile(r["score_common"], scores),
                "_photos": count_photos(platform, r["listing_id"]),
                "_disclosure": disclosure_count(platform, r["listing_id"]),
            })

        # Stratified pick: one per quintile (max diversity), then fill with leftover diversity.
        chosen: list[dict] = []
        seen_ids: set[str] = set()
        # Pass 1: best-of-each-quintile by (photos, disclosure)
        for q in sorted({r["_quintile"] for r in annotated}):
            cands = [r for r in annotated if r["_quintile"] == q]
            cand = max(cands, key=lambda r: (r["_photos"], r["_disclosure"]))
            chosen.append(cand)
            seen_ids.add(cand["listing_id"])

        # Pass 2: fill to target with remaining (highest photo+disclosure first)
        remaining = [r for r in annotated if r["listing_id"] not in seen_ids]
        remaining.sort(key=lambda r: (r["_photos"] + r["_disclosure"]), reverse=True)
        while len(chosen) < target_per_platform and remaining:
            extra = remaining.pop(0)
            chosen.append(extra)
            seen_ids.add(extra["listing_id"])

        chosen = chosen[:target_per_platform]  # guard: pass-1 fills at most 5 (one per quintile), but slice for safety
        chosen_ids = {c["listing_id"] for c in chosen}

        for r in annotated:
            if r["listing_id"] in chosen_ids:
                picked.append(r)
            else:
                dropped.append(r)

    return picked, dropped


def main() -> None:
    gold = load_gold()
    picked, dropped = pick_subset(gold)

    print(f"Picked {len(picked)} listings:")
    for p in picked:
        print(
            f"  [{p['platform']:7}] {p['listing_id']:14} "
            f"score={p['score_common']:5.2f} q={p['_quintile']} "
            f"photos={p['_photos']:3} disclosure={p['_disclosure']}"
        )
    print(f"\nDropped {len(dropped)} listings:")
    for d in dropped:
        print(
            f"  [{d['platform']:7}] {d['listing_id']:14} "
            f"score={d['score_common']:5.2f} q={d['_quintile']} "
            f"photos={d['_photos']:3} disclosure={d['_disclosure']}"
        )

    out = {
        "picked": [
            {"platform": p["platform"], "listing_id": p["listing_id"]} for p in picked
        ],
        "dropped": [
            {"platform": d["platform"], "listing_id": d["listing_id"]} for d in dropped
        ],
        "reasoning": {
            "criteria": "platform parity 5+5; quintile spread within platform; "
                        "photo+disclosure diversity",
            "spec_ref": "docs/superpowers/specs/2026-05-07-vision-agent-design.md §12.0",
        },
    }
    out_path = EVAL_DIR / "vision_gold_subset_proposal.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote proposal to {out_path}")
    print("Review the proposal, edit by hand if needed, then proceed to Task 2 lock step.")


if __name__ == "__main__":
    main()
