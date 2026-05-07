from dataclasses import dataclass, field
from typing import Iterable

from scipy.stats import kendalltau

from ci.config import (
    ACCIDENT_MAP,
    AGE_BANDS,
    IMPUTATION,
    KM_BANDS,
    OWNERS_MAP,
    WEIGHTS,
)
from ci.schemas import NormalizedListing, RankRow, ScoreRecord


@dataclass
class SensitivityResult:
    tau_perturbed: dict[str, float] = field(default_factory=dict)
    tau_leave_one_out: dict[str, float] = field(default_factory=dict)


def _value_for_dim(name: str, n: NormalizedListing) -> float:
    """Return the band-mapped value for a dim, or imputation anchor if None."""
    v = getattr(n, name)
    if v is None:
        return float(IMPUTATION[name])
    if name == "km_driven":
        for ceil, val in KM_BANDS:
            if v <= ceil:
                return float(val)
        return float(KM_BANDS[-1][1])
    if name == "age_years":
        for ceil, val in AGE_BANDS:
            if v <= ceil:
                return float(val)
        return float(AGE_BANDS[-1][1])
    if name == "owners":
        if v >= 4:
            return 25.0
        return float(OWNERS_MAP.get(v, 25))
    if name == "accident_disclosed":
        return float(ACCIDENT_MAP[v])
    raise KeyError(name)


def _score_with_weights(
    listings: list[NormalizedListing],
    weights: dict[str, int],
) -> list[RankRow]:
    """Score and rank listings under a given weights dict."""
    pairs: list[tuple[NormalizedListing, ScoreRecord]] = []
    total_weight = sum(weights.values())
    if total_weight == 0:
        # Degenerate: no dimensions. Return listings in original order with score=0.
        for n in listings:
            sc = ScoreRecord(
                listing_id=n.listing_id, platform=n.platform,
                score_common=0.0, per_dim={}, imputed_dims=[],
                disclosure_count=0, disclosed_fields={},
            )
            pairs.append((n, sc))
    else:
        for n in listings:
            total = 0.0
            per_dim = {}
            for dim, w in weights.items():
                v = _value_for_dim(dim, n)
                per_dim[dim] = v
                total += (w / total_weight) * v
            sc = ScoreRecord(
                listing_id=n.listing_id, platform=n.platform,
                score_common=round(total, 2), per_dim=per_dim,
                imputed_dims=[], disclosure_count=0, disclosed_fields={},
            )
            pairs.append((n, sc))
    # Inline ranker (avoid circular import by not using rank_listings here)
    rows = []
    for n, s in pairs:
        ratio = n.price / s.score_common if s.score_common > 0 else float("inf")
        rows.append(RankRow(
            listing_id=n.listing_id,
            platform=n.platform,
            price=n.price,
            score_common=s.score_common,
            ratio=round(ratio, 2),
            disclosure_count=0,
            imputed_dims=[],
        ))
    rows.sort(key=lambda r: r.ratio)
    return rows


def _kendall_tau(base_order: list[str], other_order: list[str]) -> float:
    """Kendall's tau between two orderings (lists of listing_ids).

    The values compared are the *positions* of each id in the base ranking,
    aligned by index of base_order.
    """
    base_pos = {lid: i for i, lid in enumerate(base_order)}
    other_pos = {lid: i for i, lid in enumerate(other_order)}
    xs = [base_pos[lid] for lid in base_order]
    ys = [other_pos[lid] for lid in base_order]
    tau, _ = kendalltau(xs, ys)
    return float(tau)


def weight_sensitivity(
    listings: list[NormalizedListing],
    *,
    perturbation: float = 0.25,
) -> SensitivityResult:
    base_weights = dict(WEIGHTS)
    base_rows = _score_with_weights(listings, base_weights)
    base_order = [r.listing_id for r in base_rows]

    tau_pert: dict[str, float] = {}
    for dim in base_weights:
        for sign, suffix in ((+1, "+"), (-1, "-")):
            ws = dict(base_weights)
            ws[dim] = max(1, int(round(ws[dim] * (1 + sign * perturbation))))
            rows = _score_with_weights(listings, ws)
            order = [r.listing_id for r in rows]
            tau_pert[f"{dim}{suffix}"] = _kendall_tau(base_order, order)

    tau_loo: dict[str, float] = {}
    for dim in base_weights:
        ws = {k: v for k, v in base_weights.items() if k != dim}
        rows = _score_with_weights(listings, ws)
        order = [r.listing_id for r in rows]
        tau_loo[dim] = _kendall_tau(base_order, order)

    return SensitivityResult(tau_perturbed=tau_pert, tau_leave_one_out=tau_loo)
