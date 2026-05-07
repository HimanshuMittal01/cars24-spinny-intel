"""Regenerate eval/gold.jsonl with the 10 picked listings + recomputed expected scores.

The score_common and per_feature_rank_scores in gold.jsonl are RANK-BASED over the
gold set (spec §14). When the gold set changes from 17→10, those ranks change, so
expected values must be recomputed via the existing scorer over the new 10-set.

Inputs:
  - eval/vision_gold_subset_proposal.json  (the locked 10-listing pick)
  - eval/gold.jsonl                         (existing 17 rows, used as source of full_fields/notes)

Output:
  - eval/gold.jsonl                         (rewritten with 10 rows + recomputed expected)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ci.config import EVAL_DIR
from ci.normalize import normalize
from ci.schemas import RawListing
from ci.score import score_listings


def load_existing_gold() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[(row["platform"], row["listing_id"])] = row
    return out


def build_new_gold_rows(
    picked: list[dict],
    existing: dict[tuple[str, str], dict],
    *,
    today_year: int,
) -> list[dict]:
    """Normalize + score the picked listings; rebuild gold rows.

    Normalizes from `full_fields` already stored in `existing` (avoids re-parsing HTML
    and keeps the function unit-testable without fixture files). Preserves `full_fields`
    and `notes` from `existing` verbatim; recomputes `score_common` and
    `per_feature_rank_scores` from the new set's ranks.
    """
    norms = []
    for entry in picked:
        platform, lid = entry["platform"], entry["listing_id"]
        old = existing.get((platform, lid))
        if old is None:
            raise KeyError(
                f"picked listing {platform}/{lid} not in existing gold"
            )
        raw = RawListing(
            platform=platform,
            listing_id=lid,
            url=f"gold://{platform}/{lid}",
            captured_at="",
            fields=old["full_fields"],
        )
        norms.append(normalize(raw, today_year=today_year))

    scored = score_listings(norms)

    rows: list[dict] = []
    for s, n in zip(scored, norms):
        old = existing[(n.platform, n.listing_id)]
        rows.append({
            "listing_id": n.listing_id,
            "platform": n.platform,
            "full_fields": old["full_fields"],
            "score_common": s.score_common,
            "notes": old.get("notes", {}),
            "per_feature_rank_scores": s.per_dim,
        })
    return rows


def main() -> None:
    proposal = json.loads(
        (EVAL_DIR / "vision_gold_subset_proposal.json").read_text()
    )
    picked = proposal["picked"]
    if len(picked) != 10:
        raise ValueError(f"proposal must have 10 picked, got {len(picked)}")

    existing = load_existing_gold()
    today_year = datetime.now(timezone.utc).year
    rows = build_new_gold_rows(picked, existing, today_year=today_year)

    out = EVAL_DIR / "gold.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
