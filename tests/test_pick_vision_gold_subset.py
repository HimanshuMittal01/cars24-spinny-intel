"""Smoke tests for the gold-subset selection script."""
import json
from pathlib import Path

import pytest

from scripts.pick_vision_gold_subset import (
    count_photos,
    pick_subset,
    percentile_quintile,
    _owners_from_full_fields,
)


def _fake_gold_row(platform: str, lid: str, score: float, owners: int = 1) -> dict:
    """Build a synthetic gold row.

    owners is the integer count; converted to the right shape per platform:
      - cars24: {"ownerNumber": owners, ...}
      - spinny:  {"no_of_owners": "1st"/"2nd"/..., ...}
    """
    ordinals = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th+"}
    if platform == "cars24":
        ff = {"ownerNumber": owners, "a": 1, "b": 2}
    else:
        ff = {"no_of_owners": ordinals.get(owners, "1st"), "a": 1, "b": 2}
    return {
        "listing_id": lid,
        "platform": platform,
        "score_common": score,
        "full_fields": ff,
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


def test_count_photos_counts_distinct_listing_urls_per_platform(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("scripts.pick_vision_gold_subset.FIXTURES_DIR", tmp_path)

    # --- Spinny fixture ---
    spinny_dir = tmp_path / "spinny" / "spinny-001"
    spinny_dir.mkdir(parents=True)
    spinny_html = """
    <html>
    <body>
      <img src="https://spn-mda.spinny.com/img/ABC123/raw/front.jpg">
      <img src="https://spn-mda.spinny.com/img/ABC123/raw/front.jpg">
      <img src="https://spn-mda.spinny.com/img/DEF456/raw/side.jpg">
      <img src="https://spn-mda.spinny.com/img/GHI789/raw/rear.jpg">
      <img src="https://spinny.com/static/some-banner.jpg">
      <img src="https://spinny.com/static/logo.png">
    </body>
    </html>
    """
    (spinny_dir / "page.html").write_text(spinny_html)

    # --- Cars24 fixture: media.cars24.com/hello-ar/... pattern ---
    cars24_dir = tmp_path / "cars24" / "cars24-001"
    cars24_dir.mkdir(parents=True)
    cars24_html = """
    <html>
    <body>
      <img src="https://media.cars24.com/hello-ar/dev/uploads/uuid-abc/slot/1.jpg">
      <img src="https://media.cars24.com/hello-ar/dev/uploads/uuid-abc/slot/1.jpg">
      <img src="https://media.cars24.com/hello-ar/dev/transformed/uploads/uuid-abc/slot/2.jpg">
      <img src="https://assets.cars24.com/banner.jpg">
      <img src="https://assets.cars24.com/promo/header.jpg">
    </body>
    </html>
    """
    (cars24_dir / "page.html").write_text(cars24_html)

    # 3 distinct listing URLs (one duplicated) — banner from spinny.com excluded
    assert count_photos("spinny", "spinny-001") == 3
    # 2 distinct listing URLs (one duplicated) — assets.cars24.com URLs excluded
    assert count_photos("cars24", "cars24-001") == 2


def test_owners_from_full_fields_parses_both_platforms():
    """Unit test: cars24 int passthrough, spinny ordinal parsing, missing → None."""
    # cars24: direct int
    assert _owners_from_full_fields("cars24", {"ownerNumber": 1}) == 1
    assert _owners_from_full_fields("cars24", {"ownerNumber": 2}) == 2
    assert _owners_from_full_fields("cars24", {}) is None

    # spinny: ordinal strings
    assert _owners_from_full_fields("spinny", {"no_of_owners": "1st"}) == 1
    assert _owners_from_full_fields("spinny", {"no_of_owners": "2nd"}) == 2
    assert _owners_from_full_fields("spinny", {"no_of_owners": "3rd"}) == 3
    assert _owners_from_full_fields("spinny", {"no_of_owners": "4th+"}) == 4
    assert _owners_from_full_fields("spinny", {}) is None
    assert _owners_from_full_fields("spinny", {"no_of_owners": ""}) is None

    # unknown platform
    assert _owners_from_full_fields("unknown", {"ownerNumber": 1}) is None


def _setup_labels(tmp_path: Path, rows: list[dict]) -> None:
    """Write label JSON files for a list of gold rows under tmp_path/labels/."""
    for r in rows:
        label_dir = tmp_path / "labels" / r["platform"]
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / f"{r['listing_id']}.json").write_text(
            json.dumps({"full_fields": r["full_fields"]})
        )


def test_pick_subset_reserves_one_multi_owner_per_platform_when_present(
    tmp_path: Path, monkeypatch
):
    """At least 1 multi-owner row must appear in picks for each platform when gold has one."""
    monkeypatch.setattr("scripts.pick_vision_gold_subset.EVAL_DIR", tmp_path)
    monkeypatch.setattr("scripts.pick_vision_gold_subset.FIXTURES_DIR", tmp_path / "fixtures")

    # 7 cars24 rows: 5 single-owner + 2 multi-owner
    cars = [_fake_gold_row("cars24", f"c{i}", 10.0 * i) for i in range(5)]
    cars += [_fake_gold_row("cars24", f"cm{i}", 10.0 * (i + 5), owners=2) for i in range(2)]
    # 10 spinny rows: 8 single-owner + 2 multi-owner
    spin = [_fake_gold_row("spinny", f"s{i}", 5.0 * i) for i in range(8)]
    spin += [_fake_gold_row("spinny", f"sm{i}", 5.0 * (i + 8), owners=2) for i in range(2)]

    _setup_labels(tmp_path, cars + spin)

    picked, dropped = pick_subset(cars + spin)

    cars_picked = [p for p in picked if p["platform"] == "cars24"]
    spin_picked = [p for p in picked if p["platform"] == "spinny"]

    assert len(cars_picked) == 5
    assert len(spin_picked) == 5

    # Each platform's picks must include at least one multi-owner row
    assert any(p["_owners"] is not None and p["_owners"] >= 2 for p in cars_picked), (
        "No multi-owner cars24 row in picks"
    )
    assert any(p["_owners"] is not None and p["_owners"] >= 2 for p in spin_picked), (
        "No multi-owner spinny row in picks"
    )


def test_pick_subset_no_op_owners_constraint_when_no_multi_owner(
    tmp_path: Path, monkeypatch
):
    """When all gold rows are single-owner, the constraint is a no-op; still 5+5 picks."""
    monkeypatch.setattr("scripts.pick_vision_gold_subset.EVAL_DIR", tmp_path)
    monkeypatch.setattr("scripts.pick_vision_gold_subset.FIXTURES_DIR", tmp_path / "fixtures")

    # All rows have owners=1
    cars = [_fake_gold_row("cars24", f"c{i}", 10.0 * i, owners=1) for i in range(7)]
    spin = [_fake_gold_row("spinny", f"s{i}", 5.0 * i, owners=1) for i in range(10)]

    _setup_labels(tmp_path, cars + spin)

    picked, dropped = pick_subset(cars + spin)

    cars_picked = [p for p in picked if p["platform"] == "cars24"]
    spin_picked = [p for p in picked if p["platform"] == "spinny"]

    assert len(cars_picked) == 5
    assert len(spin_picked) == 5
    assert len(dropped) == 7
