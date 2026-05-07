"""Per-aspect agent-vs-gold metrics: exact, adjacent, Cohen's κ."""
import pytest

from ci.eval.vision_agreement import (
    severity_to_int,
    agreement_metrics,
)


def test_severity_to_int_orders_known_values():
    assert severity_to_int("pristine") == 0
    assert severity_to_int("light_wear") == 1
    assert severity_to_int("moderate") == 2
    assert severity_to_int("heavy") == 3
    assert severity_to_int("defect") == 4
    assert severity_to_int("not_visible") is None


def test_agreement_perfect_match():
    pairs = [("pristine", "pristine"), ("light_wear", "light_wear"),
             ("moderate", "moderate")]
    m = agreement_metrics(pairs)
    assert m["exact"] == 1.0
    assert m["adjacent"] == 1.0
    assert m["kappa"] == pytest.approx(1.0, abs=1e-6)
    assert m["n_compared"] == 3


def test_agreement_off_by_one_is_adjacent_not_exact():
    pairs = [("pristine", "light_wear"), ("light_wear", "moderate")]
    m = agreement_metrics(pairs)
    assert m["exact"] == 0.0
    assert m["adjacent"] == 1.0
    assert m["n_compared"] == 2


def test_agreement_skips_pairs_with_not_visible():
    pairs = [("pristine", "not_visible"), ("light_wear", "light_wear")]
    m = agreement_metrics(pairs)
    # Only the second pair is comparable
    assert m["n_compared"] == 1
    assert m["exact"] == 1.0


def test_agreement_kappa_is_zero_when_random():
    # Constant gold, varied agent → κ ~ 0
    pairs = [("pristine", "pristine"), ("pristine", "light_wear"),
             ("pristine", "moderate"), ("pristine", "pristine")]
    m = agreement_metrics(pairs)
    # When one rater is constant, kappa is undefined or 0; we return 0.0 by convention
    assert m["kappa"] == 0.0
