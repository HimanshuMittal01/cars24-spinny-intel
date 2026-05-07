import pytest

from ci.score import score_listings, _per_dim_scores, _rank_to_score
from ci.schemas import NormalizedListing


def _norm(lid, plat="cars24", **kw):
    base = dict(
        platform=plat, listing_id=lid, price=900_000,
        km_driven=45_000, age_years=4, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={f: False for f in []},
        full_fields={},
    )
    base.update(kw)
    return NormalizedListing(**base)


def test_rank_to_score_best_worst_middle():
    assert _rank_to_score(1, 5) == 100.0
    assert _rank_to_score(5, 5) == 0.0
    assert _rank_to_score(3, 5) == 50.0


def test_per_dim_scores_km_driven_lower_better():
    listings = [
        _norm("a", km_driven=20_000),
        _norm("b", km_driven=80_000),
        _norm("c", km_driven=50_000),
    ]
    scores = _per_dim_scores(listings, "km_driven")
    assert scores["a"] == 100.0
    assert scores["c"] == 50.0
    assert scores["b"] == 0.0


def test_per_dim_scores_owners_lower_better():
    listings = [
        _norm("a", owners=1),
        _norm("b", owners=3),
        _norm("c", owners=2),
    ]
    scores = _per_dim_scores(listings, "owners")
    assert scores["a"] == 100.0
    assert scores["c"] == 50.0
    assert scores["b"] == 0.0


def test_per_dim_scores_accident_none_better_than_minor():
    listings = [
        _norm("a", accident_disclosed="none"),
        _norm("b", accident_disclosed="minor"),
        _norm("c", accident_disclosed="major"),
    ]
    scores = _per_dim_scores(listings, "accident_disclosed")
    assert scores["a"] == 100.0
    assert scores["b"] == 50.0
    assert scores["c"] == 0.0


def test_per_dim_scores_ties_averaged():
    listings = [
        _norm("a", km_driven=20_000),
        _norm("b", km_driven=50_000),
        _norm("c", km_driven=50_000),
        _norm("d", km_driven=80_000),
    ]
    scores = _per_dim_scores(listings, "km_driven")
    assert scores["a"] == 100.0
    assert scores["b"] == scores["c"]
    # Average rank of positions (2,3) is 2.5 → score = (4-2.5)/(4-1)*100 = 50
    assert scores["b"] == pytest.approx(50.0, abs=0.01)
    assert scores["d"] == 0.0


def test_per_dim_scores_missing_gets_median_rank():
    listings = [
        _norm("a", km_driven=20_000),
        _norm("b", km_driven=None),
        _norm("c", km_driven=80_000),
    ]
    scores = _per_dim_scores(listings, "km_driven")
    assert scores["a"] == 100.0
    assert scores["c"] == 0.0
    # n=3, median rank = 2 → score = (3-2)/(3-1)*100 = 50
    assert scores["b"] == pytest.approx(50.0, abs=0.01)


def test_score_listings_winner_and_loser_get_extremes():
    listings = [
        _norm("winner", km_driven=20_000, age_years=1, owners=1, accident_disclosed="none"),
        _norm("middle", km_driven=50_000, age_years=4, owners=2, accident_disclosed="minor"),
        _norm("loser",  km_driven=120_000, age_years=10, owners=3, accident_disclosed="major"),
    ]
    by_lid = {r.listing_id: r for r in score_listings(listings)}
    assert by_lid["winner"].score_common == 100.0
    assert by_lid["loser"].score_common == 0.0


def test_score_listings_per_dim_has_only_scored_dims():
    listings = [_norm("a"), _norm("b", km_driven=80_000)]
    records = score_listings(listings)
    assert set(records[0].per_dim.keys()) == {
        "km_driven", "age_years", "owners", "accident_disclosed",
    }
    assert "certification_flag" not in records[0].per_dim


def test_score_listings_marks_imputed_dims_when_value_missing():
    listings = [
        _norm("a", km_driven=None),
        _norm("b", km_driven=50_000),
    ]
    by_lid = {r.listing_id: r for r in score_listings(listings)}
    assert "km_driven" in by_lid["a"].imputed_dims
    assert "km_driven" not in by_lid["b"].imputed_dims


def test_score_listings_disclosure_count_passthrough():
    disclosed = {"accident_history_detail": True, "service_history_records": True, "insurance_type": True}
    listings = [_norm("a", disclosed_fields=disclosed)]
    assert score_listings(listings)[0].disclosure_count == 3


def test_score_listings_returns_in_input_order():
    listings = [_norm("c"), _norm("a"), _norm("b")]
    assert [r.listing_id for r in score_listings(listings)] == ["c", "a", "b"]


def test_score_listings_certification_does_not_affect_score():
    listings = [
        _norm("a", certification_flag="top"),
        _norm("b", certification_flag=None),
    ]
    records = score_listings(listings)
    assert records[0].score_common == records[1].score_common
