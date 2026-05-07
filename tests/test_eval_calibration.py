import pytest
from ci.eval.calibration import calibration_metrics


def test_calibration_perfect():
    sys_scores = [80.0, 60.0, 90.0]
    gold_scores = [80.0, 60.0, 90.0]
    platforms = ["cars24", "cars24", "spinny"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert m.mae_overall == pytest.approx(0.0)
    assert m.spearman_overall == pytest.approx(1.0)


def test_calibration_offset():
    sys_scores = [80.0, 60.0, 90.0]
    gold_scores = [85.0, 65.0, 95.0]
    platforms = ["cars24", "spinny", "cars24"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert m.mae_overall == pytest.approx(5.0, abs=0.01)
    assert m.spearman_overall == pytest.approx(1.0)


def test_calibration_per_platform():
    sys_scores = [80.0, 60.0, 90.0, 70.0]
    gold_scores = [85.0, 60.0, 90.0, 75.0]
    platforms = ["cars24", "spinny", "cars24", "spinny"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert "cars24" in m.mae_per_platform
    assert "spinny" in m.mae_per_platform
