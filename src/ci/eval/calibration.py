from dataclasses import dataclass, field

from scipy.stats import spearmanr


@dataclass
class CalibrationMetrics:
    mae_overall: float
    spearman_overall: float
    mae_per_platform: dict[str, float] = field(default_factory=dict)
    spearman_per_platform: dict[str, float] = field(default_factory=dict)
    n: int = 0


def calibration_metrics(
    sys_scores: list[float],
    gold_scores: list[float],
    platforms: list[str],
) -> CalibrationMetrics:
    n = len(sys_scores)
    assert len(gold_scores) == n == len(platforms)

    mae_overall = sum(abs(a - b) for a, b in zip(sys_scores, gold_scores)) / n
    rho_overall = float(spearmanr(sys_scores, gold_scores).correlation) if n >= 2 else 1.0

    mae_per: dict[str, float] = {}
    rho_per: dict[str, float] = {}
    for p in set(platforms):
        idx = [i for i, pl in enumerate(platforms) if pl == p]
        if len(idx) == 0:
            continue
        s = [sys_scores[i] for i in idx]
        g = [gold_scores[i] for i in idx]
        mae_per[p] = sum(abs(a - b) for a, b in zip(s, g)) / len(idx)
        rho_per[p] = float(spearmanr(s, g).correlation) if len(idx) >= 2 else 1.0

    return CalibrationMetrics(
        mae_overall=mae_overall,
        spearman_overall=rho_overall,
        mae_per_platform=mae_per,
        spearman_per_platform=rho_per,
        n=n,
    )
