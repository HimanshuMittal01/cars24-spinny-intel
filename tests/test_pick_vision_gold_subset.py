"""Smoke tests for the gold-subset selection script."""
import json
from pathlib import Path

import pytest

from scripts.pick_vision_gold_subset import pick_subset, percentile_quintile


def _fake_gold_row(platform: str, lid: str, score: float) -> dict:
    return {
        "listing_id": lid,
        "platform": platform,
        "score_common": score,
        "full_fields": {"a": 1, "b": 2, "c": 3},
    }


def test_percentile_quintile_distributes_across_0_to_4():
    values = list(range(20))  # 0..19
    quintiles = {percentile_quintile(v, values) for v in values}
    assert quintiles == {0, 1, 2, 3, 4}


def test_pick_subset_returns_5_per_platform(tmp_path: Path, monkeypatch):
    # 7 cars24 + 10 spinny synthetic gold; force EVAL_DIR/FIXTURES_DIR to tmp
    monkeypatch.setattr("scripts.pick_vision_gold_subset.EVAL_DIR", tmp_path)
    monkeypatch.setattr("scripts.pick_vision_gold_subset.FIXTURES_DIR", tmp_path / "fixtures")
    (tmp_path / "labels" / "cars24").mkdir(parents=True)
    (tmp_path / "labels" / "spinny").mkdir(parents=True)

    cars = [_fake_gold_row("cars24", f"c{i}", 10.0 * i) for i in range(7)]
    spin = [_fake_gold_row("spinny", f"s{i}", 5.0 * i) for i in range(10)]
    for r in cars + spin:
        (tmp_path / "labels" / r["platform"] / f"{r['listing_id']}.json").write_text(
            json.dumps({"full_fields": r["full_fields"]})
        )
    gold = cars + spin

    picked, dropped = pick_subset(gold)
    cars_picked = [p for p in picked if p["platform"] == "cars24"]
    spin_picked = [p for p in picked if p["platform"] == "spinny"]
    assert len(cars_picked) == 5
    assert len(spin_picked) == 5
    assert len(dropped) == 7
    # No id appears in both buckets
    picked_ids = {(p["platform"], p["listing_id"]) for p in picked}
    dropped_ids = {(d["platform"], d["listing_id"]) for d in dropped}
    assert picked_ids.isdisjoint(dropped_ids)


def test_pick_subset_spans_multiple_quintiles_per_platform(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("scripts.pick_vision_gold_subset.EVAL_DIR", tmp_path)
    monkeypatch.setattr("scripts.pick_vision_gold_subset.FIXTURES_DIR", tmp_path / "fixtures")
    (tmp_path / "labels" / "cars24").mkdir(parents=True)
    (tmp_path / "labels" / "spinny").mkdir(parents=True)
    cars = [_fake_gold_row("cars24", f"c{i}", 10.0 * i) for i in range(7)]
    spin = [_fake_gold_row("spinny", f"s{i}", 5.0 * i) for i in range(10)]
    for r in cars + spin:
        (tmp_path / "labels" / r["platform"] / f"{r['listing_id']}.json").write_text(
            json.dumps({"full_fields": r["full_fields"]})
        )
    picked, _ = pick_subset(cars + spin)
    cars_q = {p["_quintile"] for p in picked if p["platform"] == "cars24"}
    spin_q = {p["_quintile"] for p in picked if p["platform"] == "spinny"}
    # Each platform's picks span at least 3 distinct quintiles
    assert len(cars_q) >= 3
    assert len(spin_q) >= 3
