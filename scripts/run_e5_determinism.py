"""E5: 5 listings × 3 cold-cache runs of the vision agent. Reports per-aspect stability.

Picks 5 listings from the 10-gold subset (never from the 6 ranking, per spec §12.4).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR, RUNS_DIR
from ci.eval.vision_determinism import determinism_metrics
from ci.vision.agent import run_vision_agent
from ci.vision.cache import InnerCache
from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION
from ci.vision.manifest import read_manifest
from ci.vision.score import compute_vision_scores


def gold_listings():
    out = []
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out.append((r["platform"], r["listing_id"]))
    return out


async def run_once(targets, run_idx):
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    # Cold cache for each run — bypass=True
    cache = InnerCache(root=Path(f"runs/.cache/vision_e5_run{run_idx}"),
                       prompt_version=INSPECTOR_PROMPT_VERSION, bypass=True)
    assessments = []
    for platform, lid in targets:
        manifest_path = FIXTURES_DIR / platform / lid / "photos.json"
        manifest = read_manifest(manifest_path)
        if not manifest:
            continue

        async def inspector_fn(idx, _platform=platform, _lid=lid, _m=manifest):
            entry = next((p for p in _m["photos"] if p["idx"] == idx), None)
            if entry is None:
                return {"aspects_visible": [], "findings": {}}
            photo_path = FIXTURES_DIR / _platform / _lid / "photos" / f"{entry['sha256']}.jpg"
            return await inspect_photo(
                photo_path=photo_path, photo_sha=entry["sha256"],
                client=client, cache=cache,
            )

        a = await run_vision_agent(
            listing_id=lid, platform=platform,
            manifest=manifest, client=client, inspector_fn=inspector_fn,
        )
        assessments.append(a)
    return assessments


async def main_async():
    targets = gold_listings()[:5]
    runs_severities = []
    runs_visual_scores = []
    for i in range(3):
        print(f"--- run {i+1}/3 ---")
        assessments = await run_once(targets, i)
        sev_map = {a.listing_id: {f.aspect: f.severity for f in a.findings} for a in assessments}
        runs_severities.append(sev_map)
        scores = compute_vision_scores(assessments)
        runs_visual_scores.append({s.listing_id: s.visual_score for s in scores})

    metrics = determinism_metrics(runs_severities, runs_visual_scores)

    run_id = "e5_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "determinism_summary.json").write_text(json.dumps({
        "n_listings": len(targets),
        "n_runs": 3,
        "metrics": metrics,
    }, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Wrote {run_dir}/determinism_summary.json")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
