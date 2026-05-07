from ci.eval.vision_determinism import determinism_metrics


def test_three_identical_runs_score_exact_1_adjacent_1_range_0():
    runs = [
        {"L1": {"exterior_panels": "pristine"}},
        {"L1": {"exterior_panels": "pristine"}},
        {"L1": {"exterior_panels": "pristine"}},
    ]
    visual_scores = [{"L1": 50.0}, {"L1": 50.0}, {"L1": 50.0}]
    m = determinism_metrics(runs, visual_scores)
    assert m["exact"]["exterior_panels"] == 1.0
    assert m["adjacent"]["exterior_panels"] == 1.0
    assert m["per_listing_score_range"]["L1"] == 0.0


def test_off_by_one_across_runs_adjacent_1_exact_0():
    runs = [
        {"L1": {"exterior_panels": "pristine"}},
        {"L1": {"exterior_panels": "light_wear"}},
        {"L1": {"exterior_panels": "pristine"}},
    ]
    visual_scores = [{"L1": 50.0}, {"L1": 50.0}, {"L1": 50.0}]
    m = determinism_metrics(runs, visual_scores)
    assert m["exact"]["exterior_panels"] == 0.0
    # 2 of 3 pairwise comparisons are adjacent (within 1)
    assert m["adjacent"]["exterior_panels"] == 1.0
