"""E5: stability of vision agent across cold-cache reruns.

For each aspect: exact-agreement and adjacent-agreement rates across N runs.
For each listing: visual_score range (max - min).
"""
from __future__ import annotations


_SEVERITY_ORDER = {
    "pristine": 0, "light_wear": 1, "moderate": 2, "heavy": 3, "defect": 4,
    "not_visible": None,
}


def _to_int(s: str) -> int | None:
    return _SEVERITY_ORDER.get(s)


def determinism_metrics(
    runs: list[dict[str, dict[str, str]]],
    visual_scores: list[dict[str, float]],
) -> dict:
    """Each run is {listing_id: {aspect: severity}}. visual_scores parallel list of {listing_id: score}."""
    if not runs:
        return {"exact": {}, "adjacent": {}, "per_listing_score_range": {}}

    aspects = set()
    for r in runs:
        for asp_map in r.values():
            aspects.update(asp_map.keys())

    listings = set()
    for r in runs:
        listings.update(r.keys())

    exact_per_aspect = {}
    adjacent_per_aspect = {}
    for aspect in sorted(aspects):
        ex_hits = ex_total = 0
        adj_hits = adj_total = 0
        for lid in listings:
            severities = [r.get(lid, {}).get(aspect) for r in runs]
            ints = [_to_int(s) if s else None for s in severities]
            valid = [i for i in ints if i is not None]
            if len(valid) < 2:
                continue
            ex_total += 1
            adj_total += 1
            # Exact: all runs agree (all values identical)
            if len(set(valid)) == 1:
                ex_hits += 1
            # Adjacent: max deviation across all runs ≤ 1
            if max(valid) - min(valid) <= 1:
                adj_hits += 1
        exact_per_aspect[aspect] = ex_hits / ex_total if ex_total else 0.0
        adjacent_per_aspect[aspect] = adj_hits / adj_total if adj_total else 0.0

    per_listing_score_range = {}
    for lid in listings:
        scores = [vs.get(lid) for vs in visual_scores if vs.get(lid) is not None]
        if scores:
            per_listing_score_range[lid] = max(scores) - min(scores)
        else:
            per_listing_score_range[lid] = 0.0

    return {
        "exact": exact_per_aspect,
        "adjacent": adjacent_per_aspect,
        "per_listing_score_range": per_listing_score_range,
    }
