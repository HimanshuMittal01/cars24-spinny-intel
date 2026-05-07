# Plan A — Vision Gold Subset Prep + Rule Eval Rebuild

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce active gold from 17 → 10 listings, regenerate `eval/gold.jsonl` with recomputed expected scores, re-run gold-based rule evals on the new 10, and update README + tradeoffs.md + technical_appendix.md to reflect N=10. Ships a 10-gold + 6-ranking working set that is ready for Plan B (vision agent build).

**Architecture:** No pipeline modifications. Two new scripts under `scripts/` (subset selection + gold regeneration). `eval/gold.jsonl` shrinks from 17 to 10 rows; the 7 dropped listings' label files stay on disk as archive (no deletion). Existing rule eval modules unchanged in code but re-run on the new gold. Doc edits in README, tradeoffs, technical_appendix.

**Tech Stack:** Python 3.11+, pytest, scipy, pydantic. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-07-vision-agent-design.md` §12.0 and §17 step 0.

---

## Task 1: Subset selection script

**Files:**
- Create: `scripts/__init__.py` (empty, makes `scripts/` an importable package)
- Modify: `pyproject.toml` (add `.` to pythonpath so tests can import `scripts.*`)
- Create: `scripts/pick_vision_gold_subset.py`
- Create: `tests/test_pick_vision_gold_subset.py`

**Goal:** propose 10 gold listings (5 cars24 + 5 spinny) honoring quintile spread + photo-count + disclosure spread. Writes a proposal JSON the user can review and hand-edit before locking.

- [ ] **Step 0: Make `scripts/` an importable package**

Create empty `scripts/__init__.py`:

```bash
touch scripts/__init__.py
```

Edit `pyproject.toml` — find the `[tool.pytest.ini_options]` block and add `.` to `pythonpath`:

```toml
[tool.pytest.ini_options]
pythonpath = [".", "src"]
testpaths = ["tests"]
addopts = "-q"
```

Verify: `uv run python -c "import scripts; print('OK')"` should print `OK`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pick_vision_gold_subset.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pick_vision_gold_subset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.pick_vision_gold_subset'`.

- [ ] **Step 3: Write the script**

