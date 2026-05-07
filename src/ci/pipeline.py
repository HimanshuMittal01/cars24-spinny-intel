import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.rank import rank_listings
from ci.schemas import NormalizedListing, RankRow, TraceEvent
from ci.score import score_listings
from ci.snapshot import load_snapshot
from ci.trace import TraceStore


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


def run_pipeline(
    *,
    ranking_listings: list[tuple[str, str]],
    run_dir: Path,
    today_year: int | None = None,
) -> list[RankRow]:
    """Run the full pipeline. Scoring is set-based, rank-based."""
    run_id = run_dir.name
    store = TraceStore(run_dir=run_dir)
    norms: list[NormalizedListing] = []

    for platform, lid in ranking_listings:
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

    pairs = list(zip(norms, score_records))

    t0 = time.time()
    rows = rank_listings(pairs)
    _trace(store, run_id, "rank", t0,
           [{"id": p[0].listing_id} for p in pairs],
           [{"id": r.listing_id, "ratio": r.ratio} for r in rows])

    return rows
