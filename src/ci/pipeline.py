import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.rank import rank_listings
from ci.schemas import NormalizedListing, RankRow, TraceEvent, VisionScore
from ci.score import score_listings
from ci.snapshot import load_snapshot
from ci.trace import TraceStore
from ci.vision.composite import DEFAULT_ALPHA
from ci.vision.score import compute_vision_scores


def _hash(obj) -> str:
    return hashlib.sha1(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _trace(store: TraceStore, run_id: str, node: str, t0: float, inp, out) -> None:
    store.write(TraceEvent(
        run_id=run_id,
        node=node,
        timestamp=_now(),
        input_hash=_hash(inp),
        output_hash=_hash(out),
        latency_ms=int((time.time() - t0) * 1000),
    ))


async def _run_vision_for_set(
    *, norms, manifests_root: Path, run_dir: Path,
    inner_cache_root: Path, no_cache: bool,
    listings_subset: set[str] | None = None,
    max_outer_turns: int = 12, max_inspects: int = 10,
):
    """Run the outer agent + inner inspector across the listing set; return list[VisionScore]."""
    from anthropic import AsyncAnthropic
    from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION
    from ci.vision.cache import InnerCache
    from ci.vision.agent import run_vision_agent
    from ci.vision.manifest import read_manifest

    client = AsyncAnthropic()
    cache = InnerCache(root=inner_cache_root,
                       prompt_version=INSPECTOR_PROMPT_VERSION, bypass=no_cache)

    async def run_one(n):
        if listings_subset is not None and n.listing_id not in listings_subset:
            return None
        manifest_path = manifests_root / n.platform / n.listing_id / "photos.json"
        manifest = read_manifest(manifest_path)
        if manifest is None or not manifest.get("photos"):
            return None  # no photos captured for this listing

        async def inspector_fn(idx: int) -> dict:
            entry = next((p for p in manifest["photos"] if p["idx"] == idx), None)
            if entry is None:
                return {"aspects_visible": [], "findings": {}}
            photo_path = manifests_root / n.platform / n.listing_id / "photos" / f"{entry['sha256']}.jpg"
            if not photo_path.exists():
                return {"aspects_visible": [], "findings": {}}
            return await inspect_photo(
                photo_path=photo_path, photo_sha=entry["sha256"],
                client=client, cache=cache,
            )

        return await run_vision_agent(
            listing_id=n.listing_id, platform=n.platform,
            manifest=manifest, client=client, inspector_fn=inspector_fn,
            max_outer_turns=max_outer_turns, max_inspects=max_inspects,
        )

    results = await asyncio.gather(*(run_one(n) for n in norms))
    assessments = [r for r in results if r is not None]
    return compute_vision_scores(assessments)


def run_pipeline(
    *,
    listings: list[tuple[str, str]],         # full active set (16: 10 gold + 6 ranking)
    ranking_listing_ids: set[str],            # of the 16, which are the deliverable rows
    run_dir: Path,
    today_year: int | None = None,
    enable_vision: bool = True,
    vision_no_cache: bool = False,
    vision_listings_subset: set[str] | None = None,
    vision_max_inspects: int = 10,
    alpha: float = DEFAULT_ALPHA,
) -> list[RankRow]:
    """Run the full pipeline. Vision phase optional via enable_vision flag."""
    run_id = run_dir.name
    store = TraceStore(run_dir=run_dir)
    norms: list[NormalizedListing] = []

    for platform, lid in listings:
        t0 = time.time()
        snap = load_snapshot(platform, lid)
        _trace(store, run_id, f"snapshot.load.{platform}", t0,
               {"platform": platform, "listing_id": lid},
               {"captured_at": snap.captured_at})

        t0 = time.time()
        if platform == "cars24":
            raw = extract_cars24(snap)
        elif platform == "spinny":
            raw = extract_spinny(snap)
        else:
            raise ValueError(f"unsupported platform: {platform}")
        _trace(store, run_id, f"extract.{platform}", t0,
               {"listing_id": lid}, {"fields_keys": list(raw.fields.keys())[:20]})

        t0 = time.time()
        norm = normalize(raw, today_year=today_year)
        _trace(store, run_id, f"normalize.{platform}", t0,
               {"listing_id": lid}, norm.model_dump(exclude={"full_fields"}))

        norms.append(norm)

    # Set-based rank scoring runs once over the entire normalized set.
    t0 = time.time()
    score_records = score_listings(norms)
    _trace(store, run_id, "score", t0,
           [{"id": n.listing_id} for n in norms],
           [{"id": s.listing_id, "score_common": s.score_common} for s in score_records])

    vision_scores: dict[str, VisionScore] = {}
    if enable_vision:
        from ci.config import FIXTURES_DIR
        from pathlib import Path as _Path
        cache_root = _Path("runs/.cache/vision")
        t0 = time.time()
        vs_list = asyncio.run(_run_vision_for_set(
            norms=norms, manifests_root=FIXTURES_DIR, run_dir=run_dir,
            inner_cache_root=cache_root, no_cache=vision_no_cache,
            listings_subset=vision_listings_subset,
            max_inspects=vision_max_inspects,
        ))
        for vs in vs_list:
            vision_scores[vs.listing_id] = vs
        _trace(store, run_id, "vision_score.aggregate", t0,
               [{"id": n.listing_id} for n in norms],
               [{"id": v.listing_id, "visual_score": v.visual_score} for v in vs_list])

    pairs = list(zip(norms, score_records))

    t0 = time.time()
    rows = rank_listings(pairs, vision_scores=vision_scores or None, alpha=alpha)
    _trace(store, run_id, "rank", t0,
           [{"id": p[0].listing_id} for p in pairs],
           [{"id": r.listing_id, "ratio": r.ratio} for r in rows])

    # Filter output to ranking listings (the held-out deliverable subset)
    return [r for r in rows if r.listing_id in ranking_listing_ids]