```python
# scripts/pick_vision_gold_subset.py
"""Pick 10 of the 17 gold listings (5 cars24 + 5 spinny) for the vision-agent calibration set.

Selection criteria (per docs/superpowers/specs/2026-05-07-vision-agent-design.md §12.0):
  1. Platform parity: 5 cars24 + 5 spinny.
  2. Rule-score percentile spread: prefer one pick per quintile per platform.
  3. Photo-count spread: high vs low photo coverage.
  4. Disclosure spread: high vs low full_fields count.

Outputs:
  - eval/vision_gold_subset_proposal.json  (10 picks + 7 drops + reasoning)
  - prints summary to stdout for user review
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR


def percentile_quintile(value: float, all_values: list[float]) -> int:
    """Return 0..4 quintile bucket for value within all_values."""
    sorted_vals = sorted(all_values)
    rank = sum(1 for v in sorted_vals if v <= value)
    return min(4, max(0, (rank * 5 - 1) // len(sorted_vals)))


def count_photos(platform: str, listing_id: str) -> int:
    """Count distinct listing-image URLs in the snapshot HTML.

    Uses platform-specific host filters to avoid counting CMS banners or icons.
    """
    fix = FIXTURES_DIR / platform / listing_id / "page.html"
    if not fix.exists():
        return 0
    html = fix.read_text()
    if platform == "spinny":
        urls = re.findall(r"spn-mda\.spinny\.com/img/[A-Za-z0-9%_+\-/]+", html)
    else:
        urls = re.findall(r"fastly-production\.24c\.in/india/used-cars/[A-Za-z0-9%_+\-/.]+", html)
    return len(set(urls))


def disclosure_count(platform: str, listing_id: str) -> int:
    """Use the existing label file's full_fields key count as a disclosure proxy."""
    label_path = EVAL_DIR / "labels" / platform / f"{listing_id}.json"
    if not label_path.exists():
        return 0
    fields = json.loads(label_path.read_text()).get("full_fields", {})
    return len(fields)


def load_gold() -> list[dict]:
    return [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]


def pick_subset(gold: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pick 5 cars24 + 5 spinny preserving diversity. Returns (picked, dropped)."""
    target_per_platform = 5
    picked: list[dict] = []
    dropped: list[dict] = []

    for platform in ("cars24", "spinny"):
        rows = [r for r in gold if r["platform"] == platform]
        scores = [r["score_common"] for r in rows]
        annotated = []
        for r in rows:
            annotated.append({
                **r,
                "_quintile": percentile_quintile(r["score_common"], scores),
                "_photos": count_photos(platform, r["listing_id"]),
                "_disclosure": disclosure_count(platform, r["listing_id"]),
            })

        # Stratified pick: one per quintile (max diversity), then fill with leftover diversity.
        chosen: list[dict] = []
        seen_ids: set[str] = set()
        # Pass 1: best-of-each-quintile by (photos, disclosure)
        for q in sorted({r["_quintile"] for r in annotated}):
            cands = [r for r in annotated if r["_quintile"] == q]
            cand = max(cands, key=lambda r: (r["_photos"], r["_disclosure"]))
            chosen.append(cand)
            seen_ids.add(cand["listing_id"])

        # Pass 2: fill to target with remaining (highest photo+disclosure first)
        remaining = [r for r in annotated if r["listing_id"] not in seen_ids]
        remaining.sort(key=lambda r: (r["_photos"] + r["_disclosure"]), reverse=True)
        while len(chosen) < target_per_platform and remaining:
            extra = remaining.pop(0)
            chosen.append(extra)
            seen_ids.add(extra["listing_id"])

        chosen = chosen[:target_per_platform]
        chosen_ids = {c["listing_id"] for c in chosen}

        for r in annotated:
            if r["listing_id"] in chosen_ids:
                picked.append(r)
            else:
                dropped.append(r)

    return picked, dropped


def main() -> None:
    gold = load_gold()
    picked, dropped = pick_subset(gold)

    print(f"Picked {len(picked)} listings:")
    for p in picked:
        print(
            f"  [{p['platform']:7}] {p['listing_id']:14} "
            f"score={p['score_common']:5.2f} q={p['_quintile']} "
            f"photos={p['_photos']:3} disclosure={p['_disclosure']}"
        )
    print(f"\nDropped {len(dropped)} listings:")
    for d in dropped:
        print(
            f"  [{d['platform']:7}] {d['listing_id']:14} "
            f"score={d['score_common']:5.2f} q={d['_quintile']} "
            f"photos={d['_photos']:3} disclosure={d['_disclosure']}"
        )

    out = {
        "picked": [
            {"platform": p["platform"], "listing_id": p["listing_id"]} for p in picked
        ],
        "dropped": [
            {"platform": d["platform"], "listing_id": d["listing_id"]} for d in dropped
        ],
        "reasoning": {
            "criteria": "platform parity 5+5; quintile spread within platform; "
                        "photo+disclosure diversity",
            "spec_ref": "docs/superpowers/specs/2026-05-07-vision-agent-design.md §12.0",
        },
    }
    out_path = EVAL_DIR / "vision_gold_subset_proposal.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote proposal to {out_path}")
    print("Review the proposal, edit by hand if needed, then proceed to Task 2 lock step.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pick_vision_gold_subset.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/pick_vision_gold_subset.py tests/test_pick_vision_gold_subset.py pyproject.toml
git commit -m "feat(scripts): add gold-subset selection script for vision-agent calibration set"
```

---

## Task 2: Run subset selection + user lock

