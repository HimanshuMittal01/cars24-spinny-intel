import json
from pathlib import Path

from scripts.build_vision_gold_template import build_template_rows


def test_template_rows_count_matches_input():
    listings = [
        {"platform": "cars24", "listing_id": "A"},
        {"platform": "spinny", "listing_id": "B"},
        {"platform": "spinny", "listing_id": "C"},
    ]
    rows = build_template_rows(listings)
    assert len(rows) == 3


def test_template_row_has_all_5_aspects_as_null():
    listings = [{"platform": "cars24", "listing_id": "A"}]
    rows = build_template_rows(listings)
    expected_aspects = {"exterior_panels", "interior_cabin",
                        "dashboard_console", "tyres", "engine_bay"}
    assert set(rows[0]["vision_gold"].keys()) == expected_aspects
    assert all(v is None for v in rows[0]["vision_gold"].values())


def test_template_row_has_empty_notes():
    listings = [{"platform": "cars24", "listing_id": "A"}]
    rows = build_template_rows(listings)
    assert rows[0]["notes"] == {}
