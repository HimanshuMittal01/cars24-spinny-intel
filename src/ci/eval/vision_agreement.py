"""E6: per-aspect agreement between agent assessments and gold labels.

Reports three metrics on the ordinal severity scale:
  - exact agreement: agent == gold rate
  - adjacent agreement: |agent - gold| ≤ 1 rate (more stable at small N)
  - Cohen's κ: ordinal-aware kappa (linear weights)

Pairs where either side is "not_visible" are excluded from the comparison —
their gap is honest, not noise.
"""
from __future__ import annotations

_SEVERITY_ORDER = {
    "pristine": 0, "light_wear": 1, "moderate": 2, "heavy": 3, "defect": 4,
}


def severity_to_int(severity: str) -> int | None:
    return _SEVERITY_ORDER.get(severity)


def _cohen_kappa(agent_ints: list[int], gold_ints: list[int]) -> float:
    """Linear-weighted Cohen's κ. Returns 0.0 if undefined (constant rater)."""
    n = len(agent_ints)
    if n == 0:
        return 0.0
    if len(set(agent_ints)) == 1 or len(set(gold_ints)) == 1:
        return 0.0
    # Manual implementation (avoid sklearn dep): linear-weighted κ
    # κ = 1 - (Σ w_ij * O_ij) / (Σ w_ij * E_ij), weights linear |i-j|/(K-1)
    K = 5
    obs = [[0] * K for _ in range(K)]
    for a, g in zip(agent_ints, gold_ints):
        obs[a][g] += 1
    row_marg = [sum(obs[i]) for i in range(K)]
    col_marg = [sum(obs[i][j] for i in range(K)) for j in range(K)]
    weighted_obs = 0.0
    weighted_exp = 0.0
    for i in range(K):
        for j in range(K):
            w = abs(i - j) / (K - 1)
            weighted_obs += w * obs[i][j]
            weighted_exp += w * (row_marg[i] * col_marg[j] / n)
    if weighted_exp == 0:
        return 0.0
    return 1 - (weighted_obs / weighted_exp)


def agreement_metrics(pairs: list[tuple[str, str]]) -> dict:
    """Compute exact / adjacent / kappa from (agent, gold) severity strings.

    `not_visible` on either side excludes that pair from comparison.
    """
    agent_ints = []
    gold_ints = []
    for a, g in pairs:
        ai = severity_to_int(a)
        gi = severity_to_int(g)
        if ai is None or gi is None:
            continue
        agent_ints.append(ai)
        gold_ints.append(gi)

    n = len(agent_ints)
    if n == 0:
        return {"exact": 0.0, "adjacent": 0.0, "kappa": 0.0, "n_compared": 0}

    exact = sum(1 for a, g in zip(agent_ints, gold_ints) if a == g) / n
    adjacent = sum(1 for a, g in zip(agent_ints, gold_ints) if abs(a - g) <= 1) / n
    kappa = _cohen_kappa(agent_ints, gold_ints)
    return {"exact": exact, "adjacent": adjacent, "kappa": kappa, "n_compared": n}
