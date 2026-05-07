"""Run vision agent against the 10 gold listings, compare to vision_gold.jsonl, report E6.

Outputs:
  - runs/e6_<ts>/agent_assessments.json  (full agent output for each listing)
  - runs/e6_<ts>/agreement_summary.json  (per-aspect, per-platform metrics)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR, RUNS_DIR
from ci.eval.vision_agreement import agreement_metrics
from ci.vision.agent import run_vision_agent
from ci.vision.cache import InnerCache
from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION
from ci.vision.manifest import read_manifest

ASPECTS = ("exterior_panels", "interior_cabin",
           "dashboard_console", "tyres", "engine_bay")


def load_gold() -> dict[str, dict]:
    out = {}
    for line in (EVAL_DIR / "vision_gold.jsonl").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        row = json.loads(line)
        out[row["listing_id"]] = row
    return out


async def assess_one(client, cache, platform: str, lid: str) -> dict | None:
    manifest_path = FIXTURES_DIR / platform / lid / "photos.json"
    manifest = read_manifest(manifest_path)
    if not manifest or not manifest.get("photos"):
        return None

    async def inspector_fn(idx: int) -> dict:
        entry = next((p for p in manifest["photos"] if p["idx"] == idx), None)
        if entry is None:
            return {"aspects_visible": [], "findings": {}}
        photo_path = FIXTURES_DIR / platform / lid / "photos" / f"{entry['sha256']}.jpg"
        if not photo_path.exists():
            return {"aspects_visible": [], "findings": {}}
        return await inspect_photo(
            photo_path=photo_path, photo_sha=entry["sha256"],
            client=client, cache=cache,
        )

    return await run_vision_agent(
        listing_id=lid, platform=platform,
        manifest=manifest, client=client, inspector_fn=inspector_fn,
    )


async def main_async():
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    cache_root = Path("runs/.cache/vision")
    cache = InnerCache(root=cache_root, prompt_version=INSPECTOR_PROMPT_VERSION)

    gold = load_gold()
    targets = [(g["platform"], g["listing_id"]) for g in gold.values()]

    print(f"Running agent on {len(targets)} listings...")
    results = await asyncio.gather(*(assess_one(client, cache, p, l) for p, l in targets))

    by_id = {a.listing_id: a for a in results if a is not None}
    print(f"Got {len(by_id)} assessments")

    # Per aspect, per platform metrics
    per_aspect: dict = {}
    per_aspect_per_platform: dict = {}
    for aspect in ASPECTS:
        pairs = []
        plat_pairs: dict[str, list[tuple[str, str]]] = {}
        for lid, g_row in gold.items():
            assessment = by_id.get(lid)
            gold_sev = g_row["vision_gold"][aspect]
            if assessment is None or gold_sev is None:
                continue
            agent_finding = next(
                (f.severity for f in assessment.findings if f.aspect == aspect),
                "not_visible",
            )
            pairs.append((agent_finding, gold_sev))
            plat_pairs.setdefault(g_row["platform"], []).append((agent_finding, gold_sev))

        per_aspect[aspect] = agreement_metrics(pairs)
        per_aspect_per_platform[aspect] = {
            p: agreement_metrics(pp) for p, pp in plat_pairs.items()
        }

    summary = {
        "n_listings": len(by_id),
        "per_aspect": per_aspect,
        "per_aspect_per_platform": per_aspect_per_platform,
    }

    run_id = "e6_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "agent_assessments.json").write_text(
        json.dumps([a.model_dump() for a in by_id.values()], indent=2)
    )
    (run_dir / "agreement_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Wrote {run_dir}/agreement_summary.json")
    print(json.dumps(summary, indent=2))


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
