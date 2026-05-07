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


def test_rank_sorts_by_ratio_ascending():
    pairs = [
        _pair("a", "cars24", 1_200_000, 60),  # ratio 20000
        _pair("b", "spinny", 900_000, 90),    # ratio 10000
        _pair("c", "cars24", 1_000_000, 80),  # ratio 12500
    ]
    rows = rank_listings(pairs)
    assert [r.listing_id for r in rows] == ["b", "c", "a"]
    assert rows[0].ratio == 10_000.0
    assert rows[1].ratio == 12_500.0


def test_rank_carries_metadata():
    pairs = [_pair("a", "spinny", 1_000_000, 50, disclosure=7, imputed=["age_years"])]
    rows = rank_listings(pairs)
    assert rows[0].disclosure_count == 7
    assert rows[0].imputed_dims == ["age_years"]
