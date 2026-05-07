# src/ci/vision/score.py
"""Set-relative rank-based aggregation of vision findings.

Mirrors src/ci/score.py:_per_dim_scores semantics: per aspect, rank listings
by numeric severity (lower is better), map rank to 0-100, missing values get
median of valid scores. Per-listing visual_score = mean of 5 aspect scores.
"""
from __future__ import annotations

from typing import get_args

from ci.schemas import Aspect, VisionAssessment, VisionScore

_ASPECTS: tuple[str, ...] = get_args(Aspect)

_SEVERITY_ORDER: dict[str, int] = {
    "pristine": 0,
    "light_wear": 1,
    "moderate": 2,
    "heavy": 3,
    "defect": 4,
}


def _severity_to_int(severity: str) -> int | None:
    return _SEVERITY_ORDER.get(severity)  # not_visible → None


def _rank_to_score(rank: float, n: int) -> float:
    if n <= 1:
        return 100.0
    return round(100.0 * (n - rank) / (n - 1), 2)


def _per_aspect_scores_for_set(
    assessments: list[VisionAssessment], aspect: str
) -> dict[str, float]:
    """Return {listing_id: 0-100 score} for one aspect across the listing set."""
    pairs: list[tuple[str, int | None]] = []
    for a in assessments:
        sev = next((f.severity for f in a.findings if f.aspect == aspect), "not_visible")
        pairs.append((a.listing_id, _severity_to_int(sev)))

    valid = [(lid, v) for lid, v in pairs if v is not None]
    missing_ids = [lid for lid, v in pairs if v is None]
    k = len(valid)

    out: dict[str, float] = {}
    if k == 0:
        return {lid: 50.0 for lid, _ in pairs}

    # Lower severity is better → sort ascending and rank 1..k
    valid_sorted = sorted(valid, key=lambda x: x[1])
    i = 0
    while i < len(valid_sorted):
        j = i
        while j < len(valid_sorted) and valid_sorted[j][1] == valid_sorted[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for idx in range(i, j):
            out[valid_sorted[idx][0]] = _rank_to_score(avg_rank, k)
        i = j

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


def compute_vision_scores(assessments: list[VisionAssessment]) -> list[VisionScore]:
    """Per-listing VisionScore from a set of assessments. Set-relative ranks per aspect."""
    per_aspect_table: dict[str, dict[str, float]] = {
        aspect: _per_aspect_scores_for_set(assessments, aspect) for aspect in _ASPECTS
    }
    out: list[VisionScore] = []
    for a in assessments:
        per_aspect_score = {asp: per_aspect_table[asp][a.listing_id] for asp in _ASPECTS}
        visual = round(sum(per_aspect_score.values()) / len(_ASPECTS), 2)
        imputed = [
            f.aspect for f in a.findings if f.severity == "not_visible"
        ]
        out.append(VisionScore(
            listing_id=a.listing_id, platform=a.platform,
            visual_score=visual,
            per_aspect_score=per_aspect_score,  # type: ignore[arg-type]
            imputed_aspects=imputed,  # type: ignore[arg-type]
            assessment=a,
        ))
    return out
