from ci.rank import rank_listings
from ci.schemas import NormalizedListing, ScoreRecord


def _pair(lid, plat, price, score, disclosure=0, imputed=None):
    n = NormalizedListing(
        platform=plat, listing_id=lid, price=price,
        km_driven=50_000, age_years=4, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={}, full_fields={},
    )
    s = ScoreRecord(
        listing_id=lid, platform=plat, score_common=score,
        per_dim={}, imputed_dims=imputed or [],
        disclosure_count=disclosure, disclosed_fields={},
    )
    return n, s


def test_rank_sorts_by_score_descending():
    pairs = [
        _pair("a", "cars24", 1_200_000, 60),  # rule_score 60 → rank 3rd
        _pair("b", "spinny", 900_000, 90),    # rule_score 90 → rank 1st
        _pair("c", "cars24", 1_000_000, 80),  # rule_score 80 → rank 2nd
    ]
    rows = rank_listings(pairs)
    assert [r.listing_id for r in rows] == ["b", "c", "a"]
    assert rows[0].rule_score == 90.0
    assert rows[1].rule_score == 80.0


def test_rank_carries_metadata():
    pairs = [_pair("a", "spinny", 1_000_000, 50, disclosure=7, imputed=["age_years"])]
    rows = rank_listings(pairs)
    assert rows[0].disclosure_count == 7
    assert rows[0].imputed_dims == ["age_years"]


def test_rank_with_vision_scores_uses_composite():
    from ci.schemas import (
        NormalizedListing, ScoreRecord, VisionScore,
        VisionAssessment, VisionFinding,
    )
    from ci.rank import rank_listings

    n1 = NormalizedListing(
        platform="cars24", listing_id="L1", price=500000,
        km_driven=50000, age_years=3, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={}, full_fields={},
    )
    sc1 = ScoreRecord(
        listing_id="L1", platform="cars24", score_common=80.0,
        per_dim={}, imputed_dims=[], disclosure_count=0, disclosed_fields={},
    )
    vs1 = VisionScore(
        listing_id="L1", platform="cars24",
        visual_score=60.0, per_aspect_score={
            "exterior_panels": 60.0, "interior_cabin": 60.0,
            "dashboard_console": 60.0, "tyres": 60.0, "engine_bay": 60.0,
        }, imputed_aspects=[],
        assessment=VisionAssessment(
            listing_id="L1", platform="cars24", findings=[
                VisionFinding(aspect=a, severity="moderate", confidence="med",
                              photo_refs=[], evidence_note="")
                for a in ("exterior_panels", "interior_cabin",
                          "dashboard_console", "tyres", "engine_bay")
            ],
            photos_inspected=[], photo_count_total=5, agent_turns=2,
        ),
    )
    rows = rank_listings([(n1, sc1)], vision_scores={"L1": vs1})
    assert rows[0].composite_score == 74.0  # 0.7*80 + 0.3*60
    assert rows[0].ratio == round(500000 / 74.0, 2)
