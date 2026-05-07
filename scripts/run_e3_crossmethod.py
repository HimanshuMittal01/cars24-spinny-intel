"""E3: three-way Spearman on the 10 gold listings. Uses E6's agent assessments.

Reuses the latest runs/e6_*/agent_assessments.json. Run E6 first.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from ci.config import EVAL_DIR, RUNS_DIR
from ci.eval.cross_method import three_way_spearman
from ci.schemas import VisionAssessment, VisionFinding
from ci.vision.score import compute_vision_scores


def main():
    # Load gold rule_scores
    gold_rule = {}
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            gold_rule[r["listing_id"]] = r["score_common"]

    # Load gold-visual: build VisionAssessments from vision_gold.jsonl, score them
    gold_assessments = []
    for line in (EVAL_DIR / "vision_gold.jsonl").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        r = json.loads(line)
        findings = [
            VisionFinding(
                aspect=a, severity=r["vision_gold"][a],
                confidence="high", photo_refs=[], evidence_note="",
            )
            for a in r["vision_gold"]
        ]
        gold_assessments.append(VisionAssessment(
            listing_id=r["listing_id"], platform=r["platform"],
            findings=findings, photos_inspected=[],
            photo_count_total=0, agent_turns=0,
        ))
    gold_visual = {s.listing_id: s.visual_score for s in compute_vision_scores(gold_assessments)}

    # Load agent assessments from latest E6 run
    paths = sorted(glob.glob(str(RUNS_DIR / "e6_*/agent_assessments.json")))
    if not paths:
        raise SystemExit("Run E6 first (no runs/e6_*/agent_assessments.json found)")
    latest = paths[-1]
    print(f"Using agent assessments from {latest}")
    agent_data = json.loads(Path(latest).read_text())
    agent_assessments = [VisionAssessment.model_validate(d) for d in agent_data]
    agent_visual = {s.listing_id: s.visual_score for s in compute_vision_scores(agent_assessments)}

    out = three_way_spearman(gold_rule, gold_visual, agent_visual)
    print(json.dumps(out, indent=2))

    # Persist
    parent = Path(latest).parent
    (parent / "cross_method_e3.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {parent}/cross_method_e3.json")


if __name__ == "__main__":
    main()
