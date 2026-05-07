# src/ci/vision/composite.py
"""Composite score: alpha-weighted blend of rule_score and visual_score."""

DEFAULT_ALPHA: float = 0.7


def compute_composite(
    *, rule_score: float, visual_score: float, alpha: float = DEFAULT_ALPHA
) -> float:
    """composite = alpha * rule + (1 - alpha) * visual; rounded to 2dp."""
    return round(alpha * rule_score + (1 - alpha) * visual_score, 2)
