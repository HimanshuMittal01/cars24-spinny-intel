import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ci.pipeline import run_pipeline


@dataclass
class DeterminismResult:
    identical: bool
    distinct_outputs: int


def determinism_check(
    *,
    platform: str,
    listing_id: str,
    run_root: Path,
    reps: int,
) -> DeterminismResult:
    hashes: set[str] = set()
    for i in range(reps):
        run_dir = run_root / f"determinism-{i}"
        rows = run_pipeline(
            ranking_listings=[(platform, listing_id)],
            run_dir=run_dir,
        )
        payload = json.dumps([r.model_dump() for r in rows], sort_keys=True)
        hashes.add(hashlib.sha1(payload.encode()).hexdigest())
    return DeterminismResult(
        identical=len(hashes) == 1,
        distinct_outputs=len(hashes),
    )
