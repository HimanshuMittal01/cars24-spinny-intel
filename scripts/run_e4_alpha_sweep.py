"""E4: weights × α joint sweep on the 10 gold listings.

For each α in {0.5, 0.6, 0.7, 0.8, 0.9, 1.0}, compose with each weight perturbation
and measure rank stability against α=0.7 baseline. Uses gold-visual as the visual signal
(so the result is calibration stability, not contaminated by agent variance).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import kendalltau

from ci.config import EVAL_DIR, RUNS_DIR
from ci.normalize import normalize
from ci.schemas import RawListing, VisionAssessment, VisionFinding
from ci.score import score_listings
from ci.vision.composite import compute_composite
from ci.vision.score import compute_vision_scores


def _load_gold():
    rows = []
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_vision_gold():
    rows = []
    for line in (EVAL_DIR / "vision_gold.jsonl").read_text().splitlines():
        if not line.startswith("#") and line.strip():
            rows.append(json.loads(line))
    return rows


def main():
    gold = _load_gold()
    norms = []
    for r in gold:
        norms.append(normalize(
            RawListing(
                platform=r["platform"], listing_id=r["listing_id"],
                url="gold://", captured_at="gold", fields=r["full_fields"],
            ),
            today_year=2026,
        ))
    rule_scores = {s.listing_id: s.score_common for s in score_listings(norms)}

    vg = _load_vision_gold()
    gold_assessments = [
        VisionAssessment(
            listing_id=r["listing_id"], platform=r["platform"],
            findings=[
                VisionFinding(aspect=a, severity=r["vision_gold"][a],
                              confidence="high", photo_refs=[], evidence_note="")
                for a in r["vision_gold"]
            ],
            photos_inspected=[], photo_count_total=0, agent_turns=0,
        )
        for r in vg
    ]
    visual_scores = {s.listing_id: s.visual_score for s in compute_vision_scores(gold_assessments)}

    alphas = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    rankings_by_alpha = {}
    for a in alphas:
        composites = {
            lid: compute_composite(rule_score=rule_scores[lid],
                                    visual_score=visual_scores[lid], alpha=a)
            for lid in rule_scores
        }
        order = sorted(composites, key=lambda lid: composites[lid], reverse=True)
        rankings_by_alpha[a] = order

    # Kendall tau between α=0.7 baseline and each other α
    base = rankings_by_alpha[0.7]
    base_pos = {lid: i for i, lid in enumerate(base)}
    tau_by_alpha = {}
    for a, order in rankings_by_alpha.items():
        if a == 0.7:
            tau_by_alpha[a] = 1.0
            continue
        other_pos = {lid: i for i, lid in enumerate(order)}
        xs = [base_pos[lid] for lid in base]
        ys = [other_pos[lid] for lid in base]
        tau, _ = kendalltau(xs, ys)
        tau_by_alpha[a] = float(tau)

    summary = {
        "alphas": alphas,
        "ranking_by_alpha": rankings_by_alpha,
        "kendall_tau_vs_alpha_0_7": tau_by_alpha,
    }

    run_id = "e4_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "alpha_sweep.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"Wrote {run_dir}/alpha_sweep.json")


if __name__ == "__main__":
    main()
