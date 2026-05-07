"""Run extraction + calibration + sensitivity evals against the current eval/gold.jsonl.

Writes a single JSON summary under runs/rule_eval_<timestamp>/eval_summary.json
that the doc-update tasks (Plan A Tasks 5-7) consume.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ci.config import EVAL_DIR, RUNS_DIR
from ci.eval.calibration import calibration_metrics
from ci.eval.extraction import _approx_equal, CHECKED_FIELDS, TOLERANCE
from ci.eval.sensitivity import weight_sensitivity
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.schemas import GoldRecord, RawListing
from ci.score import score_listings
from ci.snapshot import load_snapshot


def load_gold_records() -> list[GoldRecord]:
    out: list[GoldRecord] = []
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(GoldRecord(
            listing_id=d["listing_id"],
            platform=d["platform"],
            full_fields=d["full_fields"],
            score_common=d["score_common"],
            notes=d.get("notes", {}),
        ))
    return out


def _extract_recall(gold: list[GoldRecord], today_year: int) -> dict:
    """Field-level recall: extracted normalized values vs gold normalized values."""
    matches = {f: 0 for f in CHECKED_FIELDS}
    matches_per_platform: dict[str, dict[str, int]] = {}
    n_per_platform: dict[str, int] = {}
    for g in gold:
        snap = load_snapshot(g.platform, g.listing_id)
        raw = extract_cars24(snap) if g.platform == "cars24" else extract_spinny(snap)
        norm = normalize(raw, today_year=today_year)

        gold_raw = RawListing(
            platform=g.platform, listing_id=g.listing_id,
            url="gold://", captured_at="gold", fields=g.full_fields,
        )
        gold_norm = normalize(gold_raw, today_year=today_year)

        per_p = matches_per_platform.setdefault(g.platform, {f: 0 for f in CHECKED_FIELDS})
        n_per_platform[g.platform] = n_per_platform.get(g.platform, 0) + 1
        for f in CHECKED_FIELDS:
            if _approx_equal(getattr(norm, f), getattr(gold_norm, f), TOLERANCE[f]):
                matches[f] += 1
                per_p[f] += 1

    n = len(gold)
    return {
        "n": n,
        "field_recall": {f: matches[f] / n for f in CHECKED_FIELDS},
        "field_recall_per_platform": {
            p: {f: matches_per_platform[p][f] / n_per_platform[p] for f in CHECKED_FIELDS}
            for p in matches_per_platform
        },
    }


def _calibration(gold: list[GoldRecord], today_year: int) -> dict:
    norms = []
    for g in gold:
        norms.append(normalize(
            RawListing(
                platform=g.platform, listing_id=g.listing_id,
                url="gold://", captured_at="gold", fields=g.full_fields,
            ),
            today_year=today_year,
        ))
    scored = score_listings(norms)
    sys = [s.score_common for s in scored]
    gld = [g.score_common for g in gold]
    plats = [g.platform for g in gold]
    m = calibration_metrics(sys, gld, plats)
    return {
        "n": m.n,
        "mae_overall": m.mae_overall,
        "spearman_overall": m.spearman_overall,
        "mae_per_platform": m.mae_per_platform,
        "spearman_per_platform": m.spearman_per_platform,
    }


def _sensitivity(gold: list[GoldRecord], today_year: int) -> dict:
    norms = []
    for g in gold:
        norms.append(normalize(
            RawListing(
                platform=g.platform, listing_id=g.listing_id,
                url="gold://", captured_at="gold", fields=g.full_fields,
            ),
            today_year=today_year,
        ))
    s = weight_sensitivity(norms)
    return {
        "tau_perturbed": s.tau_perturbed,
        "tau_leave_one_out": s.tau_leave_one_out,
    }


def main() -> None:
    today_year = datetime.now(timezone.utc).year
    gold = load_gold_records()
    print(f"Loaded {len(gold)} gold records")

    summary = {
        "extraction": _extract_recall(gold, today_year),
        "calibration": _calibration(gold, today_year),
        "sensitivity": _sensitivity(gold, today_year),
        "n_gold": len(gold),
        "today_year": today_year,
    }

    run_id = (
        "rule_eval_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:6]
    )
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "eval_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
