from ci.normalize import normalize, _parse_owners_spinny
from ci.schemas import RawListing


def _raw(platform, fields, lid="x"):
    return RawListing(
        platform=platform, listing_id=lid, url="snapshot://x",
        captured_at="2026-05-07T10:00:00Z", fields=fields,
    )


def test_parse_owners_spinny_ordinals():
    assert _parse_owners_spinny("1st") == 1
    assert _parse_owners_spinny("2nd") == 2
    assert _parse_owners_spinny("3rd") == 3
    assert _parse_owners_spinny("4th") == 4
    assert _parse_owners_spinny(2) == 2  # int passthrough
    assert _parse_owners_spinny(None) is None
    assert _parse_owners_spinny("???") is None
    assert _parse_owners_spinny("4th+") == 4  # leading-digit fallback


def test_normalize_cars24_basic_fields():
    raw = _raw("cars24", {
        "listingPrice": 950_000, "odometerReading": 50_673,
        "year": 2020, "ownerNumber": 2,
        "fuelType": "Petrol", "transmission": "Automatic",
        "lastServicedAt": "2026-04-28T18:00:51.040Z",
        "insuranceType": "3rd Party",
        "insuranceExpiry": "1801247400",
    })
    n = normalize(raw, today_year=2026)
    assert n.platform == "cars24"
    assert n.price == 950_000
    assert n.km_driven == 50_673
    assert n.age_years == 6
    assert n.owners == 2
    assert n.certification_flag is None
    assert n.accident_disclosed == "none"  # Cars24 platform promise


def test_normalize_cars24_disclosure_fields():
    raw = _raw("cars24", {
        "listingPrice": 900_000, "odometerReading": 40_000,
        "year": 2021, "ownerNumber": 1,
        "lastServicedAt": "2026-04-01T00:00:00Z",
        "insuranceType": "Comprehensive",
        "insuranceExpiry": "9999",
    })
    n = normalize(raw, today_year=2026)
    d = n.disclosed_fields
    assert d["service_history_records"] is True
    assert d["insurance_type"] is True
    assert d["insurance_validity"] is True
    assert d["warranty_remaining_months"] is True
    # Cars24 doesn't expose these pre-auth
    assert d["accident_history_detail"] is False
    assert d["inspection_per_section_ratings"] is False
    assert d["per_listing_certification_tier"] is False
    assert d["buy_back_pricing"] is False
    assert d["market_price_delta"] is False


def test_normalize_spinny_basic_fields():
    raw = _raw("spinny", {
        "productPrice": 1_347_000.0, "productMileage": 33_191,
        "make_year": 2022, "registration_year": 2022,
        "no_of_owners": "1st",
        "fuel_type": "petrol", "transmission": "automatic",
        "procurement_category": "assured",
        "is_assured": True,
        "inspection_report": {"report": {"summary": {"is_accidental": False}}},
    })
    n = normalize(raw, today_year=2026)
    assert n.platform == "spinny"
    assert n.price == 1_347_000
    assert n.km_driven == 33_191
    assert n.age_years == 4
    assert n.owners == 1
    assert n.certification_flag == "mid"  # "assured" → mid
    assert n.accident_disclosed == "none"


def test_normalize_spinny_assured_plus_top_tier():
    raw = _raw("spinny", {
        "productPrice": 1_500_000, "productMileage": 25_000,
        "make_year": 2023, "no_of_owners": "1st",
        "procurement_category": "assured-plus",
        "inspection_report": {"report": {"summary": {"is_accidental": False}}},
    })
    n = normalize(raw, today_year=2026)
    assert n.certification_flag == "top"


def test_normalize_spinny_accident_true_maps_to_minor():
    raw = _raw("spinny", {
        "productPrice": 800_000, "productMileage": 80_000,
        "make_year": 2018, "no_of_owners": "2nd",
        "procurement_category": "assured",
        "inspection_report": {"report": {"summary": {"is_accidental": True}}},
    })
    n = normalize(raw, today_year=2026)
    assert n.accident_disclosed == "minor"


def test_normalize_spinny_disclosure_richer_than_cars24():
    raw = _raw("spinny", {
        "productPrice": 1_000_000, "productMileage": 30_000,
        "make_year": 2022, "no_of_owners": "1st",
        "procurement_category": "assured",
        "inspection_report": {"report": {"summary": {"is_accidental": False}}},
        "inspection_report_v3": {"sections": [{}]},
        "last_service_date": "2026-04-21T08:17:28Z",
        "insurance_type": "Comprehensive",
        "insurance_validity_month": "Aug",
        "insurance_validity_year": 2026,
        "pricing": {
            "extended_warranty_pricing": {"some": 1},
            "market_price": {"price": "14,81,700"},
        },
        "buy_back_pricing": {12: {"value": 1}},
        "galleryV3": [{"url": "img1"}],
    })
    n = normalize(raw, today_year=2026)
    cnt = sum(1 for v in n.disclosed_fields.values() if v)
    # Spinny should disclose ≥10 fields with this fixture
    assert cnt >= 10


def test_normalize_falls_back_for_string_price_and_mileage():
    raw = _raw("spinny", {
        "price": "13,47,000",
        "mileage": "33,191",
        "make_year": 2022, "no_of_owners": "1st",
        "procurement_category": "assured",
        "inspection_report": {"report": {"summary": {"is_accidental": False}}},
    })
    n = normalize(raw, today_year=2026)
    assert n.price == 1_347_000
    assert n.km_driven == 33_191
