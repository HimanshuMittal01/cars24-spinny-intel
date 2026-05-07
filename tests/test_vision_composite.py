# tests/test_vision_composite.py
from ci.vision.composite import compute_composite, DEFAULT_ALPHA


def test_default_alpha_is_0_7_rule_leaning():
    assert DEFAULT_ALPHA == 0.7


def test_compute_composite_with_default_alpha():
    # 0.7 * 80 + 0.3 * 60 = 56 + 18 = 74
    assert compute_composite(rule_score=80.0, visual_score=60.0) == 74.0


def test_compute_composite_with_alpha_1_returns_rule_only():
    assert compute_composite(rule_score=80.0, visual_score=60.0, alpha=1.0) == 80.0


def test_compute_composite_with_alpha_0_returns_visual_only():
    assert compute_composite(rule_score=80.0, visual_score=60.0, alpha=0.0) == 60.0


def test_compute_composite_rounds_to_2dp():
    # 0.333... * 90 + 0.666... * 60 = 30 + 40 = 70 — just check 2dp
    out = compute_composite(rule_score=90.0, visual_score=60.0, alpha=1/3)
    assert out == round(out, 2)
