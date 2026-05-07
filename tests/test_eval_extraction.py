from ci.eval.extraction import extraction_metrics
from ci.schemas import GoldRecord, NormalizedListing


def _norm(lid, plat="cars24", **kw):
    base = dict(
        platform=plat, listing_id=lid, price=900_000,
        km_driven=45_000, age_years=4, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={}, full_fields={},
    )
    base.update(kw)
    return NormalizedListing(**base)


def _gold(lid, plat, full_fields, score=80.0):
    return GoldRecord(
        listing_id=lid, platform=plat,
        full_fields=full_fields,
        score_common=score, notes={},
    )


def test_perfect_recall_cars24():
    norm = _norm("a", "cars24", price=900_000, km_driven=45_000, age_years=4, owners=2)
    gold = _gold("a", "cars24", full_fields={
        "listingPrice": 900_000, "odometerReading": 45_000,
        "year": 2022, "ownerNumber": 2,
    })
    m = extraction_metrics([(norm, gold)], today_year=2026)
    assert m.field_recall["price"] == 1.0
    assert m.field_recall["km_driven"] == 1.0
    assert m.field_recall["age_years"] == 1.0
    assert m.field_recall["owners"] == 1.0
    assert m.n == 1


def test_perfect_recall_spinny():
    norm = _norm("b", "spinny", price=1_200_000, km_driven=30_000, age_years=4, owners=1)
    gold = _gold("b", "spinny", full_fields={
        "productPrice": 1_200_000, "productMileage": 30_000,
        "make_year": 2022, "no_of_owners": "1st",
        "procurement_category": "assured",
        "inspection_report": {"report": {"summary": {"is_accidental": False}}},
    })
    m = extraction_metrics([(norm, gold)], today_year=2026)
    assert m.field_recall["price"] == 1.0
    assert m.field_recall["km_driven"] == 1.0


def test_recall_drop_when_extractor_disagrees():
    # System extracted km_driven=50000 but gold says 45000 — recall should be 0 for km
    norm = _norm("a", "cars24", price=900_000, km_driven=50_000, age_years=4, owners=2)
    gold = _gold("a", "cars24", full_fields={
        "listingPrice": 900_000, "odometerReading": 45_000,
        "year": 2022, "ownerNumber": 2,
    })
    m = extraction_metrics([(norm, gold)], today_year=2026)
    assert m.field_recall["km_driven"] == 0.0
    assert m.field_recall["price"] == 1.0


def test_per_platform_breakdown():
    pairs = [
        (_norm("a", "cars24", price=900_000, km_driven=45_000),
         _gold("a", "cars24", full_fields={"listingPrice": 900_000, "odometerReading": 45_000, "year": 2022, "ownerNumber": 1})),
        (_norm("b", "spinny", price=1_200_000, km_driven=30_000),
         _gold("b", "spinny", full_fields={
             "productPrice": 1_200_000, "productMileage": 30_000,
             "make_year": 2022, "no_of_owners": "1st",
             "procurement_category": "assured",
             "inspection_report": {"report": {"summary": {"is_accidental": False}}},
         })),
    ]
    m = extraction_metrics(pairs, today_year=2026)
    assert m.n == 2
    # Per-platform key should exist
    assert "cars24" in m.field_recall_per_platform
    assert "spinny" in m.field_recall_per_platform
