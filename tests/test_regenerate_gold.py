"""Smoke tests for gold.jsonl regeneration."""
import json
from pathlib import Path

import pytest

from scripts.regenerate_gold import build_new_gold_rows


def _fake_existing_gold() -> dict:
    """Two-listing fake gold, keyed by (platform, listing_id)."""
    return {
        ("cars24", "10006504768"): {
            "listing_id": "10006504768",
            "platform": "cars24",
            "full_fields": {
                "listingPrice": 484000,
                "odometerReading": 69401,
                "year": 2016,
                "ownerNumber": 1,
            },
            "score_common": 36.25,
            "notes": {"km_driven": "69,401 km"},
            "per_feature_rank_scores": {"km_driven": 37.5},
        },
        ("cars24", "10017390119"): {
            "listing_id": "10017390119",
            "platform": "cars24",
            "full_fields": {
                "listingPrice": 849000,
                "odometerReading": 124656,
                "year": 2020,
                "ownerNumber": 1,
            },
            "score_common": 35.62,
            "notes": {},
            "per_feature_rank_scores": {"km_driven": 0.0},
        },
    }


def test_build_new_gold_rows_preserves_full_fields_and_notes():
    existing = _fake_existing_gold()
    picked = [
        {"platform": "cars24", "listing_id": "10006504768"},
        {"platform": "cars24", "listing_id": "10017390119"},
    ]
    rows = build_new_gold_rows(picked, existing, today_year=2026)

    assert len(rows) == 2
    by_id = {r["listing_id"]: r for r in rows}
    assert by_id["10006504768"]["full_fields"] == existing[("cars24", "10006504768")]["full_fields"]
    assert by_id["10006504768"]["notes"] == {"km_driven": "69,401 km"}


def test_build_new_gold_rows_recomputes_score_in_0_to_100():
    existing = _fake_existing_gold()
    picked = [
        {"platform": "cars24", "listing_id": "10006504768"},
        {"platform": "cars24", "listing_id": "10017390119"},
    ]
    rows = build_new_gold_rows(picked, existing, today_year=2026)
    for r in rows:
        assert 0.0 <= r["score_common"] <= 100.0
        assert isinstance(r["per_feature_rank_scores"], dict)
        assert set(r["per_feature_rank_scores"].keys()) == {
            "km_driven", "age_years", "owners", "accident_disclosed",
        }


def test_build_new_gold_rows_set_relative_changes_with_new_set():
    """A 2-listing set produces different scores than the original 17-set baseline."""
    existing = _fake_existing_gold()
    picked = [
        {"platform": "cars24", "listing_id": "10006504768"},
        {"platform": "cars24", "listing_id": "10017390119"},
    ]
    rows = build_new_gold_rows(picked, existing, today_year=2026)
    # Old gold had 36.25 / 35.62 on a 17-set; on a 2-set the rank gap collapses to 0/100
    by_id = {r["listing_id"]: r for r in rows}
    assert by_id["10006504768"]["score_common"] != 36.25
    assert by_id["10017390119"]["score_common"] != 35.62