**Files:**
- Modify: `eval/vision_gold_subset_proposal.json` (created by script, possibly hand-edited)

**Goal:** Run the script, present picks to the user, accept hand-edits, lock the final 10.

- [ ] **Step 1: Run the picker**

Run: `uv run python -m scripts.pick_vision_gold_subset`
Expected: prints 10 picks + 7 drops to stdout; writes `eval/vision_gold_subset_proposal.json`.

- [ ] **Step 2: Present picks to user**

Read and show the contents of `eval/vision_gold_subset_proposal.json` to the user, plus the stdout summary table from Step 1. Ask:

> "These are the 10 picked + 7 dropped. Edit `eval/vision_gold_subset_proposal.json` if you want to swap any. Reply 'lock' to proceed."

- [ ] **Step 3: Wait for user lock**

If user requests swaps, manually edit `eval/vision_gold_subset_proposal.json` (the `picked` and `dropped` arrays) per their instructions. Then re-confirm.

- [ ] **Step 4: Verify proposal integrity**

Run:
```bash
uv run python -c "
import json
from pathlib import Path
p = json.loads(Path('eval/vision_gold_subset_proposal.json').read_text())
ids_p = {(r['platform'], r['listing_id']) for r in p['picked']}
ids_d = {(r['platform'], r['listing_id']) for r in p['dropped']}
assert len(p['picked']) == 10, f'picked must be 10, got {len(p[\"picked\"])}'
assert len(p['dropped']) == 7, f'dropped must be 7, got {len(p[\"dropped\"])}'
assert ids_p.isdisjoint(ids_d), 'picked and dropped overlap'
cars = sum(1 for r in p['picked'] if r['platform'] == 'cars24')
spin = sum(1 for r in p['picked'] if r['platform'] == 'spinny')
assert cars == 5 and spin == 5, f'platform parity broken: {cars}+{spin}'
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 5: Commit the locked proposal**

```bash
git add eval/vision_gold_subset_proposal.json
git commit -m "chore(eval): lock 10-listing vision-gold subset proposal (5 cars24 + 5 spinny)"
```

---

## Task 3: Regenerate eval/gold.jsonl with recomputed expected scores

**Files:**
- Create: `scripts/regenerate_gold.py`
- Modify: `eval/gold.jsonl` (rebuilt from 17 to 10 rows; old version preserved in git history)
- Create: `tests/test_regenerate_gold.py`

**Goal:** The 10 gold rows' `score_common` and `per_feature_rank_scores` were computed against the 17-listing rank set (per spec §14). With the rank set changing to 10, those expected values must be recomputed via the existing scorer over the new 10-set. `full_fields` and `notes` are preserved verbatim from the old gold.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_regenerate_gold.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regenerate_gold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.regenerate_gold'`.

- [ ] **Step 3: Write the script**

