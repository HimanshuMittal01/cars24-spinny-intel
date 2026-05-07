"""Set-based, rank-based composite scorer (per spec §14).

Per-feature scoring is by *rank position* within the listing set, not by
anchored bands. Best on a feature → 100, worst → 0, others linearly
interpolated by rank. Ties get averaged ranks.

This eliminates the band-cutoff priors that were a defensibility concern;
weights remain a prior but their ablation surface is now narrower.
"""

from ci.config import ACCIDENT_ORDER, WEIGHTS
from ci.schemas import NormalizedListing, ScoreRecord


def _comparable_value(name: str, n: NormalizedListing) -> float | None:
    """Return a value where HIGHER = BETTER on this feature, or None if missing."""
    v = getattr(n, name)
    if v is None:
        return None
    if name in ("km_driven", "age_years", "owners"):
        # Lower value is better → invert sign
        return -float(v)
    if name == "accident_disclosed":
        return float(ACCIDENT_ORDER.get(v, 0))
    raise KeyError(name)


def _rank_to_score(rank: float, n: int) -> float:
    """Rank position (1=best, n=worst, ties averaged) → 0-100 score."""
    if n <= 1:
        return 100.0
    return round(100.0 * (n - rank) / (n - 1), 2)


def _per_dim_scores(
    listings: list[NormalizedListing], dim: str
) -> dict[str, float]:
    """Return {listing_id: score 0-100} for a given dim across the listing set.

    Valid (non-null) listings are ranked among themselves and span 0-100. Listings
    with a missing value receive the median of valid scores (neutral; no opacity
    penalty, matching spec §3 null-handling policy).
    """
    if not listings:
        return {}
    pairs = [(li.listing_id, _comparable_value(dim, li)) for li in listings]
    valid = [(lid, v) for lid, v in pairs if v is not None]
    missing_ids = [lid for lid, v in pairs if v is None]
    k = len(valid)

    out: dict[str, float] = {}

    # If no valid values at all, every listing gets 50 (no information).
    if k == 0:
        return {lid: 50.0 for lid in (lid for lid, _ in pairs)}

    # Rank valid listings within themselves (1=best, k=worst), with tie averaging.
    valid_sorted = sorted(valid, key=lambda x: x[1], reverse=True)
    i = 0
    while i < len(valid_sorted):
        j = i
        while j < len(valid_sorted) and valid_sorted[j][1] == valid_sorted[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2  # 1-indexed average across the tied block
        for idx in range(i, j):
            out[valid_sorted[idx][0]] = _rank_to_score(avg_rank, k)
        i = j

    # Missing → median of valid scores.
    if missing_ids:
        valid_scores = sorted(out.values())
        m = len(valid_scores)
        if m % 2 == 1:
            median = valid_scores[m // 2]
        else:
            median = (valid_scores[m // 2 - 1] + valid_scores[m // 2]) / 2
        for lid in missing_ids:
            out[lid] = median

    return out


def score_listings(listings: list[NormalizedListing]) -> list[ScoreRecord]:
    """Score the entire listing set in one pass, using rank-based per-dim scoring."""
    per_dim_scores = {
        dim: _per_dim_scores(listings, dim) for dim in WEIGHTS
    }
    out: list[ScoreRecord] = []
    for li in listings:
        per_dim = {dim: per_dim_scores[dim][li.listing_id] for dim in WEIGHTS}
        composite = sum(WEIGHTS[d] / 100.0 * per_dim[d] for d in WEIGHTS)
        imputed = [d for d in WEIGHTS if getattr(li, d) is None]
        out.append(ScoreRecord(
            listing_id=li.listing_id,
            platform=li.platform,
            score_common=round(composite, 2),
            per_dim=per_dim,
            imputed_dims=imputed,
            disclosure_count=sum(1 for v in li.disclosed_fields.values() if v),
            disclosed_fields=dict(li.disclosed_fields),
        ))
    return out
