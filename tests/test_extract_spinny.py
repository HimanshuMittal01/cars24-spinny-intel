from ci.extract.spinny import extract_spinny, SPINNY_TOOL_SCHEMA
from ci.llm import FakeLLMClient
from ci.snapshot import Snapshot


def test_spinny_extractor_returns_raw_listing():
    snap = Snapshot(
        platform="spinny", listing_id="xyz",
        html="<html>...spinny detail...</html>",
        captured_at="2026-05-06T10:00:00Z",
    )
    fake = FakeLLMClient(canned_tool_input={
        "price": 1_080_000,
        "km_driven": 35_000,
        "year": 2021,
        "owners_count": 1,
        "registration_state": "HR",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "body_color": "Silver",
        "spinny_assured_tier": "Assured",
        "inspection_points_passed": "194/200",
        "inspection_issue_list": ["Right-rear bumper scratch"],
        "accident_history_detail": "minor cosmetic, rear",
    })

    raw = extract_spinny(snap, fake)
    assert raw.platform == "spinny"
    assert raw.fields["spinny_assured_tier"] == "Assured"
    assert raw.fields["inspection_issue_list"] == ["Right-rear bumper scratch"]


def test_spinny_tool_schema_has_required_keys():
    for key in ["price", "km_driven", "year", "owners_count", "spinny_assured_tier",
                "inspection_points_passed", "inspection_issue_list"]:
        assert key in SPINNY_TOOL_SCHEMA["properties"]
