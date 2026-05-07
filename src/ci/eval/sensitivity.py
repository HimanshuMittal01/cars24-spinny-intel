"""Weight-sensitivity eval for the rank-based scorer.

The per-dim rank scores are independent of the weight table; only the
composite weighting changes when weights are perturbed. So the per-dim
rank scoring is computed once and reused across all weight variants.
"""

from dataclasses import dataclass, field

from scipy.stats import kendalltau

from ci.config import WEIGHTS
from ci.rank import rank_listings
from ci.schemas import NormalizedListing, RankRow, ScoreRecord
from ci.score import _per_dim_scores


@dataclass
class SensitivityResult:
    tau_perturbed: dict[str, float] = field(default_factory=dict)
    tau_leave_one_out: dict[str, float] = field(default_factory=dict)


def _rank_with_weights(
    listings: list[NormalizedListing],
    per_dim_score_table: dict[str, dict[str, float]],
    weights: dict[str, int],
) -> list[RankRow]:
    pairs: list[tuple[NormalizedListing, ScoreRecord]] = []
    total_weight = sum(weights.values())
    for n in listings:
        if total_weight == 0:
            composite = 0.0
            per_dim = {}
        else:
            per_dim = {d: per_dim_score_table[d][n.listing_id] for d in weights}
            composite = sum(weights[d] / total_weight * per_dim[d] for d in weights)
        sc = ScoreRecord(
            listing_id=n.listing_id, platform=n.platform,
            score_common=round(composite, 2),
            per_dim=per_dim,
            imputed_dims=[],
            disclosure_count=0, disclosed_fields={},
        )
        pairs.append((n, sc))
    return rank_listings(pairs)


def _kendall_tau(base_order: list[str], other_order: list[str]) -> float:
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
    # Per-dim rank scores are weight-independent; compute once.
    per_dim_score_table = {
        dim: _per_dim_scores(listings, dim) for dim in WEIGHTS
    }

    base_weights = dict(WEIGHTS)
    base_rows = _rank_with_weights(listings, per_dim_score_table, base_weights)
    base_order = [r.listing_id for r in base_rows]

    tau_pert: dict[str, float] = {}
    for dim in base_weights:
        for sign, suffix in ((+1, "+"), (-1, "-")):
            ws = dict(base_weights)
            ws[dim] = max(1, int(round(ws[dim] * (1 + sign * perturbation))))
            rows = _rank_with_weights(listings, per_dim_score_table, ws)
            tau_pert[f"{dim}{suffix}"] = _kendall_tau(
                base_order, [r.listing_id for r in rows]
            )

    tau_loo: dict[str, float] = {}
    for dim in base_weights:
        ws = {k: v for k, v in base_weights.items() if k != dim}
        rows = _rank_with_weights(listings, per_dim_score_table, ws)
        tau_loo[dim] = _kendall_tau(
            base_order, [r.listing_id for r in rows]
        )

    return SensitivityResult(tau_perturbed=tau_pert, tau_leave_one_out=tau_loo)