```python
# scripts/regenerate_gold.py
"""Regenerate eval/gold.jsonl with the 10 picked listings + recomputed expected scores.

The score_common and per_feature_rank_scores in gold.jsonl are RANK-BASED over the
gold set (spec §14). When the gold set changes from 17→10, those ranks change, so
expected values must be recomputed via the existing scorer over the new 10-set.

Inputs:
  - eval/vision_gold_subset_proposal.json  (the locked 10-listing pick)
  - eval/gold.jsonl                         (existing 17 rows, used as source of full_fields/notes)
  - fixtures/<platform>/<listing_id>/page.html  (for re-extraction + normalization)

Output:
  - eval/gold.jsonl                         (rewritten with 10 rows + recomputed expected)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ci.config import EVAL_DIR
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.score import score_listings
from ci.snapshot import load_snapshot


def load_existing_gold() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[(row["platform"], row["listing_id"])] = row
    return out


def build_new_gold_rows(
    picked: list[dict],
    existing: dict[tuple[str, str], dict],
    *,
    today_year: int,
) -> list[dict]:
    """Re-extract → normalize → score the picked listings; rebuild gold rows.

    Preserves `full_fields` and `notes` from `existing`; recomputes
    `score_common` and `per_feature_rank_scores` from the new set's ranks.
    """
    norms = []
    for entry in picked:
        platform, lid = entry["platform"], entry["listing_id"]
        snap = load_snapshot(platform, lid)
        raw = extract_cars24(snap) if platform == "cars24" else extract_spinny(snap)
        norms.append(normalize(raw, today_year=today_year))

    scored = score_listings(norms)

    rows: list[dict] = []
    for s, n in zip(scored, norms):
        old = existing.get((n.platform, n.listing_id))
        if old is None:
            raise KeyError(
                f"picked listing {n.platform}/{n.listing_id} not in existing gold"
            )
        rows.append({
            "listing_id": n.listing_id,
            "platform": n.platform,
            "full_fields": old["full_fields"],
            "score_common": s.score_common,
            "notes": old.get("notes", {}),
            "per_feature_rank_scores": s.per_dim,
        })
    return rows


def main() -> None:
    proposal = json.loads(
        (EVAL_DIR / "vision_gold_subset_proposal.json").read_text()
    )
    picked = proposal["picked"]
    if len(picked) != 10:
        raise ValueError(f"proposal must have 10 picked, got {len(picked)}")

    existing = load_existing_gold()
    today_year = datetime.now(timezone.utc).year
    rows = build_new_gold_rows(picked, existing, today_year=today_year)

    out = EVAL_DIR / "gold.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_regenerate_gold.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the script against the locked proposal**

Run: `uv run python -m scripts.regenerate_gold`
Expected: prints `Wrote 10 rows to .../eval/gold.jsonl`.

Verify:
```bash
wc -l eval/gold.jsonl
```
Expected: `10 eval/gold.jsonl`.

- [ ] **Step 6: Commit**

```bash
git add scripts/regenerate_gold.py tests/test_regenerate_gold.py eval/gold.jsonl
git commit -m "feat(eval): regenerate gold.jsonl with 10-listing subset and recomputed rank scores"
```

---

## Task 4: Re-run rule evals on new 10-gold and capture metrics

**Files:**
- Create: `scripts/run_rule_evals.py`
- Create: `runs/rule_eval_<timestamp>/eval_summary.json` (output)

**Goal:** Run the existing rule eval suite (extraction recall, calibration, weight sensitivity) against the new 10-gold and capture the numbers. The numbers feed Tasks 5-7 doc updates.

- [ ] **Step 1: Write the eval driver script**

```python
# scripts/run_rule_evals.py
"""Run extraction + calibration + sensitivity evals against the current eval/gold.jsonl.

Writes a single JSON summary under runs/rule_eval_<timestamp>/eval_summary.json
that the doc-update tasks (Plan A Tasks 5-7) consume.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from ci.config import EVAL_DIR, RUNS_DIR
from ci.eval.calibration import calibration_metrics
from ci.eval.extraction import _approx_equal, CHECKED_FIELDS, TOLERANCE
from ci.eval.sensitivity import weight_sensitivity
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.normalize import normalize
from ci.schemas import GoldRecord
from ci.score import score_listings
from ci.snapshot import load_snapshot


def load_gold_records() -> list[GoldRecord]:
    out: list[GoldRecord] = []
    for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(GoldRecord(
            listing_id=d["listing_id"],
            platform=d["platform"],
            full_fields=d["full_fields"],
            score_common=d["score_common"],
            notes=d.get("notes", {}),
        ))
    return out


def _extract_recall(gold: list[GoldRecord], today_year: int) -> dict:
    """Field-level recall: extracted normalized values vs gold normalized values."""
    matches = {f: 0 for f in CHECKED_FIELDS}
    matches_per_platform: dict[str, dict[str, int]] = {}
    n_per_platform: dict[str, int] = {}
    for g in gold:
        snap = load_snapshot(g.platform, g.listing_id)
        raw = extract_cars24(snap) if g.platform == "cars24" else extract_spinny(snap)
        norm = normalize(raw, today_year=today_year)

        # Build a "gold normalized" by running the normalizer over the gold full_fields.
        from ci.schemas import RawListing
        gold_raw = RawListing(
            platform=g.platform, listing_id=g.listing_id,
            url="gold://", captured_at="gold", fields=g.full_fields,
        )
        gold_norm = normalize(gold_raw, today_year=today_year)

        per_p = matches_per_platform.setdefault(g.platform, {f: 0 for f in CHECKED_FIELDS})
        n_per_platform[g.platform] = n_per_platform.get(g.platform, 0) + 1
        for f in CHECKED_FIELDS:
            if _approx_equal(getattr(norm, f), getattr(gold_norm, f), TOLERANCE[f]):
                matches[f] += 1
                per_p[f] += 1

    n = len(gold)
    return {
        "n": n,
        "field_recall": {f: matches[f] / n for f in CHECKED_FIELDS},
        "field_recall_per_platform": {
            p: {f: matches_per_platform[p][f] / n_per_platform[p] for f in CHECKED_FIELDS}
            for p in matches_per_platform
        },
    }


def _calibration(gold: list[GoldRecord], today_year: int) -> dict:
    norms = []
    for g in gold:
        from ci.schemas import RawListing
        norms.append(normalize(
            RawListing(
                platform=g.platform, listing_id=g.listing_id,
                url="gold://", captured_at="gold", fields=g.full_fields,
            ),
            today_year=today_year,
        ))
    scored = score_listings(norms)
    sys = [s.score_common for s in scored]
    gld = [g.score_common for g in gold]
    plats = [g.platform for g in gold]
    m = calibration_metrics(sys, gld, plats)
    return {
        "n": m.n,
        "mae_overall": m.mae_overall,
        "spearman_overall": m.spearman_overall,
        "mae_per_platform": m.mae_per_platform,
        "spearman_per_platform": m.spearman_per_platform,
    }


def _sensitivity(gold: list[GoldRecord], today_year: int) -> dict:
    from ci.schemas import RawListing
    norms = []
    for g in gold:
        norms.append(normalize(
            RawListing(
                platform=g.platform, listing_id=g.listing_id,
                url="gold://", captured_at="gold", fields=g.full_fields,
            ),
            today_year=today_year,
        ))
    s = weight_sensitivity(norms)
    return {
        "tau_perturbed": s.tau_perturbed,
        "tau_leave_one_out": s.tau_leave_one_out,
    }


def main() -> None:
    today_year = datetime.now(timezone.utc).year
    gold = load_gold_records()
    print(f"Loaded {len(gold)} gold records")

    summary = {
        "extraction": _extract_recall(gold, today_year),
        "calibration": _calibration(gold, today_year),
        "sensitivity": _sensitivity(gold, today_year),
        "n_gold": len(gold),
        "today_year": today_year,
    }

    run_id = (
        "rule_eval_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:6]
    )
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "eval_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script imports cleanly**

Run: `uv run python -c "import scripts.run_rule_evals"`
Expected: no error.

`_approx_equal`, `CHECKED_FIELDS`, and `TOLERANCE` are module-level in `src/ci/eval/extraction.py`, so the import works. If a future refactor makes them private, copy the three definitions inline rather than reaching into private symbols.

- [ ] **Step 3: Run the eval driver**

Run: `uv run python -m scripts.run_rule_evals`
Expected: prints loaded count (10), writes `runs/rule_eval_<ts>/eval_summary.json`, prints summary JSON.

- [ ] **Step 4: Sanity-check the metrics are well-formed**

Run:
```bash
uv run python -c "
import json, glob
latest = sorted(glob.glob('runs/rule_eval_*/eval_summary.json'))[-1]
s = json.loads(open(latest).read())
assert s['n_gold'] == 10
assert 0 <= s['calibration']['spearman_overall'] <= 1.0001
assert all(0 <= v <= 1.0 for v in s['extraction']['field_recall'].values())
print('OK', latest)
"
```
Expected: prints `OK <path>`.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_rule_evals.py
git commit -m "feat(scripts): rule-eval driver capturing extraction+calibration+sensitivity into JSON"
```

(The `runs/rule_eval_*/` outputs are generated; commit only if `runs/` is tracked. Check `.gitignore` first.)

---

## Task 5: Update README — "How we know the ranking holds up" section

**Files:**
- Modify: `README.md`

**Goal:** README's gold-based metrics currently reflect N=17. Update with the N=10 metrics from Task 4's `eval_summary.json`. Preserve the README's prose voice; only swap numbers and the `N=` mentions. Add a one-line note that gold was reduced to 10 to support the vision-agent calibration.

- [ ] **Step 1: Read the latest eval summary**

Run:
```bash
ls -t runs/rule_eval_*/eval_summary.json | head -1 | xargs cat
```
Note down: `n_gold`, `calibration.spearman_overall`, `calibration.mae_overall`, `extraction.field_recall` per field.

- [ ] **Step 2: Locate gold-metric references in the README**

Run:
```bash
grep -nE 'gold|N ?= ?17|17 gold|Spearman|MAE|recall' README.md
```
Note line numbers for each match.

- [ ] **Step 3: Edit README**

For each match from Step 2 that references a gold-derived number:
- Replace `17` with `10` in any "gold set of 17" phrasing.
- Replace numeric values (Spearman, MAE, recall) with the new ones from Step 1.

Add a one-paragraph note (insert near the gold section's intro) explaining the reduction:

> The gold set was reduced from 17 to 10 listings to support the vision-agent calibration (see [vision-agent design](docs/superpowers/specs/2026-05-07-vision-agent-design.md) §12.0). The 7 dropped listings remain on disk as archive but no longer feed `eval/gold.jsonl`. Statistical caveat at N=10: Cohen's κ is noisy; adjacent agreement is the more stable companion statistic where used.

- [ ] **Step 4: Verify markdown renders cleanly**

Run:
```bash
uv run python -c "
import re
md = open('README.md').read()
# No leftover '17 gold' or 'N=17' phrasings
assert '17 gold' not in md, '17 gold still in README'
assert 'N=17' not in md and 'N = 17' not in md, 'N=17 still in README'
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs(README): rebuild gold-based metrics on the 10-listing subset"
```

---

## Task 6: Update technical_appendix.md — stability/dominance section

**Files:**
- Modify: `docs/technical_appendix.md`

**Goal:** The recent commit `a231d2a` added a stability/dominance check on the 17 gold concluding "owners is meaningfully influential." Re-validate this on N=10. The conclusion may or may not survive — accept whichever the data shows.

- [ ] **Step 1: Pull the new sensitivity numbers**

Run:
```bash
ls -t runs/rule_eval_*/eval_summary.json | head -1 | xargs cat | python -c "
import json, sys
s = json.loads(sys.stdin.read())
print('tau_perturbed:', s['sensitivity']['tau_perturbed'])
print('tau_leave_one_out:', s['sensitivity']['tau_leave_one_out'])
"
```

- [ ] **Step 2: Locate the stability/dominance section**

Run:
```bash
grep -nE 'stability|dominance|owners.*influential|leave.one.out|Kendall|tau' docs/technical_appendix.md
```

- [ ] **Step 3: Edit the appendix**

Replace the table or prose values with the new tau_perturbed and tau_leave_one_out numbers from Step 1. Keep the existing structure.

Re-evaluate the "owners is meaningfully influential" conclusion:
- If `tau_leave_one_out["owners"]` is the lowest of the four dims AND meaningfully below 1.0 (e.g., < 0.7), the conclusion stands.
- If it ties with another dim or is closer to 1.0, replace the prose with what the new data shows. Be honest — write what the numbers say even if it changes the story.

Add the same N=10 caveat sentence used in README near the section start:

> Re-run on N=10 (down from N=17) following the gold-set reduction for vision-agent calibration. Results below reflect the smaller set; statistical power is reduced.

- [ ] **Step 4: Verify**

Run:
```bash
grep -E 'N ?= ?17|17 gold' docs/technical_appendix.md
```
Expected: no output (or only matches in clearly historical context).

- [ ] **Step 5: Commit**

```bash
git add docs/technical_appendix.md
git commit -m "docs(appendix): rerun stability/dominance check on N=10 gold subset"
```

---

## Task 7: Update tradeoffs.md — N reference if any

**Files:**
- Modify (conditional): `docs/tradeoffs.md`

**Goal:** Sweep tradeoffs.md for any `17 gold` / `N=17` references and update them. If none exist, this task is a no-op.

- [ ] **Step 1: Sweep for references**

Run:
```bash
grep -nE '17 gold|N ?= ?17|17[- ]listing' docs/tradeoffs.md || echo "no matches"
```

- [ ] **Step 2: If matches present, edit them**

For each match: replace `17` with `10` if the sentence is about the current gold set; preserve as-is if it's clearly historical.

- [ ] **Step 3: Verify**

```bash
grep -E 'N ?= ?17|17 gold' docs/tradeoffs.md && echo "still has N=17 refs" || echo "OK"
```
Expected: `OK`.

- [ ] **Step 4: Commit (only if Step 2 made changes)**

```bash
git add docs/tradeoffs.md
git commit -m "docs(tradeoffs): align gold-set N with the 10-listing subset"
```

If no changes were needed, skip the commit.

---

## Task 8: Final verification

**Goal:** Confirm Plan A's invariants hold end-to-end before declaring it done.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (no regressions from the existing pre-Plan-A suite + the two new test files).

- [ ] **Step 2: Verify gold integrity**

```bash
uv run python -c "
import json
from pathlib import Path
rows = [json.loads(l) for l in Path('eval/gold.jsonl').read_text().splitlines() if l.strip()]
assert len(rows) == 10, f'gold should have 10 rows, has {len(rows)}'
plats = [r['platform'] for r in rows]
assert plats.count('cars24') == 5 and plats.count('spinny') == 5, plats
for r in rows:
    assert 0 <= r['score_common'] <= 100
    assert set(r['per_feature_rank_scores'].keys()) == {'km_driven','age_years','owners','accident_disclosed'}
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 3: Check label files for the dropped 7 are still on disk**

```bash
uv run python -c "
import json
from pathlib import Path
proposal = json.loads(Path('eval/vision_gold_subset_proposal.json').read_text())
for d in proposal['dropped']:
    p = Path(f'eval/labels/{d[\"platform\"]}/{d[\"listing_id\"]}.json')
    assert p.exists(), f'archive label missing: {p}'
print('OK')
"
```
Expected: prints `OK`. Confirms the dropped 7's labels remain as archive (not deleted).

- [ ] **Step 4: Verify README + appendix render and contain the N=10 caveat**

```bash
grep -c 'N=10\|10-listing\|10 listings\|reduced.*to 10' README.md docs/technical_appendix.md
```
Expected: at least 1 match in each file.

- [ ] **Step 5: Tag the milestone**

```bash
git tag -a plan-a-complete -m "Plan A complete: 10-listing gold subset + rule-eval rebuild"
```

---

## Plan A complete. Plan B begins next.

After Plan A is locked, invoke `writing-plans` again to author Plan B (vision-agent core: photos + schemas + inspector + outer agent + scoring + pipeline integration). Plan B will reference the locked 10-listing IDs from `eval/vision_gold_subset_proposal.json` directly — no placeholders.
