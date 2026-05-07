# tests/test_vision_score.py
"""Set-relative rank-based aggregation of VisionAssessments to VisionScores."""
from ci.schemas import VisionAssessment, VisionFinding
from ci.vision.score import compute_vision_scores, _severity_to_int


def _assess(lid: str, sev_map: dict[str, str]) -> VisionAssessment:
    return VisionAssessment(
        listing_id=lid, platform="cars24",
        findings=[
            VisionFinding(aspect=a, severity=sev_map[a], confidence="med",  # type: ignore[arg-type]
                          photo_refs=[], evidence_note="")
            for a in ("exterior_panels", "interior_cabin",
                      "dashboard_console", "tyres", "engine_bay")
        ],
        photos_inspected=[], photo_count_total=0, agent_turns=0,
    )


def test_severity_to_int_mapping():
    assert _severity_to_int("pristine") == 0
    assert _severity_to_int("light_wear") == 1
    assert _severity_to_int("moderate") == 2
    assert _severity_to_int("heavy") == 3
    assert _severity_to_int("defect") == 4
    assert _severity_to_int("not_visible") is None


def test_two_listing_set_pristine_vs_defect_get_extreme_scores():
    a = _assess("A", {a: "pristine" for a in ("exterior_panels", "interior_cabin",
                                              "dashboard_console", "tyres", "engine_bay")})
    b = _assess("B", {a: "defect" for a in ("exterior_panels", "interior_cabin",
                                            "dashboard_console", "tyres", "engine_bay")})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    assert by_id["A"].visual_score == 100.0
    assert by_id["B"].visual_score == 0.0


def test_not_visible_imputes_to_median_score():
    """One listing visible, one not_visible — not_visible gets median of visible."""
    a = _assess("A", {a: "moderate" for a in ("exterior_panels", "interior_cabin",
                                              "dashboard_console", "tyres", "engine_bay")})
    b = _assess("B", {a: "not_visible" for a in ("exterior_panels", "interior_cabin",
                                                 "dashboard_console", "tyres", "engine_bay")})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    # Single visible listing → 100; not_visible → median = 100
    assert by_id["A"].visual_score == 100.0
    assert by_id["B"].visual_score == 100.0
    assert "engine_bay" in by_id["B"].imputed_aspects


def test_visual_score_is_mean_of_per_aspect_scores():
    a = _assess("A", {"exterior_panels": "pristine", "interior_cabin": "pristine",
                      "dashboard_console": "defect", "tyres": "defect", "engine_bay": "defect"})
    b = _assess("B", {"exterior_panels": "defect", "interior_cabin": "defect",
                      "dashboard_console": "pristine", "tyres": "pristine", "engine_bay": "pristine"})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    # A: 100, 100, 0, 0, 0 → mean 40; B: 0, 0, 100, 100, 100 → mean 60
    assert by_id["A"].visual_score == 40.0
    assert by_id["B"].visual_score == 60.0
