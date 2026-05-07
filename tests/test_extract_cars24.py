from ci.extract.cars24 import extract_cars24, CARS24_TOOL_SCHEMA
from ci.llm import FakeLLMClient
from ci.snapshot import Snapshot


def test_cars24_extractor_returns_raw_listing():
    snap = Snapshot(
        platform="cars24", listing_id="abc",
        html="<html>...listing detail...</html>",
        captured_at="2026-05-06T10:00:00Z",
    )
    fake = FakeLLMClient(canned_tool_input={
        "price": 920_000,
        "km_driven": 42_000,
        "year": 2020,
        "owners_count": 1,
        "registration_state": "DL",
        "fuel": "Petrol",
        "transmission": "Manual",
        "body_color": "White",
        "certification_tier": "Imperial",
        "accident_disclosed": None,
        "inspection_issue_list": None,
        "service_history_records": None,
        "warranty_remaining_months": 6,
    })

    raw = extract_cars24(snap, fake)
    assert raw.platform == "cars24"
    assert raw.listing_id == "abc"
    assert raw.fields["price"] == 920_000
    assert raw.fields["certification_tier"] == "Imperial"
    assert len(fake.calls) == 1


def test_cars24_tool_schema_has_required_keys():
    assert CARS24_TOOL_SCHEMA["type"] == "object"
    for key in [
        "price", "km_driven", "year", "owners_count", "fuel", "transmission",
        "certification_tier",
    ]:
        assert key in CARS24_TOOL_SCHEMA["properties"]
