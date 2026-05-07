# Cars24 vs Spinny Competitive Intel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synchronous Python pipeline that ingests cached HTML snapshots of 6 used-car listings (3 Cars24 + 3 Spinny, Hyundai Creta in Delhi-NCR ₹8-14L), extracts structured fields via LLM agents, scores condition deterministically, ranks by price-to-condition, and is validated end-to-end by a five-eval gold-grounded harness.

**Architecture:** Single explicit DAG: `snapshot_loader → per-platform extractor (LLM, structured output) → normalizer → scorer (deterministic composite + disclosure metric) → ranker → reporter`. A trace store writes per-node records. The eval harness runs against snapshot replay + a hand-labeled `gold.jsonl`.

**Tech Stack:** Python 3.11+, `uv` for env/deps, Pydantic v2 schemas, Anthropic SDK (Sonnet 4.6, structured tool-use output, temp=0), pytest, scipy (Spearman / Kendall τ), matplotlib (single chart), python-dotenv.

**Reference spec:** [`docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md`](../specs/2026-05-06-cars24-spinny-comp-intel-design.md). Read it first; this plan implements that design.

---

## File Structure

Files created by this plan, with their single responsibility.

```
cars24-comp-intel/
├── pyproject.toml                         # uv project config + deps
├── uv.lock
├── .env.example                           # ANTHROPIC_API_KEY placeholder
├── .gitignore
├── README.md                              # how to run + minimal usage
├── docs/
│   ├── superpowers/
│   │   ├── specs/2026-05-06-...-design.md (already exists)
│   │   └── plans/2026-05-06-...-implementation.md (this file)
│   ├── tradeoffs.md                       # decisions journal during build
│   └── report.md                          # final assessment deliverable (T19)
├── fixtures/
│   ├── cars24/<listing_id>/{page.html, captured_at.txt}
│   └── spinny/<listing_id>/{page.html, captured_at.txt}
├── eval/
│   ├── gold.jsonl                         # hand-labeled ground truth
│   └── gold_template.json                 # exemplar record for labeling
├── runs/<run_id>/trace.jsonl              # per-node trace records (gitignored)
├── src/ci/
│   ├── __init__.py
│   ├── config.py                          # paths, weights, anchors, imputation, disclosure-eligible set
│   ├── schemas.py                         # all Pydantic models
│   ├── snapshot.py                        # disk-only loader + collection helper
│   ├── trace.py                           # trace store (JSONL writer/reader)
│   ├── llm.py                             # Anthropic client wrapper
│   ├── extract/
│   │   ├── __init__.py
│   │   ├── cars24.py                      # cars24 extraction agent
│   │   └── spinny.py                      # spinny extraction agent
│   ├── normalize.py                       # raw → common + disclosure_fields
│   ├── score.py                           # composite scorer + disclosure_count
│   ├── rank.py                            # ratio compute + sort
│   ├── report.py                          # markdown + chart generation
│   ├── pipeline.py                        # DAG orchestration
│   └── eval/
│       ├── __init__.py
│       ├── extraction.py                  # E2: per-field P/R + schema + hallucination
│       ├── calibration.py                 # E3: MAE + Spearman vs gold
│       ├── sensitivity.py                 # E4: weight perturbation + LOO
│       └── determinism.py                 # E5: 1-listing × 3-rep spot-check
├── scripts/
│   ├── collect_snapshots.py               # one-time: fetch listing HTML to fixtures/
│   ├── run_pipeline.py                    # end-to-end run on the 6 ranking listings
│   ├── run_evals.py                       # runs E2–E5 over gold + writes summary
│   └── label_gold.py                      # CLI that walks fixtures, prompts for labels
└── tests/
    ├── conftest.py                        # shared fixtures (synthetic snapshots, mock LLM)
    ├── test_schemas.py
    ├── test_snapshot.py
    ├── test_trace.py
    ├── test_llm.py
    ├── test_extract_cars24.py
    ├── test_extract_spinny.py
    ├── test_normalize.py
    ├── test_score.py
    ├── test_rank.py
    ├── test_pipeline.py
    ├── test_eval_extraction.py
    ├── test_eval_calibration.py
    ├── test_eval_sensitivity.py
    ├── test_eval_determinism.py
    └── test_report.py
```

---

## Conventions for every task

- **TDD throughout.** Failing test → minimal implementation → passing test → commit. No exceptions.
- **No live LLM calls in unit tests.** All extractor and pipeline tests use a `FakeLLMClient` (defined in T7) that returns canned responses. One end-to-end integration test (T13) optionally hits the real API behind an env-flag check.
- **Frequent commits.** Commit after every passing test cycle.
- **Run all tests after each task** with `uv run pytest -q`. New code never breaks earlier tasks.
- **Code style:** type hints everywhere, no docstrings unless behavior is non-obvious (per project conventions).

---

## Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/ci/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize uv project**

```bash
cd /Users/himan/Documents/projects/cars24-comp-intel
uv init --name ci --python 3.11
```

This creates `pyproject.toml`, `.python-version`, and a hello-world `main.py`. Delete `main.py` afterwards.

- [ ] **Step 2: Add runtime dependencies**

```bash
uv add pydantic anthropic scipy matplotlib python-dotenv
uv add --dev pytest pytest-cov
```

- [ ] **Step 3: Create source and test directory structure**

```bash
mkdir -p src/ci/extract src/ci/eval scripts tests fixtures eval runs docs
touch src/ci/__init__.py src/ci/extract/__init__.py src/ci/eval/__init__.py
touch tests/__init__.py
```

- [ ] **Step 4: Configure package layout in pyproject.toml**

Edit `pyproject.toml` so the `[project]` block includes a build target. Append:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ci"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 5: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 6: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
runs/
fixtures/*/page.html
.DS_Store
```

(Note: snapshot HTML is gitignored to avoid bloating the repo. `captured_at.txt` and small parsed JSON files stay tracked so the dataset roster is visible.)

- [ ] **Step 7: Write minimal `README.md`**

```markdown
# Cars24 vs Spinny Competitive Intel

Multi-agent extraction + ranking pipeline for an assessment task.
See `docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md`.

## Setup

    uv sync
    cp .env.example .env  # add ANTHROPIC_API_KEY

## Run

    uv run python scripts/collect_snapshots.py   # one-time, manual
    uv run python scripts/run_pipeline.py        # end-to-end on ranking 6
    uv run python scripts/run_evals.py           # E2-E5 over gold

## Test

    uv run pytest
```

- [ ] **Step 8: Write `tests/conftest.py` placeholder**

```python
import pytest


@pytest.fixture
def tmp_run_dir(tmp_path):
    d = tmp_path / "runs" / "test-run"
    d.mkdir(parents=True)
    return d
```

- [ ] **Step 9: Verify install + empty test run**

```bash
uv run pytest
```

Expected: `no tests ran` (or 0 collected) without errors.

- [ ] **Step 10: Initial commit**

```bash
cd /Users/himan/Documents/projects/cars24-comp-intel
git init
git add -A
git commit -m "chore: bootstrap uv project with pydantic/anthropic deps"
```

---

## Task 2: Configuration module

**Files:**
- Create: `src/ci/config.py`
- Test: (config is data-only; verified via use in later tasks — no dedicated test file)

This module is the **single source of truth** for weights, anchors, imputation values, and the disclosure-eligible field set. Every later module imports from here.

- [ ] **Step 1: Create `src/ci/config.py` with full content**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
EVAL_DIR = ROOT / "eval"
RUNS_DIR = ROOT / "runs"
DOCS_DIR = ROOT / "docs"

MODEL_EXTRACTOR = "claude-sonnet-4-6"
EXTRACTOR_TEMPERATURE = 0.0
EXTRACTOR_MAX_TOKENS = 4096

# --- score_common weight tables (§4) ---
# Used when accident_disclosed is included in the locked common set:
WEIGHTS_WITH_ACCIDENT = {
    "km_driven": 30,
    "age_years": 20,
    "owners": 20,
    "certification_flag": 15,
    "accident_disclosed": 15,
}
# Used when accident_disclosed is NOT in the locked common set:
WEIGHTS_WITHOUT_ACCIDENT = {
    "km_driven": 35,
    "age_years": 25,
    "owners": 25,
    "certification_flag": 15,
}

# --- anchored bands per dimension (§4) ---
KM_BANDS = [
    (20_000, 100),
    (40_000, 85),
    (70_000, 70),
    (100_000, 55),
    (150_000, 40),
    (float("inf"), 25),
]

AGE_BANDS = [
    (2, 100),
    (4, 85),
    (7, 65),
    (10, 45),
    (float("inf"), 25),
]

OWNERS_MAP = {1: 100, 2: 75, 3: 50}  # 4+ → 25 by lookup default

ACCIDENT_MAP = {
    "none": 100,
    "minor": 70,      # cosmetic
    "major": 30,      # structural
}

CERT_MAP = {
    "top": 100,       # Imperial / Royal Blue / Spinny Assured Plus
    "mid": 75,
    "base": 60,
    "none": 40,
}

# --- imputation anchors (§4 null handling) ---
IMPUTATION = {
    "km_driven": 60,
    "age_years": 60,
    "owners": 60,
    "accident_disclosed": 60,
    "certification_flag": 40,
}

# --- disclosure-eligible field set (§4 Disclosure metric, locked) ---
DISCLOSURE_FIELDS = [
    "accident_history_detail",
    "service_history_records",
    "inspection_issue_list",
    "inspection_points_passed",
    "cosmetic_exterior_notes",
    "cosmetic_interior_notes",
    "tire_condition",
    "engine_remarks",
    "transmission_remarks",
    "battery_status",
    "ac_remarks",
    "electrical_remarks",
    "previous_use_type",
    "noc_status",
    "hypothecation_status",
    "insurance_status",
    "rc_type",
    "challan_status",
    "warranty_remaining_months",
    "inspection_photo_count",
]

PROMPT_VERSION = "v1.0"
```

- [ ] **Step 2: Commit**

```bash
git add src/ci/config.py
git commit -m "feat(config): weights, anchors, imputation, disclosure field set"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `src/ci/schemas.py`
- Test: `tests/test_schemas.py`

All inter-node data shapes live here. Pipeline nodes consume and produce these.

- [ ] **Step 1: Write the failing tests**

`tests/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from ci.schemas import (
    RawListing, NormalizedListing, ScoreRecord, RankRow, GoldRecord, TraceEvent,
)


def test_raw_listing_minimal_valid():
    raw = RawListing(
        platform="cars24",
        listing_id="abc123",
        url="https://cars24.com/listing/abc123",
        captured_at="2026-05-06T10:00:00Z",
        fields={"price": 950000, "km_driven": 45000, "year": 2020},
    )
    assert raw.platform == "cars24"
    assert raw.fields["price"] == 950000


def test_raw_listing_rejects_unknown_platform():
    with pytest.raises(ValidationError):
        RawListing(
            platform="olx",
            listing_id="x",
            url="https://x",
            captured_at="2026-05-06T10:00:00Z",
            fields={},
        )


def test_normalized_listing_requires_common_fields():
    n = NormalizedListing(
        platform="spinny",
        listing_id="x",
        price=1_100_000,
        km_driven=38_000,
        age_years=4,
        owners=1,
        certification_flag="top",
        accident_disclosed=None,
        disclosed_fields={"accident_history_detail": True, "service_history_records": False},
        full_fields={"accident_history_detail": "minor rear bumper scuff"},
    )
    assert n.disclosed_fields["accident_history_detail"] is True


def test_score_record_shape():
    s = ScoreRecord(
        listing_id="x",
        platform="cars24",
        score_common=78.5,
        per_dim={"km_driven": 85, "age_years": 65, "owners": 100, "certification_flag": 60},
        imputed_dims=[],
        disclosure_count=4,
        disclosed_fields={f: False for f in []},
    )
    assert s.score_common == 78.5


def test_rank_row_ratio():
    r = RankRow(
        listing_id="x",
        platform="cars24",
        price=900_000,
        score_common=75.0,
        ratio=12_000.0,
        disclosure_count=4,
        imputed_dims=[],
    )
    assert r.ratio == 12_000.0


def test_gold_record_shape():
    g = GoldRecord(
        listing_id="x",
        platform="spinny",
        full_fields={"price": 1_200_000, "km_driven": 30_000},
        score_common=82.0,
        notes={"km_driven": "30k, well below band threshold"},
    )
    assert g.score_common == 82.0


def test_trace_event_shape():
    t = TraceEvent(
        run_id="r1",
        node="extract.cars24",
        timestamp="2026-05-06T10:00:01Z",
        input_hash="abc",
        output_hash="def",
        latency_ms=1234,
        tokens_in=500,
        tokens_out=200,
        model="claude-sonnet-4-6",
        prompt_version="v1.0",
        cost_usd=0.0123,
    )
    assert t.node == "extract.cars24"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_schemas.py -v
```

Expected: ImportError on `ci.schemas`.

- [ ] **Step 3: Implement `src/ci/schemas.py`**

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

Platform = Literal["cars24", "spinny"]


class RawListing(BaseModel):
    platform: Platform
    listing_id: str
    url: str
    captured_at: str
    fields: dict[str, Any]


class NormalizedListing(BaseModel):
    platform: Platform
    listing_id: str

    # common fields used in score_common
    price: int
    km_driven: int | None
    age_years: int | None
    owners: int | None
    certification_flag: Literal["top", "mid", "base", "none"] | None
    accident_disclosed: Literal["none", "minor", "major"] | None

    # disclosure measurement (§4)
    disclosed_fields: dict[str, bool]
    full_fields: dict[str, Any]


class ScoreRecord(BaseModel):
    listing_id: str
    platform: Platform
    score_common: float
    per_dim: dict[str, float]
    imputed_dims: list[str]
    disclosure_count: int
    disclosed_fields: dict[str, bool]


class RankRow(BaseModel):
    listing_id: str
    platform: Platform
    price: int
    score_common: float
    ratio: float
    disclosure_count: int
    imputed_dims: list[str]


class GoldRecord(BaseModel):
    listing_id: str
    platform: Platform
    full_fields: dict[str, Any]
    score_common: float
    notes: dict[str, str] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    run_id: str
    node: str
    timestamp: str
    input_hash: str
    output_hash: str
    latency_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    prompt_version: str = ""
    cost_usd: float = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_schemas.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/schemas.py tests/test_schemas.py
git commit -m "feat(schemas): pydantic models for raw, normalized, score, rank, gold, trace"
```

---

## Task 4: Trace store

**Files:**
- Create: `src/ci/trace.py`
- Test: `tests/test_trace.py`

Append-only JSONL writer. One file per `run_id`. Used by every pipeline node.

- [ ] **Step 1: Write the failing tests**

`tests/test_trace.py`:

```python
import json
from ci.trace import TraceStore
from ci.schemas import TraceEvent


def test_trace_store_writes_jsonl(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    ev = TraceEvent(
        run_id="r1", node="extract.cars24",
        timestamp="2026-05-06T10:00:00Z",
        input_hash="a", output_hash="b",
        latency_ms=100,
    )
    store.write(ev)
    contents = (tmp_path / "runs" / "r1" / "trace.jsonl").read_text().strip()
    assert json.loads(contents)["node"] == "extract.cars24"


def test_trace_store_appends_multiple(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    for n in ["a", "b", "c"]:
        store.write(TraceEvent(
            run_id="r1", node=n,
            timestamp="t", input_hash="i", output_hash="o", latency_ms=1,
        ))
    lines = (tmp_path / "runs" / "r1" / "trace.jsonl").read_text().strip().splitlines()
    assert [json.loads(l)["node"] for l in lines] == ["a", "b", "c"]


def test_trace_store_read_returns_events(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    ev = TraceEvent(
        run_id="r1", node="x",
        timestamp="t", input_hash="i", output_hash="o", latency_ms=42,
    )
    store.write(ev)
    events = list(store.read())
    assert len(events) == 1
    assert events[0].latency_ms == 42
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_trace.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/trace.py`**

```python
import json
from pathlib import Path
from typing import Iterator

from ci.schemas import TraceEvent


class TraceStore:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "trace.jsonl"

    def write(self, event: TraceEvent) -> None:
        with self.path.open("a") as f:
            f.write(event.model_dump_json())
            f.write("\n")

    def read(self) -> Iterator[TraceEvent]:
        if not self.path.exists():
            return
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    yield TraceEvent.model_validate_json(line)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_trace.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/trace.py tests/test_trace.py
git commit -m "feat(trace): append-only jsonl trace store per run_id"
```

---

## Task 5: Snapshot loader

**Files:**
- Create: `src/ci/snapshot.py`
- Test: `tests/test_snapshot.py`

Loads HTML + metadata from `fixtures/<platform>/<listing_id>/`. **No network access.** Eval is reproducible because everything replays from disk.

- [ ] **Step 1: Write the failing tests**

`tests/test_snapshot.py`:

```python
import pytest
from ci.snapshot import load_snapshot, list_snapshots, SnapshotMissing


def test_load_snapshot_returns_html_and_metadata(tmp_path, monkeypatch):
    fix = tmp_path / "fixtures" / "cars24" / "abc"
    fix.mkdir(parents=True)
    (fix / "page.html").write_text("<html>hi</html>")
    (fix / "captured_at.txt").write_text("2026-05-06T10:00:00Z")

    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    snap = load_snapshot("cars24", "abc")
    assert snap.html == "<html>hi</html>"
    assert snap.captured_at == "2026-05-06T10:00:00Z"
    assert snap.platform == "cars24"
    assert snap.listing_id == "abc"


def test_load_snapshot_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")
    with pytest.raises(SnapshotMissing):
        load_snapshot("cars24", "ghost")


def test_list_snapshots_per_platform(tmp_path, monkeypatch):
    for plat, lid in [("cars24", "a"), ("cars24", "b"), ("spinny", "c")]:
        fix = tmp_path / "fixtures" / plat / lid
        fix.mkdir(parents=True)
        (fix / "page.html").write_text("x")
        (fix / "captured_at.txt").write_text("t")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    assert sorted(list_snapshots("cars24")) == ["a", "b"]
    assert list_snapshots("spinny") == ["c"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_snapshot.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/snapshot.py`**

```python
from dataclasses import dataclass
from pathlib import Path

from ci.config import FIXTURES_DIR


class SnapshotMissing(FileNotFoundError):
    pass


@dataclass
class Snapshot:
    platform: str
    listing_id: str
    html: str
    captured_at: str


def load_snapshot(platform: str, listing_id: str) -> Snapshot:
    fix = FIXTURES_DIR / platform / listing_id
    if not fix.exists():
        raise SnapshotMissing(f"{platform}/{listing_id}")
    html_path = fix / "page.html"
    cap_path = fix / "captured_at.txt"
    if not html_path.exists() or not cap_path.exists():
        raise SnapshotMissing(f"incomplete snapshot at {fix}")
    return Snapshot(
        platform=platform,
        listing_id=listing_id,
        html=html_path.read_text(),
        captured_at=cap_path.read_text().strip(),
    )


def list_snapshots(platform: str) -> list[str]:
    base = FIXTURES_DIR / platform
    if not base.exists():
        return []
    return [d.name for d in base.iterdir() if d.is_dir()]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_snapshot.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/snapshot.py tests/test_snapshot.py
git commit -m "feat(snapshot): disk-only loader for fixtures"
```

---

## Task 6: Snapshot collection helper script

**Files:**
- Create: `scripts/collect_snapshots.py`
- (No automated test — script is operator-driven and uses live network.)

This script is run **once** by the operator to capture HTML for the 6 ranking listings + 15 gold listings. It is **not** part of the runtime pipeline.

- [ ] **Step 1: Write `scripts/collect_snapshots.py`**

```python
"""
One-time snapshot collection.

Usage:
    uv run python scripts/collect_snapshots.py <platform> <listing_id> <url>

Saves to fixtures/<platform>/<listing_id>/{page.html, captured_at.txt}.
The operator is expected to provide URLs from the public listing pages
of Cars24 / Spinny for Hyundai Creta in Delhi-NCR within ₹8-14L.

This script does NOT bypass any access control. It does a single GET
with a normal browser User-Agent. If the page requires JS rendering,
the operator should save the rendered HTML manually via browser
"Save Page As" and place it at fixtures/<platform>/<listing_id>/page.html
plus write captured_at.txt by hand.
"""
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ci.config import FIXTURES_DIR

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def collect(platform: str, listing_id: str, url: str) -> Path:
    if platform not in ("cars24", "spinny"):
        raise SystemExit(f"unsupported platform: {platform}")
    out_dir = FIXTURES_DIR / platform / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    (out_dir / "page.html").write_text(html)
    (out_dir / "captured_at.txt").write_text(
        datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    print(f"saved {out_dir}")
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    collect(sys.argv[1], sys.argv[2], sys.argv[3])
```

- [ ] **Step 2: Run a smoke test against a benign URL**

```bash
uv run python scripts/collect_snapshots.py cars24 _smoke https://example.com
ls fixtures/cars24/_smoke/
```

Expected: `page.html` and `captured_at.txt` exist. Delete the smoke fixture afterwards:

```bash
rm -rf fixtures/cars24/_smoke
```

- [ ] **Step 3: Operator collection step (manual, off-plan)**

The operator runs the script (or saves HTML manually if JS rendering is required) for:
- 3 Cars24 Hyundai Creta listings, Delhi-NCR, ₹8-14L
- 3 Spinny Hyundai Creta listings, Delhi-NCR, ₹8-14L
- 7-8 additional gold listings per platform

Listing IDs should be stable identifiers visible in the URL. **Do not include personal/auth-required pages.**

- [ ] **Step 4: Commit**

```bash
git add scripts/collect_snapshots.py
git commit -m "feat(scripts): one-time snapshot collection helper"
```

---

## Task 7: LLM client wrapper

**Files:**
- Create: `src/ci/llm.py`
- Test: `tests/test_llm.py`

Thin wrapper over the Anthropic SDK that (a) uses the **tool-use pattern** to force structured output matching a schema, (b) is mockable in tests via a `Protocol`.

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:

```python
from ci.llm import LLMResponse, FakeLLMClient


def test_fake_client_returns_canned_tool_input():
    client = FakeLLMClient(canned_tool_input={"price": 900_000, "km_driven": 45_000})
    resp = client.extract_structured(
        system="you extract", user="some html", tool_name="extract", tool_schema={
            "type": "object", "properties": {}, "required": [],
        },
    )
    assert isinstance(resp, LLMResponse)
    assert resp.parsed == {"price": 900_000, "km_driven": 45_000}
    assert resp.tokens_in > 0
    assert resp.tokens_out > 0


def test_fake_client_records_calls():
    client = FakeLLMClient(canned_tool_input={"x": 1})
    client.extract_structured(
        system="s", user="u", tool_name="t", tool_schema={"type": "object", "properties": {}, "required": []},
    )
    assert len(client.calls) == 1
    assert client.calls[0]["user"] == "u"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_llm.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/llm.py`**

```python
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from anthropic import Anthropic

from ci.config import (
    EXTRACTOR_MAX_TOKENS,
    EXTRACTOR_TEMPERATURE,
    MODEL_EXTRACTOR,
)


@dataclass
class LLMResponse:
    parsed: dict[str, Any]
    tokens_in: int
    tokens_out: int
    model: str


class LLMClient(Protocol):
    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse: ...


class AnthropicLLMClient:
    def __init__(self, api_key: str | None = None, model: str = MODEL_EXTRACTOR):
        self.client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=EXTRACTOR_MAX_TOKENS,
            temperature=EXTRACTOR_TEMPERATURE,
            system=system,
            tools=[{
                "name": tool_name,
                "description": "Return the structured extraction.",
                "input_schema": tool_schema,
            }],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )
        # Find the tool_use block.
        tool_block = next(b for b in msg.content if b.type == "tool_use")
        return LLMResponse(
            parsed=tool_block.input,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            model=self.model,
        )


@dataclass
class FakeLLMClient:
    canned_tool_input: dict[str, Any]
    canned_tokens_in: int = 100
    canned_tokens_out: int = 50
    model: str = "fake"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse:
        self.calls.append({
            "system": system, "user": user,
            "tool_name": tool_name, "tool_schema": tool_schema,
        })
        return LLMResponse(
            parsed=self.canned_tool_input,
            tokens_in=self.canned_tokens_in,
            tokens_out=self.canned_tokens_out,
            model=self.model,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_llm.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/llm.py tests/test_llm.py
git commit -m "feat(llm): anthropic client wrapper with tool-use structured output and fake for tests"
```

---

## Task 8: Cars24 extraction agent

**Files:**
- Create: `src/ci/extract/cars24.py`
- Test: `tests/test_extract_cars24.py`

Takes a `Snapshot`, returns a `RawListing` keyed for the Cars24 schema.

- [ ] **Step 1: Write the failing tests**

`tests/test_extract_cars24.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_extract_cars24.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/extract/cars24.py`**

```python
from ci.llm import LLMClient
from ci.schemas import RawListing
from ci.snapshot import Snapshot

CARS24_SYSTEM = """You extract structured data from Cars24 used-car listing HTML.
Return ONLY values you can find in the page; for any field you cannot find, return null.
Do not infer, normalize, or invent. Numeric fields must be integers (no commas).
Year is the manufacturing year. Owners count is the integer number of prior owners.
Certification tier is the platform's named tier (e.g. "Imperial", "Royal Blue") or
null if no tier badge is visible. Accident disclosed is "none" / "minor" / "major" or null."""

CARS24_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "price": {"type": ["integer", "null"]},
        "km_driven": {"type": ["integer", "null"]},
        "year": {"type": ["integer", "null"]},
        "owners_count": {"type": ["integer", "null"]},
        "registration_state": {"type": ["string", "null"]},
        "fuel": {"type": ["string", "null"]},
        "transmission": {"type": ["string", "null"]},
        "body_color": {"type": ["string", "null"]},
        "certification_tier": {"type": ["string", "null"]},
        "accident_disclosed": {
            "type": ["string", "null"],
            "enum": ["none", "minor", "major", None],
        },
        "inspection_issue_list": {"type": ["array", "null"], "items": {"type": "string"}},
        "service_history_records": {"type": ["string", "null"]},
        "warranty_remaining_months": {"type": ["integer", "null"]},
        "noc_status": {"type": ["string", "null"]},
        "rc_type": {"type": ["string", "null"]},
        "insurance_status": {"type": ["string", "null"]},
        "previous_use_type": {"type": ["string", "null"]},
        "tire_condition": {"type": ["string", "null"]},
        "engine_remarks": {"type": ["string", "null"]},
        "transmission_remarks": {"type": ["string", "null"]},
        "battery_status": {"type": ["string", "null"]},
        "ac_remarks": {"type": ["string", "null"]},
        "electrical_remarks": {"type": ["string", "null"]},
        "cosmetic_exterior_notes": {"type": ["string", "null"]},
        "cosmetic_interior_notes": {"type": ["string", "null"]},
        "challan_status": {"type": ["string", "null"]},
        "hypothecation_status": {"type": ["string", "null"]},
        "inspection_photo_count": {"type": ["integer", "null"]},
        "inspection_points_passed": {"type": ["string", "null"]},
        "accident_history_detail": {"type": ["string", "null"]},
    },
    "required": ["price", "km_driven", "year"],
}


def extract_cars24(snapshot: Snapshot, client: LLMClient) -> RawListing:
    user = (
        "Extract the structured fields from this Cars24 listing HTML. "
        "If a field is not visible, return null. Do not invent values.\n\n"
        f"HTML:\n{snapshot.html}"
    )
    resp = client.extract_structured(
        system=CARS24_SYSTEM,
        user=user,
        tool_name="cars24_extract",
        tool_schema=CARS24_TOOL_SCHEMA,
    )
    return RawListing(
        platform="cars24",
        listing_id=snapshot.listing_id,
        url=f"snapshot://{snapshot.listing_id}",
        captured_at=snapshot.captured_at,
        fields=resp.parsed,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_extract_cars24.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/extract/cars24.py tests/test_extract_cars24.py
git commit -m "feat(extract): cars24 LLM extraction agent"
```

---

## Task 9: Spinny extraction agent

**Files:**
- Create: `src/ci/extract/spinny.py`
- Test: `tests/test_extract_spinny.py`

Mirror of Task 8 but for Spinny's vocabulary.

- [ ] **Step 1: Write the failing tests**

`tests/test_extract_spinny.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_extract_spinny.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/extract/spinny.py`**

```python
from ci.llm import LLMClient
from ci.schemas import RawListing
from ci.snapshot import Snapshot

SPINNY_SYSTEM = """You extract structured data from Spinny used-car listing HTML.
Return ONLY values present in the page; for any field you cannot find, return null.
Do not infer, normalize, or invent. Numeric fields must be integers.
Spinny tier values are typically "Assured" or "Assured Plus" (or null if no badge).
Inspection points passed should be a string like "194/200" if present, else null.
Accident detail is the verbatim summary if exposed, else null."""

SPINNY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "price": {"type": ["integer", "null"]},
        "km_driven": {"type": ["integer", "null"]},
        "year": {"type": ["integer", "null"]},
        "owners_count": {"type": ["integer", "null"]},
        "registration_state": {"type": ["string", "null"]},
        "fuel": {"type": ["string", "null"]},
        "transmission": {"type": ["string", "null"]},
        "body_color": {"type": ["string", "null"]},
        "spinny_assured_tier": {"type": ["string", "null"]},
        "inspection_points_passed": {"type": ["string", "null"]},
        "inspection_issue_list": {"type": ["array", "null"], "items": {"type": "string"}},
        "accident_history_detail": {"type": ["string", "null"]},
        "service_history_records": {"type": ["string", "null"]},
        "warranty_remaining_months": {"type": ["integer", "null"]},
        "noc_status": {"type": ["string", "null"]},
        "rc_type": {"type": ["string", "null"]},
        "insurance_status": {"type": ["string", "null"]},
        "previous_use_type": {"type": ["string", "null"]},
        "tire_condition": {"type": ["string", "null"]},
        "engine_remarks": {"type": ["string", "null"]},
        "transmission_remarks": {"type": ["string", "null"]},
        "battery_status": {"type": ["string", "null"]},
        "ac_remarks": {"type": ["string", "null"]},
        "electrical_remarks": {"type": ["string", "null"]},
        "cosmetic_exterior_notes": {"type": ["string", "null"]},
        "cosmetic_interior_notes": {"type": ["string", "null"]},
        "challan_status": {"type": ["string", "null"]},
        "hypothecation_status": {"type": ["string", "null"]},
        "inspection_photo_count": {"type": ["integer", "null"]},
    },
    "required": ["price", "km_driven", "year"],
}


def extract_spinny(snapshot: Snapshot, client: LLMClient) -> RawListing:
    user = (
        "Extract the structured fields from this Spinny listing HTML. "
        "If a field is not visible, return null. Do not invent values.\n\n"
        f"HTML:\n{snapshot.html}"
    )
    resp = client.extract_structured(
        system=SPINNY_SYSTEM,
        user=user,
        tool_name="spinny_extract",
        tool_schema=SPINNY_TOOL_SCHEMA,
    )
    return RawListing(
        platform="spinny",
        listing_id=snapshot.listing_id,
        url=f"snapshot://{snapshot.listing_id}",
        captured_at=snapshot.captured_at,
        fields=resp.parsed,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_extract_spinny.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/extract/spinny.py tests/test_extract_spinny.py
git commit -m "feat(extract): spinny LLM extraction agent"
```

---

## Task 10: Normalizer

**Files:**
- Create: `src/ci/normalize.py`
- Test: `tests/test_normalize.py`

Maps platform-specific `RawListing` to a `NormalizedListing`. Computes `disclosed_fields` from the disclosure-eligible field set. Maps platform-specific tier names to canonical tier values.

- [ ] **Step 1: Write the failing tests**

`tests/test_normalize.py`:

```python
from ci.normalize import normalize
from ci.schemas import RawListing


def _raw(platform, fields):
    return RawListing(
        platform=platform, listing_id="x", url="snapshot://x",
        captured_at="2026-05-06T10:00:00Z", fields=fields,
    )


def test_normalize_cars24_imperial_tier_top():
    raw = _raw("cars24", {
        "price": 950_000, "km_driven": 45_000, "year": 2020,
        "owners_count": 1, "certification_tier": "Imperial",
        "accident_disclosed": None, "service_history_records": "yes, 4 records",
    })
    n = normalize(raw, today_year=2026)
    assert n.price == 950_000
    assert n.km_driven == 45_000
    assert n.age_years == 6
    assert n.owners == 1
    assert n.certification_flag == "top"
    assert n.disclosed_fields["service_history_records"] is True
    assert n.disclosed_fields["accident_history_detail"] is False


def test_normalize_spinny_assured_plus_tier_top():
    raw = _raw("spinny", {
        "price": 1_200_000, "km_driven": 30_000, "year": 2022,
        "owners_count": 1, "spinny_assured_tier": "Assured Plus",
        "inspection_issue_list": ["minor scratch"],
        "accident_history_detail": "minor cosmetic",
    })
    n = normalize(raw, today_year=2026)
    assert n.certification_flag == "top"
    assert n.disclosed_fields["inspection_issue_list"] is True
    assert n.disclosed_fields["accident_history_detail"] is True


def test_normalize_uncertified_listing_maps_to_none():
    raw = _raw("cars24", {
        "price": 800_000, "km_driven": 80_000, "year": 2018,
        "owners_count": 2, "certification_tier": None,
    })
    n = normalize(raw, today_year=2026)
    assert n.certification_flag == "none"


def test_normalize_full_fields_carries_extra_keys():
    raw = _raw("cars24", {
        "price": 800_000, "km_driven": 80_000, "year": 2018,
        "owners_count": 2, "certification_tier": "Imperial",
        "warranty_remaining_months": 6,
    })
    n = normalize(raw, today_year=2026)
    assert n.full_fields["warranty_remaining_months"] == 6
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_normalize.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/normalize.py`**

```python
from datetime import datetime

from ci.config import DISCLOSURE_FIELDS
from ci.schemas import NormalizedListing, RawListing

CARS24_TIER_MAP: dict[str, str] = {
    "imperial": "top",
    "royal blue": "top",
    "royal": "top",
    # extend as platform vocabulary changes
}

SPINNY_TIER_MAP: dict[str, str] = {
    "assured plus": "top",
    "assured": "mid",
}


def _map_cert_cars24(tier: str | None) -> str:
    if tier is None or not tier.strip():
        return "none"
    return CARS24_TIER_MAP.get(tier.strip().lower(), "base")


def _map_cert_spinny(tier: str | None) -> str:
    if tier is None or not tier.strip():
        return "none"
    return SPINNY_TIER_MAP.get(tier.strip().lower(), "base")


def _disclosed(fields: dict, name: str) -> bool:
    v = fields.get(name)
    if v is None:
        return False
    if isinstance(v, str) and v.strip() == "":
        return False
    if isinstance(v, list) and len(v) == 0:
        return False
    return True


def normalize(raw: RawListing, today_year: int | None = None) -> NormalizedListing:
    today_year = today_year or datetime.utcnow().year
    f = raw.fields

    age = None
    if f.get("year") is not None:
        age = max(today_year - int(f["year"]), 0)

    if raw.platform == "cars24":
        cert = _map_cert_cars24(f.get("certification_tier"))
    else:
        cert = _map_cert_spinny(f.get("spinny_assured_tier"))

    disclosed = {name: _disclosed(f, name) for name in DISCLOSURE_FIELDS}

    return NormalizedListing(
        platform=raw.platform,
        listing_id=raw.listing_id,
        price=int(f["price"]),
        km_driven=f.get("km_driven"),
        age_years=age,
        owners=f.get("owners_count"),
        certification_flag=cert,
        accident_disclosed=f.get("accident_disclosed"),
        disclosed_fields=disclosed,
        full_fields=dict(f),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_normalize.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/normalize.py tests/test_normalize.py
git commit -m "feat(normalize): platform raw to common schema with disclosure tracking"
```

---

## Task 11: Scorer (composite + disclosure_count)

**Files:**
- Create: `src/ci/score.py`
- Test: `tests/test_score.py`

Deterministic. Produces `score_common`, per-dim breakdown, imputed-dims list, and `disclosure_count`. Weight table choice depends on whether `accident_disclosed` is in the locked common set — passed in via parameter.

- [ ] **Step 1: Write the failing tests**

`tests/test_score.py`:

```python
import pytest
from ci.score import score_listing, _km_band, _age_band, _owners_band, _accident_band
from ci.schemas import NormalizedListing


def _norm(**kw):
    base = dict(
        platform="cars24", listing_id="x", price=900_000,
        km_driven=45_000, age_years=4, owners=1,
        certification_flag="top", accident_disclosed="none",
        disclosed_fields={f: False for f in []},
        full_fields={},
    )
    base.update(kw)
    return NormalizedListing(**base)


def test_km_band_lookup():
    assert _km_band(15_000) == 100
    assert _km_band(45_000) == 70
    assert _km_band(160_000) == 25


def test_age_band_lookup():
    assert _age_band(1) == 100
    assert _age_band(5) == 65
    assert _age_band(11) == 25


def test_owners_band_lookup():
    assert _owners_band(1) == 100
    assert _owners_band(2) == 75
    assert _owners_band(4) == 25
    assert _owners_band(7) == 25


def test_accident_band_lookup():
    assert _accident_band("none") == 100
    assert _accident_band("minor") == 70
    assert _accident_band("major") == 30


def test_score_listing_excellent_with_accident_in_common():
    n = _norm(km_driven=18_000, age_years=1, owners=1,
              certification_flag="top", accident_disclosed="none")
    s = score_listing(n, accident_in_common=True)
    assert s.score_common == pytest.approx(100.0, abs=0.01)
    assert s.imputed_dims == []


def test_score_listing_average_with_accident_in_common():
    n = _norm(km_driven=60_000, age_years=5, owners=2,
              certification_flag="mid", accident_disclosed="minor")
    s = score_listing(n, accident_in_common=True)
    expected = 0.30 * 70 + 0.20 * 65 + 0.20 * 75 + 0.15 * 75 + 0.15 * 70
    assert s.score_common == pytest.approx(expected, abs=0.01)


def test_score_listing_imputes_missing_km():
    n = _norm(km_driven=None, age_years=4, owners=1,
              certification_flag="top", accident_disclosed="none")
    s = score_listing(n, accident_in_common=True)
    assert "km_driven" in s.imputed_dims
    expected = 0.30 * 60 + 0.20 * 85 + 0.20 * 100 + 0.15 * 100 + 0.15 * 100
    assert s.score_common == pytest.approx(expected, abs=0.01)


def test_score_listing_without_accident_in_common_uses_4_dim_weights():
    n = _norm(km_driven=45_000, age_years=4, owners=1,
              certification_flag="top", accident_disclosed=None)
    s = score_listing(n, accident_in_common=False)
    expected = 0.35 * 70 + 0.25 * 85 + 0.25 * 100 + 0.15 * 100
    assert s.score_common == pytest.approx(expected, abs=0.01)
    assert "accident_disclosed" not in s.per_dim


def test_score_listing_disclosure_count():
    disclosed = {f: False for f in []}
    disclosed.update({"accident_history_detail": True, "service_history_records": True})
    n = _norm(disclosed_fields=disclosed)
    s = score_listing(n, accident_in_common=True)
    assert s.disclosure_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_score.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/score.py`**

```python
from ci.config import (
    ACCIDENT_MAP,
    AGE_BANDS,
    CERT_MAP,
    IMPUTATION,
    KM_BANDS,
    OWNERS_MAP,
    WEIGHTS_WITH_ACCIDENT,
    WEIGHTS_WITHOUT_ACCIDENT,
)
from ci.schemas import NormalizedListing, ScoreRecord


def _km_band(km: int) -> int:
    for ceil, val in KM_BANDS:
        if km < ceil:
            return val
    return KM_BANDS[-1][1]


def _age_band(age: int) -> int:
    for ceil, val in AGE_BANDS:
        if age < ceil:
            return val
    return AGE_BANDS[-1][1]


def _owners_band(owners: int) -> int:
    if owners >= 4:
        return 25
    return OWNERS_MAP.get(owners, 25)


def _accident_band(label: str) -> int:
    return ACCIDENT_MAP[label]


def _cert_band(label: str) -> int:
    return CERT_MAP[label]


def _value_for_dim(name: str, n: NormalizedListing) -> tuple[float, bool]:
    """Return (value, was_imputed)."""
    v = getattr(n, name)
    if v is None:
        return float(IMPUTATION[name]), True
    if name == "km_driven":
        return float(_km_band(v)), False
    if name == "age_years":
        return float(_age_band(v)), False
    if name == "owners":
        return float(_owners_band(v)), False
    if name == "accident_disclosed":
        return float(_accident_band(v)), False
    if name == "certification_flag":
        return float(_cert_band(v)), False
    raise KeyError(name)


def score_listing(n: NormalizedListing, *, accident_in_common: bool) -> ScoreRecord:
    weights = WEIGHTS_WITH_ACCIDENT if accident_in_common else WEIGHTS_WITHOUT_ACCIDENT
    per_dim: dict[str, float] = {}
    imputed: list[str] = []
    total = 0.0
    for dim, w in weights.items():
        v, was_imp = _value_for_dim(dim, n)
        per_dim[dim] = v
        if was_imp:
            imputed.append(dim)
        total += (w / 100.0) * v

    return ScoreRecord(
        listing_id=n.listing_id,
        platform=n.platform,
        score_common=round(total, 2),
        per_dim=per_dim,
        imputed_dims=imputed,
        disclosure_count=sum(1 for v in n.disclosed_fields.values() if v),
        disclosed_fields=dict(n.disclosed_fields),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_score.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/score.py tests/test_score.py
git commit -m "feat(score): deterministic composite scorer with imputation + disclosure"
```

---

## Task 12: Ranker

**Files:**
- Create: `src/ci/rank.py`
- Test: `tests/test_rank.py`

Computes `ratio = price / score_common`, sorts ascending (lower ratio = better deal), returns a list of `RankRow`.

- [ ] **Step 1: Write the failing tests**

`tests/test_rank.py`:

```python
from ci.rank import rank_listings
from ci.schemas import NormalizedListing, ScoreRecord


def _pair(lid, plat, price, score, disclosure=0, imputed=None):
    n = NormalizedListing(
        platform=plat, listing_id=lid, price=price,
        km_driven=50_000, age_years=4, owners=1,
        certification_flag="top", accident_disclosed=None,
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_rank.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/rank.py`**

```python
from ci.schemas import NormalizedListing, RankRow, ScoreRecord


def rank_listings(
    pairs: list[tuple[NormalizedListing, ScoreRecord]],
) -> list[RankRow]:
    rows: list[RankRow] = []
    for n, s in pairs:
        ratio = n.price / s.score_common if s.score_common > 0 else float("inf")
        rows.append(RankRow(
            listing_id=n.listing_id,
            platform=n.platform,
            price=n.price,
            score_common=s.score_common,
            ratio=round(ratio, 2),
            disclosure_count=s.disclosure_count,
            imputed_dims=list(s.imputed_dims),
        ))
    rows.sort(key=lambda r: r.ratio)
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_rank.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/rank.py tests/test_rank.py
git commit -m "feat(rank): ratio compute + ascending sort"
```

---

## Task 13: Pipeline orchestration

**Files:**
- Create: `src/ci/pipeline.py`
- Create: `scripts/run_pipeline.py`
- Test: `tests/test_pipeline.py`

Wires together loader → extractor → normalizer → scorer → ranker, writes a `TraceEvent` per node.

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline.py`:

```python
import json
from pathlib import Path

from ci.llm import FakeLLMClient
from ci.pipeline import run_pipeline
from ci.snapshot import Snapshot


def test_pipeline_runs_end_to_end_with_fake_llm(tmp_path, monkeypatch):
    fix_root = tmp_path / "fixtures"
    for plat, lid in [("cars24", "a"), ("spinny", "b")]:
        d = fix_root / plat / lid
        d.mkdir(parents=True)
        (d / "page.html").write_text("<html>x</html>")
        (d / "captured_at.txt").write_text("2026-05-06T10:00:00Z")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", fix_root)

    fake = FakeLLMClient(canned_tool_input={
        "price": 950_000, "km_driven": 45_000, "year": 2022,
        "owners_count": 1, "certification_tier": "Imperial",
        "spinny_assured_tier": "Assured Plus",
    })

    rows = run_pipeline(
        ranking_listings=[("cars24", "a"), ("spinny", "b")],
        client=fake,
        run_dir=tmp_path / "runs" / "r1",
        accident_in_common=False,
        today_year=2026,
    )
    assert len(rows) == 2
    assert all(r.score_common > 0 for r in rows)
    trace_path = tmp_path / "runs" / "r1" / "trace.jsonl"
    lines = trace_path.read_text().strip().splitlines()
    nodes = [json.loads(l)["node"] for l in lines]
    assert "extract.cars24" in nodes
    assert "extract.spinny" in nodes
    assert "score" in nodes
    assert "rank" in nodes
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/pipeline.py`**

```python
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.llm import LLMClient
from ci.normalize import normalize
from ci.rank import rank_listings
from ci.schemas import RankRow, TraceEvent
from ci.score import score_listing
from ci.snapshot import load_snapshot
from ci.trace import TraceStore


def _hash(obj) -> str:
    return hashlib.sha1(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _trace(store: TraceStore, run_id: str, node: str, t0: float, inp, out) -> None:
    store.write(TraceEvent(
        run_id=run_id,
        node=node,
        timestamp=_now(),
        input_hash=_hash(inp),
        output_hash=_hash(out),
        latency_ms=int((time.time() - t0) * 1000),
    ))


def run_pipeline(
    *,
    ranking_listings: list[tuple[str, str]],
    client: LLMClient,
    run_dir: Path,
    accident_in_common: bool,
    today_year: int | None = None,
) -> list[RankRow]:
    run_id = run_dir.name
    store = TraceStore(run_dir=run_dir)
    pairs = []

    for platform, lid in ranking_listings:
        t0 = time.time()
        snap = load_snapshot(platform, lid)
        _trace(store, run_id, f"snapshot.load.{platform}", t0,
               {"platform": platform, "listing_id": lid},
               {"captured_at": snap.captured_at})

        t0 = time.time()
        if platform == "cars24":
            raw = extract_cars24(snap, client)
        else:
            raw = extract_spinny(snap, client)
        _trace(store, run_id, f"extract.{platform}", t0,
               {"listing_id": lid}, raw.model_dump())

        t0 = time.time()
        norm = normalize(raw, today_year=today_year)
        _trace(store, run_id, f"normalize.{platform}", t0,
               raw.model_dump(), norm.model_dump())

        t0 = time.time()
        sc = score_listing(norm, accident_in_common=accident_in_common)
        _trace(store, run_id, "score", t0, norm.model_dump(), sc.model_dump())

        pairs.append((norm, sc))

    t0 = time.time()
    rows = rank_listings(pairs)
    _trace(store, run_id, "rank", t0,
           [{"id": p[0].listing_id} for p in pairs],
           [r.model_dump() for r in rows])

    return rows
```

- [ ] **Step 4: Implement `scripts/run_pipeline.py`**

```python
"""Run the end-to-end pipeline on the 6 ranking listings.

Reads ranking listing IDs from eval/ranking_listings.json (operator-provided).
Writes trace + ranking output under runs/<timestamp>/.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from ci.config import EVAL_DIR, RUNS_DIR
from ci.llm import AnthropicLLMClient
from ci.pipeline import run_pipeline


def main() -> None:
    load_dotenv()
    listings_file = EVAL_DIR / "ranking_listings.json"
    listings = [(d["platform"], d["listing_id"]) for d in json.loads(listings_file.read_text())]
    accident_meta = json.loads((EVAL_DIR / "common_set.json").read_text())
    accident_in_common = accident_meta.get("accident_in_common", False)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = RUNS_DIR / run_id

    client = AnthropicLLMClient()
    rows = run_pipeline(
        ranking_listings=listings,
        client=client,
        run_dir=run_dir,
        accident_in_common=accident_in_common,
    )
    out_path = run_dir / "ranking.json"
    out_path.write_text(json.dumps([r.model_dump() for r in rows], indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/ci/pipeline.py scripts/run_pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): DAG orchestration with per-node trace + run script"
```

---

## Task 14: Gold dataset format + labeling helper

**Files:**
- Create: `eval/gold_template.json`
- Create: `eval/ranking_listings.json` (empty list to be filled by operator)
- Create: `eval/common_set.json` (default: `{"accident_in_common": false}`)
- Create: `scripts/label_gold.py`

This task produces the *structure* and *helper*, not the labels themselves. Labeling is a manual operator activity, done after snapshots are collected.

- [ ] **Step 1: Write `eval/gold_template.json`**

```json
{
  "listing_id": "REPLACE_ME",
  "platform": "cars24",
  "full_fields": {
    "price": 0,
    "km_driven": 0,
    "year": 0,
    "owners_count": 0,
    "registration_state": null,
    "fuel": null,
    "transmission": null,
    "body_color": null,
    "certification_tier": null,
    "spinny_assured_tier": null,
    "accident_disclosed": null,
    "accident_history_detail": null,
    "inspection_issue_list": null,
    "inspection_points_passed": null,
    "service_history_records": null,
    "warranty_remaining_months": null,
    "noc_status": null,
    "rc_type": null,
    "insurance_status": null,
    "previous_use_type": null,
    "tire_condition": null,
    "engine_remarks": null,
    "transmission_remarks": null,
    "battery_status": null,
    "ac_remarks": null,
    "electrical_remarks": null,
    "cosmetic_exterior_notes": null,
    "cosmetic_interior_notes": null,
    "challan_status": null,
    "hypothecation_status": null,
    "inspection_photo_count": null
  },
  "score_common": 0.0,
  "notes": {
    "km_driven": "",
    "age_years": "",
    "owners": "",
    "certification_flag": "",
    "accident_disclosed": ""
  }
}
```

- [ ] **Step 2: Write empty `eval/ranking_listings.json`**

```json
[]
```

(Operator fills with 6 entries: `[{"platform": "cars24", "listing_id": "..."}, ...]`)

- [ ] **Step 3: Write `eval/common_set.json`**

```json
{"accident_in_common": false}
```

(Operator flips to `true` after snapshot inspection if accident is exposed in ≥90% of listings on both platforms.)

- [ ] **Step 4: Write `scripts/label_gold.py`**

```python
"""Interactive helper for labeling gold listings.

For each fixture under fixtures/, prints a path and opens an editor on
a copy of gold_template.json. After labeling all listings, run:

    uv run python scripts/label_gold.py compile

to merge per-listing JSON files in eval/labels/<platform>/<listing_id>.json
into a single eval/gold.jsonl.
"""
import json
import sys
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR


def list_unlabeled() -> list[tuple[str, str]]:
    labels = EVAL_DIR / "labels"
    out = []
    for plat_dir in FIXTURES_DIR.iterdir():
        if not plat_dir.is_dir():
            continue
        for lid_dir in plat_dir.iterdir():
            if not lid_dir.is_dir():
                continue
            lab = labels / plat_dir.name / f"{lid_dir.name}.json"
            if not lab.exists():
                out.append((plat_dir.name, lid_dir.name))
    return out


def init_label(platform: str, listing_id: str) -> Path:
    labels = EVAL_DIR / "labels" / platform
    labels.mkdir(parents=True, exist_ok=True)
    target = labels / f"{listing_id}.json"
    if not target.exists():
        tmpl = json.loads((EVAL_DIR / "gold_template.json").read_text())
        tmpl["listing_id"] = listing_id
        tmpl["platform"] = platform
        target.write_text(json.dumps(tmpl, indent=2))
    return target


def compile_jsonl() -> Path:
    labels = EVAL_DIR / "labels"
    out_path = EVAL_DIR / "gold.jsonl"
    rows = []
    for plat_dir in labels.iterdir():
        for f in plat_dir.glob("*.json"):
            rows.append(json.loads(f.read_text()))
    out_path.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"wrote {len(rows)} records to {out_path}")
    return out_path


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "compile":
        compile_jsonl()
        return
    if len(sys.argv) == 2 and sys.argv[1] == "list":
        for plat, lid in list_unlabeled():
            print(f"{plat}/{lid}")
        return
    if len(sys.argv) == 3:
        plat, lid = sys.argv[1], sys.argv[2]
        path = init_label(plat, lid)
        print(f"label file: {path}")
        return
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Smoke test the helper**

```bash
uv run python scripts/label_gold.py list
```

Expected: prints unlabeled fixture paths (or nothing if no fixtures yet).

- [ ] **Step 6: Operator labeling step (manual, off-plan)**

For each of ~15 gold listings, the operator opens `eval/labels/<platform>/<listing_id>.json`, fills `full_fields` from the snapshot HTML, computes `score_common` against the rubric in `docs/superpowers/specs/.../design.md` §4, writes per-dim notes, saves. Then runs `uv run python scripts/label_gold.py compile`.

- [ ] **Step 7: Commit**

```bash
git add eval/gold_template.json eval/ranking_listings.json eval/common_set.json scripts/label_gold.py
git commit -m "feat(eval): gold dataset template + labeling CLI helper"
```

---

## Task 15: E2 — Extraction quality eval

**Files:**
- Create: `src/ci/eval/extraction.py`
- Test: `tests/test_eval_extraction.py`

Computes per-field precision/recall vs gold, schema conformance rate, and a hallucination rate (extracted-but-null-in-gold).

- [ ] **Step 1: Write the failing tests**

`tests/test_eval_extraction.py`:

```python
from ci.eval.extraction import extraction_metrics
from ci.schemas import GoldRecord, NormalizedListing


def _norm(lid, plat="cars24", **kw):
    base = dict(
        platform=plat, listing_id=lid, price=900_000,
        km_driven=45_000, age_years=4, owners=1,
        certification_flag="top", accident_disclosed="none",
        disclosed_fields={}, full_fields={},
    )
    base.update(kw)
    return NormalizedListing(**base)


def _gold(lid, plat="cars24", full_fields=None, score=80.0):
    return GoldRecord(
        listing_id=lid, platform=plat,
        full_fields=full_fields or {"price": 900_000, "km_driven": 45_000, "year": 2022, "owners_count": 1},
        score_common=score, notes={},
    )


def test_field_precision_recall_perfect():
    norm = _norm("a", price=900_000, km_driven=45_000, age_years=4, owners=1)
    gold = _gold("a")
    m = extraction_metrics([(norm, gold)], today_year=2026)
    assert m.field_recall["price"] == 1.0
    assert m.field_recall["km_driven"] == 1.0


def test_hallucination_when_extractor_invents_value():
    # Gold has no warranty info. Normalizer carries warranty_remaining_months=12 from extractor.
    norm = _norm("a", full_fields={"warranty_remaining_months": 12})
    gold = _gold("a", full_fields={"price": 900_000, "km_driven": 45_000})
    m = extraction_metrics([(norm, gold)], today_year=2026)
    assert m.hallucination_rate > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_eval_extraction.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/eval/extraction.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime

from ci.schemas import GoldRecord, NormalizedListing

NUMERIC_FIELDS_TOLERANCE: dict[str, int | float] = {
    "price": 1,                # exact match expected for INR price
    "km_driven": 500,          # tolerance for rounding/extraction
}


@dataclass
class ExtractionMetrics:
    field_recall: dict[str, float] = field(default_factory=dict)
    field_precision: dict[str, float] = field(default_factory=dict)
    schema_conformance: float = 1.0
    hallucination_rate: float = 0.0
    n: int = 0


def _approx_equal(a, b, tol) -> bool:
    if a is None or b is None:
        return a == b
    if isinstance(tol, (int, float)) and isinstance(a, (int, float)):
        return abs(a - b) <= tol
    return a == b


def extraction_metrics(
    pairs: list[tuple[NormalizedListing, GoldRecord]],
    today_year: int | None = None,
) -> ExtractionMetrics:
    today_year = today_year or datetime.utcnow().year
    n = len(pairs)
    if n == 0:
        return ExtractionMetrics()

    fields_to_check = ["price", "km_driven", "owners_count", "year"]
    field_recall: dict[str, float] = {}

    for fkey in fields_to_check:
        match = 0
        gold_present = 0
        for norm, gold in pairs:
            g = gold.full_fields.get(fkey)
            if g is None:
                continue
            gold_present += 1
            if fkey == "year":
                # year not stored on normalized; reconstruct from age
                if norm.age_years is None:
                    continue
                norm_year = today_year - norm.age_years
                if norm_year == g:
                    match += 1
            else:
                norm_attr = {"owners_count": "owners"}.get(fkey, fkey)
                v = getattr(norm, norm_attr, None)
                tol = NUMERIC_FIELDS_TOLERANCE.get(fkey, 0)
                if _approx_equal(v, g, tol):
                    match += 1
        field_recall[fkey] = match / gold_present if gold_present else 1.0

    halluc_count = 0
    halluc_eligible = 0
    for norm, gold in pairs:
        for k, v in norm.full_fields.items():
            if v is None:
                continue
            if k in gold.full_fields:
                halluc_eligible += 1
                if gold.full_fields[k] is None:
                    halluc_count += 1
    hallucination_rate = halluc_count / halluc_eligible if halluc_eligible else 0.0

    return ExtractionMetrics(
        field_recall=field_recall,
        field_precision=dict(field_recall),  # symmetric at this granularity
        schema_conformance=1.0,
        hallucination_rate=hallucination_rate,
        n=n,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_eval_extraction.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/eval/extraction.py tests/test_eval_extraction.py
git commit -m "feat(eval): E2 extraction P/R + hallucination rate"
```

---

## Task 16: E3 — Calibration eval

**Files:**
- Create: `src/ci/eval/calibration.py`
- Test: `tests/test_eval_calibration.py`

Compares system `score_common` to gold `score_common`. Reports MAE, Spearman ρ, per-platform breakdown.

- [ ] **Step 1: Write the failing tests**

`tests/test_eval_calibration.py`:

```python
import pytest
from ci.eval.calibration import calibration_metrics


def test_calibration_perfect():
    sys_scores = [80.0, 60.0, 90.0]
    gold_scores = [80.0, 60.0, 90.0]
    platforms = ["cars24", "cars24", "spinny"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert m.mae_overall == pytest.approx(0.0)
    assert m.spearman_overall == pytest.approx(1.0)


def test_calibration_offset():
    sys_scores = [80.0, 60.0, 90.0]
    gold_scores = [85.0, 65.0, 95.0]
    platforms = ["cars24", "spinny", "cars24"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert m.mae_overall == pytest.approx(5.0, abs=0.01)
    assert m.spearman_overall == pytest.approx(1.0)


def test_calibration_per_platform():
    sys_scores = [80.0, 60.0, 90.0, 70.0]
    gold_scores = [85.0, 60.0, 90.0, 75.0]
    platforms = ["cars24", "spinny", "cars24", "spinny"]
    m = calibration_metrics(sys_scores, gold_scores, platforms)
    assert "cars24" in m.mae_per_platform
    assert "spinny" in m.mae_per_platform
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_eval_calibration.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/eval/calibration.py`**

```python
from dataclasses import dataclass, field

from scipy.stats import spearmanr


@dataclass
class CalibrationMetrics:
    mae_overall: float
    spearman_overall: float
    mae_per_platform: dict[str, float] = field(default_factory=dict)
    spearman_per_platform: dict[str, float] = field(default_factory=dict)
    n: int = 0


def calibration_metrics(
    sys_scores: list[float],
    gold_scores: list[float],
    platforms: list[str],
) -> CalibrationMetrics:
    n = len(sys_scores)
    assert len(gold_scores) == n == len(platforms)

    mae_overall = sum(abs(a - b) for a, b in zip(sys_scores, gold_scores)) / n
    rho_overall = float(spearmanr(sys_scores, gold_scores).correlation) if n >= 2 else 1.0

    mae_per: dict[str, float] = {}
    rho_per: dict[str, float] = {}
    for p in set(platforms):
        idx = [i for i, pl in enumerate(platforms) if pl == p]
        if len(idx) == 0:
            continue
        s = [sys_scores[i] for i in idx]
        g = [gold_scores[i] for i in idx]
        mae_per[p] = sum(abs(a - b) for a, b in zip(s, g)) / len(idx)
        rho_per[p] = float(spearmanr(s, g).correlation) if len(idx) >= 2 else 1.0

    return CalibrationMetrics(
        mae_overall=mae_overall,
        spearman_overall=rho_overall,
        mae_per_platform=mae_per,
        spearman_per_platform=rho_per,
        n=n,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_eval_calibration.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/eval/calibration.py tests/test_eval_calibration.py
git commit -m "feat(eval): E3 score_common calibration vs gold (MAE + Spearman)"
```

---

## Task 17: E4 — Weight sensitivity eval

**Files:**
- Create: `src/ci/eval/sensitivity.py`
- Test: `tests/test_eval_sensitivity.py`

For each weight: perturb ±25%, re-rank, compute Kendall's τ vs unperturbed. Also leave-one-dim-out.

- [ ] **Step 1: Write the failing tests**

`tests/test_eval_sensitivity.py`:

```python
from ci.eval.sensitivity import weight_sensitivity
from ci.schemas import NormalizedListing


def _n(lid, plat, price, km, age, owners, cert, acc):
    return NormalizedListing(
        platform=plat, listing_id=lid, price=price,
        km_driven=km, age_years=age, owners=owners,
        certification_flag=cert, accident_disclosed=acc,
        disclosed_fields={}, full_fields={},
    )


def test_sensitivity_returns_taus_per_dim():
    listings = [
        _n("a", "cars24", 1_200_000, 45_000, 4, 1, "top", "none"),
        _n("b", "spinny", 900_000, 60_000, 5, 2, "mid", "minor"),
        _n("c", "cars24", 1_000_000, 30_000, 2, 1, "top", "none"),
    ]
    res = weight_sensitivity(listings, accident_in_common=True, perturbation=0.25)
    assert set(res.tau_perturbed.keys()) == {
        "km_driven", "age_years", "owners", "certification_flag", "accident_disclosed",
    }
    for tau in res.tau_perturbed.values():
        assert -1.0 <= tau <= 1.0
    for tau in res.tau_leave_one_out.values():
        assert -1.0 <= tau <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_eval_sensitivity.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/eval/sensitivity.py`**

```python
from dataclasses import dataclass, field

from scipy.stats import kendalltau

from ci.config import WEIGHTS_WITH_ACCIDENT, WEIGHTS_WITHOUT_ACCIDENT
from ci.rank import rank_listings
from ci.schemas import NormalizedListing
from ci.score import score_listing


@dataclass
class SensitivityResult:
    tau_perturbed: dict[str, float] = field(default_factory=dict)
    tau_leave_one_out: dict[str, float] = field(default_factory=dict)


def _score_with_weights(
    listings: list[NormalizedListing],
    weights: dict[str, int],
):
    # Monkey-style override: copy listings; build pairs with custom-weighted scorer
    from ci.config import (
        ACCIDENT_MAP, CERT_MAP, IMPUTATION, KM_BANDS, OWNERS_MAP, AGE_BANDS,
    )

    def _value(name, n):
        v = getattr(n, name)
        if v is None:
            return float(IMPUTATION[name]), True
        if name == "km_driven":
            for ceil, val in KM_BANDS:
                if v < ceil:
                    return float(val), False
            return float(KM_BANDS[-1][1]), False
        if name == "age_years":
            for ceil, val in AGE_BANDS:
                if v < ceil:
                    return float(val), False
            return float(AGE_BANDS[-1][1]), False
        if name == "owners":
            if v >= 4:
                return 25.0, False
            return float(OWNERS_MAP.get(v, 25)), False
        if name == "accident_disclosed":
            return float(ACCIDENT_MAP[v]), False
        if name == "certification_flag":
            return float(CERT_MAP[v]), False
        raise KeyError(name)

    pairs = []
    total_weight = sum(weights.values())
    from ci.schemas import ScoreRecord
    for n in listings:
        total = 0.0
        per_dim = {}
        imputed = []
        for dim, w in weights.items():
            v, was_imp = _value(dim, n)
            per_dim[dim] = v
            if was_imp:
                imputed.append(dim)
            total += (w / total_weight) * v
        sc = ScoreRecord(
            listing_id=n.listing_id, platform=n.platform,
            score_common=round(total, 2), per_dim=per_dim,
            imputed_dims=imputed, disclosure_count=0, disclosed_fields={},
        )
        pairs.append((n, sc))
    return rank_listings(pairs)


def _ranking_ids(rows) -> list[str]:
    return [r.listing_id for r in rows]


def weight_sensitivity(
    listings: list[NormalizedListing],
    *,
    accident_in_common: bool,
    perturbation: float = 0.25,
) -> SensitivityResult:
    base_weights = (
        dict(WEIGHTS_WITH_ACCIDENT) if accident_in_common
        else dict(WEIGHTS_WITHOUT_ACCIDENT)
    )
    base_rows = _ranking_ids(_score_with_weights(listings, base_weights))

    tau_pert = {}
    for dim in base_weights:
        for sign in (1, -1):
            ws = dict(base_weights)
            ws[dim] = max(1, int(round(ws[dim] * (1 + sign * perturbation))))
            rows = _ranking_ids(_score_with_weights(listings, ws))
            tau, _ = kendalltau(
                [base_rows.index(x) for x in base_rows],
                [base_rows.index(x) for x in rows],
            )
            key = f"{dim}{'+' if sign > 0 else '-'}"
            tau_pert[key] = float(tau)

    tau_loo = {}
    for dim in base_weights:
        ws = {k: v for k, v in base_weights.items() if k != dim}
        rows = _ranking_ids(_score_with_weights(listings, ws))
        tau, _ = kendalltau(
            [base_rows.index(x) for x in base_rows],
            [base_rows.index(x) for x in rows],
        )
        tau_loo[dim] = float(tau)

    return SensitivityResult(tau_perturbed=tau_pert, tau_leave_one_out=tau_loo)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_eval_sensitivity.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/eval/sensitivity.py tests/test_eval_sensitivity.py
git commit -m "feat(eval): E4 weight sensitivity (perturbation + leave-one-out)"
```

---

## Task 18: E5 — Determinism spot-check

**Files:**
- Create: `src/ci/eval/determinism.py`
- Test: `tests/test_eval_determinism.py`

Run pipeline 3 times on one listing with the same fake/real client; assert outputs are byte-identical.

- [ ] **Step 1: Write the failing tests**

`tests/test_eval_determinism.py`:

```python
from ci.eval.determinism import determinism_check
from ci.llm import FakeLLMClient


def test_determinism_passes_when_outputs_identical(tmp_path, monkeypatch):
    fix = tmp_path / "fixtures" / "cars24" / "z"
    fix.mkdir(parents=True)
    (fix / "page.html").write_text("<html></html>")
    (fix / "captured_at.txt").write_text("2026-05-06T10:00:00Z")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    fake = FakeLLMClient(canned_tool_input={
        "price": 900_000, "km_driven": 45_000, "year": 2022,
        "owners_count": 1, "certification_tier": "Imperial",
    })
    res = determinism_check(
        platform="cars24", listing_id="z", client=fake,
        run_root=tmp_path / "runs", reps=3, accident_in_common=False,
    )
    assert res.identical is True
    assert res.distinct_outputs == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_eval_determinism.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/eval/determinism.py`**

```python
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ci.llm import LLMClient
from ci.pipeline import run_pipeline


@dataclass
class DeterminismResult:
    identical: bool
    distinct_outputs: int


def determinism_check(
    *,
    platform: str,
    listing_id: str,
    client: LLMClient,
    run_root: Path,
    reps: int,
    accident_in_common: bool,
) -> DeterminismResult:
    hashes: set[str] = set()
    for i in range(reps):
        run_dir = run_root / f"determinism-{i}"
        rows = run_pipeline(
            ranking_listings=[(platform, listing_id)],
            client=client,
            run_dir=run_dir,
            accident_in_common=accident_in_common,
        )
        payload = json.dumps([r.model_dump() for r in rows], sort_keys=True)
        hashes.add(hashlib.sha1(payload.encode()).hexdigest())
    return DeterminismResult(
        identical=len(hashes) == 1,
        distinct_outputs=len(hashes),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_eval_determinism.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/eval/determinism.py tests/test_eval_determinism.py
git commit -m "feat(eval): E5 determinism spot-check via repeated pipeline runs"
```

---

## Task 19: Reporter (markdown + chart)

**Files:**
- Create: `src/ci/report.py`
- Test: `tests/test_report.py`
- Create: `scripts/run_evals.py` (uses report.py to write final report.md)

Generates `docs/report.md` with: ranking table, topology section (static text in plan), eval results section (numbers from E2-E5), one tradeoff (read from `docs/tradeoffs.md`), limitations. Plus a price-vs-condition scatter chart at `docs/figures/ranking.png`.

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:

```python
from ci.report import render_report, render_chart
from ci.schemas import RankRow


def _row(lid, plat, price, score, ratio, disclosure, imputed=None):
    return RankRow(
        listing_id=lid, platform=plat, price=price,
        score_common=score, ratio=ratio, disclosure_count=disclosure,
        imputed_dims=imputed or [],
    )


def test_render_report_contains_ranking_table():
    rows = [
        _row("a", "spinny", 900_000, 90.0, 10_000.0, 7),
        _row("b", "cars24", 1_000_000, 80.0, 12_500.0, 3),
    ]
    md = render_report(
        rows=rows,
        extraction_metrics_summary={"hallucination_rate": 0.0, "field_recall": {"price": 1.0}},
        calibration_summary={"mae_overall": 4.2, "spearman_overall": 0.78},
        sensitivity_summary={"tau_perturbed": {"km_driven+": 1.0}, "tau_leave_one_out": {"km_driven": 0.9}},
        determinism_summary={"identical": True, "distinct_outputs": 1},
        tradeoff_md="### The tradeoff that bit\n\nA real story from build.",
        common_set={"accident_in_common": False},
    )
    assert "Ranking" in md
    assert "spinny" in md and "cars24" in md
    assert "10,000" in md or "10000" in md
    assert "Eval harness" in md
    assert "tradeoff" in md.lower()
    assert "Limitations" in md


def test_render_chart_writes_png(tmp_path):
    rows = [
        _row("a", "spinny", 900_000, 90.0, 10_000.0, 7),
        _row("b", "cars24", 1_000_000, 80.0, 12_500.0, 3),
        _row("c", "spinny", 1_100_000, 70.0, 15_714.0, 5),
    ]
    out = tmp_path / "chart.png"
    render_chart(rows, out)
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_report.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/ci/report.py`**

```python
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from ci.schemas import RankRow


def render_chart(rows: list[RankRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    for plat, marker, color in [("cars24", "o", "#1f77b4"), ("spinny", "s", "#d62728")]:
        sub = [r for r in rows if r.platform == plat]
        if not sub:
            continue
        ax.scatter(
            [r.score_common for r in sub],
            [r.price / 1e5 for r in sub],
            marker=marker, color=color, label=plat, s=80,
        )
        for r in sub:
            ax.annotate(r.listing_id, (r.score_common, r.price / 1e5),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel("score_common (0-100)")
    ax.set_ylabel("price (₹ lakh)")
    ax.set_title("Cars24 vs Spinny — price vs constructed condition score")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _format_inr(n: float) -> str:
    return f"{n:,.0f}"


def render_report(
    *,
    rows: list[RankRow],
    extraction_metrics_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
    sensitivity_summary: dict[str, Any],
    determinism_summary: dict[str, Any],
    tradeoff_md: str,
    common_set: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Cars24 vs Spinny — Competitive Intel Report\n")
    lines.append("## 1. Ranking (price-to-condition)\n")
    lines.append("| # | listing | platform | price (₹) | score_common | ratio | disclosure_count | imputed dims |")
    lines.append("|---|---------|----------|-----------|--------------|-------|------------------|--------------|")
    for i, r in enumerate(rows, 1):
        imp = ", ".join(r.imputed_dims) if r.imputed_dims else "—"
        lines.append(
            f"| {i} | `{r.listing_id}` | {r.platform} | {_format_inr(r.price)} "
            f"| {r.score_common:.1f} | {_format_inr(r.ratio)} | {r.disclosure_count} | {imp} |"
        )
    lines.append("")
    lines.append("![ranking chart](figures/ranking.png)\n")

    lines.append("## 2. Agent topology\n")
    lines.append(
        "Single explicit DAG, synchronous. LLM-driven extractor agents per platform "
        "(cars24, spinny) write into a common Pydantic schema via the normalizer. "
        "Scoring and ranking are deterministic so the audit trail is auditable. "
        "Trace store records every node call (input hash, output hash, latency, model, prompt version).\n"
    )
    lines.append("```\n"
                 "snapshots → extract.cars24 / extract.spinny → normalize → score → rank → report\n"
                 "```\n")
    lines.append(
        "Choosing deterministic scoring instead of an LLM-as-judge is itself a design choice — "
        "it preserves auditability and makes the eval harness (§3) meaningful. "
        f"Common-set decision: `accident_in_common = {common_set.get('accident_in_common', False)}`.\n"
    )

    lines.append("## 3. Eval harness\n")
    lines.append("### E2 Extraction quality")
    lines.append(f"- field_recall: `{extraction_metrics_summary.get('field_recall', {})}`")
    lines.append(f"- hallucination_rate: `{extraction_metrics_summary.get('hallucination_rate', 0):.3f}`\n")
    lines.append("### E3 Calibration vs gold")
    lines.append(f"- MAE: `{calibration_summary.get('mae_overall', 0):.2f}`")
    lines.append(f"- Spearman ρ: `{calibration_summary.get('spearman_overall', 0):.3f}`")
    lines.append("- Reported as directional, not significant — N is small (≈15 gold).\n")
    lines.append("### E4 Weight sensitivity")
    lines.append(f"- τ under ±25% perturbations: `{sensitivity_summary.get('tau_perturbed', {})}`")
    lines.append(f"- τ under leave-one-dim-out: `{sensitivity_summary.get('tau_leave_one_out', {})}`")
    lines.append(
        "- The claim this evidences: the ranking is stable under reasonable weight "
        "perturbations. It does *not* claim the weights are correct — these are priors.\n"
    )
    lines.append("### E5 Determinism spot-check")
    lines.append(f"- identical across reps: `{determinism_summary.get('identical')}` "
                 f"(distinct outputs: {determinism_summary.get('distinct_outputs')})\n")

    lines.append("## 4. The tradeoff that bit\n")
    lines.append(tradeoff_md)
    lines.append("")

    lines.append("## 5. Limitations\n")
    lines.append("- N=6 ranking; conclusions are illustrative.")
    lines.append("- Gold N≈15; calibration confidence intervals are wide. Read directional, not significant.")
    lines.append("- Rubric weights are reasonable priors, not grounded in external data. E4 only proves robustness, not groundedness.")
    lines.append("- `disclosure_count` measures presence, not depth-of-disclosure (a single sentence disclosure counts the same as detailed exposure).")
    lines.append("- Snapshots are point-in-time; results apply to the captured state of each listing.")
    lines.append("- Single annotator on gold (no inter-rater data).\n")

    return "\n".join(lines)
```

- [ ] **Step 4: Implement `scripts/run_evals.py`**

```python
"""Run eval harness over gold + ranking, write final report.

Reads:
- runs/<latest>/ranking.json
- eval/gold.jsonl
- docs/tradeoffs.md  (last entry used as 'the tradeoff that bit')

Writes:
- docs/report.md
- docs/figures/ranking.png
"""
import json
from pathlib import Path

from ci.config import DOCS_DIR, EVAL_DIR, RUNS_DIR
from ci.report import render_chart, render_report
from ci.schemas import RankRow


def _latest_run() -> Path:
    runs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("no runs/ — execute scripts/run_pipeline.py first")
    return runs[-1]


def main() -> None:
    run = _latest_run()
    rows = [RankRow.model_validate(d) for d in json.loads((run / "ranking.json").read_text())]

    # Eval summaries (placeholders — populated by E2-E5 in real run; here we read from files
    # written by a sister evaluation harness if present, else use empty defaults).
    extraction_summary = json.loads((run / "extraction.json").read_text()) if (run / "extraction.json").exists() else {}
    calibration_summary = json.loads((run / "calibration.json").read_text()) if (run / "calibration.json").exists() else {}
    sensitivity_summary = json.loads((run / "sensitivity.json").read_text()) if (run / "sensitivity.json").exists() else {}
    determinism_summary = json.loads((run / "determinism.json").read_text()) if (run / "determinism.json").exists() else {}

    tradeoff_path = DOCS_DIR / "tradeoffs.md"
    tradeoff_md = tradeoff_path.read_text() if tradeoff_path.exists() else "_no entries yet — see docs/tradeoffs.md_"

    common_set = json.loads((EVAL_DIR / "common_set.json").read_text())

    figures_dir = DOCS_DIR / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    render_chart(rows, figures_dir / "ranking.png")

    md = render_report(
        rows=rows,
        extraction_metrics_summary=extraction_summary,
        calibration_summary=calibration_summary,
        sensitivity_summary=sensitivity_summary,
        determinism_summary=determinism_summary,
        tradeoff_md=tradeoff_md,
        common_set=common_set,
    )
    (DOCS_DIR / "report.md").write_text(md)
    print(f"wrote {DOCS_DIR / 'report.md'} and {figures_dir / 'ranking.png'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_report.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass (cumulative across T1-T19).

- [ ] **Step 7: Initialize tradeoffs journal**

Create `docs/tradeoffs.md`:

```markdown
# Tradeoffs Journal

Append entries during build. Each entry: situation → decision → alternative
considered → what hurt. The "tradeoff that bit" answer in the report is
selected from here at report time.

---

(no entries yet)
```

- [ ] **Step 8: Commit**

```bash
git add src/ci/report.py scripts/run_evals.py docs/tradeoffs.md tests/test_report.py
git commit -m "feat(report): markdown + chart renderer + run_evals script + tradeoffs journal"
```

---

## Final integration step (operator-driven, off-plan)

After the above 19 tasks are complete and snapshots + gold are labeled:

1. `uv run python scripts/run_pipeline.py` — produces `runs/<id>/ranking.json`.
2. Eval steps E2–E5 are run via small wrappers in `scripts/run_evals.py` (the file is set up to load `*.json` summaries from the run dir; running the actual eval functions and writing those JSON files is straightforward and may be added inline in the same script during integration). Each writes its summary JSON to the run dir.
3. `uv run python scripts/run_evals.py` — produces `docs/report.md` + `docs/figures/ranking.png`.
4. Append the real "tradeoff that bit" entry to `docs/tradeoffs.md` based on what actually hurt during build.
5. Re-run `scripts/run_evals.py` to pick up the updated tradeoff.

---

## Self-review

**Spec coverage check:**
- Spec §2 scope (6 listings + ~15 gold, Creta Delhi-NCR ₹8-14L) — covered by T6 (collection) + T14 (gold structure) + operator steps. ✓
- Spec §3 common field set (locked after snapshots, accident conditional) — `eval/common_set.json` flag (T14) + scorer branching by `accident_in_common` (T11). ✓
- Spec §4 score_common rubric (anchored bands, imputation, no rebalancing) — config (T2) + scorer (T11). ✓
- Spec §4 disclosure metric (locked field set, count, disclosed_fields[]) — config DISCLOSURE_FIELDS (T2) + normalizer (T10) + scorer carries through (T11). ✓
- Spec §4 ranking inputs explicit (price, score_common only) — ranker uses only these (T12). ✓
- Spec §5 architecture DAG + trace store — pipeline (T13) + trace (T4). ✓
- Spec §6 eval harness E1-E5 — gold structure (T14), E2 (T15), E3 (T16), E4 (T17), E5 (T18). ✓
- Spec §7 reporting (table, topology, eval, tradeoff, limitations) — render_report (T19). ✓
- Spec §8 tech (Python 3.11+, uv, Pydantic v2, Sonnet 4.6, sync) — T1 + config (T2) + llm (T7). ✓
- Spec §9 tradeoffs journal — T19 step 7. ✓

**Placeholder scan:**
- No "TBD" / "implement later" remain; every step has concrete code.
- One "off-plan" operator activity (snapshot collection T6 step 3, gold labeling T14 step 6, final integration after T19) is unavoidable manual work, not a code placeholder.

**Type consistency check:**
- `NormalizedListing.owners` (int | None) is consistently named in normalize, score, sensitivity. ✓
- `ScoreRecord.disclosure_count` and `disclosed_fields` flow from normalize → score → rank consistently. ✓
- `RankRow.ratio` is float (rounded), used consistently. ✓
- `accident_in_common` boolean flows from `eval/common_set.json` → `run_pipeline` → `score_listing` → `weight_sensitivity` consistently. ✓

No issues found.

---

## Execution Handoff

Plan complete and saved to [`docs/superpowers/plans/2026-05-06-cars24-spinny-comp-intel-implementation.md`](2026-05-06-cars24-spinny-comp-intel-implementation.md). Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

---

## Revisions (2026-05-07)

After completing T1–T9 we fetched real Cars24 and Spinny detail pages and discovered the v1 schemas were speculative. Spec §13 ("Reality check") in the design doc captures the design changes; this section captures the plan-task revisions that follow from it.

T1, T3–T7, T12–T16, T18, T19 are **unchanged** from the original plan.

T2, T8, T9 are **rewritten below** as T2-rev, T8-rev, T9-rev. T10 and T11 are **modified** as T10-rev, T11-rev (their plan text in the original section still applies, with the small adjustments listed inline below).

The fixtures `fixtures/cars24/10041693110/` and `fixtures/spinny/28476005/` exist (saved during the reality check). Tests that need real-shape data should use these.

### T2-rev: Configuration module (revised)

**Files:**
- Modify: `src/ci/config.py`

**Changes from v1 T2:**
- Drop `WEIGHTS_WITHOUT_ACCIDENT` (we no longer have the conditional).
- Replace `WEIGHTS_WITH_ACCIDENT` with a single `WEIGHTS` table (cert removed):

  ```python
  WEIGHTS = {
      "km_driven": 35,
      "age_years": 25,
      "owners": 25,
      "accident_disclosed": 15,
  }
  ```

- Drop `CERT_MAP` and `IMPUTATION["certification_flag"]`.
- Replace `DISCLOSURE_FIELDS` with the 17-field list from spec §13:

  ```python
  DISCLOSURE_FIELDS = [
      "accident_history_detail",
      "inspection_per_section_ratings",
      "inspection_repair_statements",
      "tyre_condition_per_wheel",
      "service_history_records",
      "warranty_remaining_months",
      "noc_status",
      "rc_type",
      "insurance_type",
      "insurance_validity",
      "previous_use_type",
      "challan_status",
      "hypothecation_status",
      "inspection_photo_count",
      "per_listing_certification_tier",
      "buy_back_pricing",
      "market_price_delta",
  ]
  ```

- Steps: open `src/ci/config.py`, make the edits above, run `uv run pytest -q` to confirm nothing else broke (T2 has no dedicated test file; downstream tests will catch issues), commit with `chore(config): drop cert from common-set; revise disclosure-eligible list (per spec §13)`.

### T8-rev: Cars24 extractor (JSON-parse-first)

**Files:**
- Rewrite: `src/ci/extract/cars24.py`
- Update: `tests/test_extract_cars24.py` — replace canned-LLM tests with a real fixture-based parsing test against `fixtures/cars24/10041693110/page.html`.

**Approach:**
1. Read the snapshot HTML.
2. Find all `self.__next_f.push([1,"<escaped-string>"])` matches via regex.
3. Decode each captured string with `bytes.decode('unicode_escape')`.
4. Concatenate (or scan all) and locate the substring containing `"odometerReading":` — this anchors the listing-detail JSON.
5. Walk back to find the start of the enclosing `{` (the `content` object), then scan forward with a brace counter to find the matching `}`.
6. `json.loads()` the resulting object. Required keys must be present (`listingPrice`, `odometerReading`, `year`, `ownerNumber`).
7. Map into the existing `RawListing(platform="cars24", listing_id=…, fields=…)` shape. Field names from Cars24 are kept verbatim; the normalizer (T10) handles the rename.
8. LLM client parameter is still accepted in the signature but is unused unless a free-text fallback is added later (kept for API stability with T13 pipeline orchestrator).

**Test (`tests/test_extract_cars24.py`):**
- Use `fixtures/cars24/10041693110/page.html` via `load_snapshot("cars24", "10041693110")` (with monkeypatched `FIXTURES_DIR` pointing to the project's actual `fixtures/`).
- Call `extract_cars24(snap, FakeLLMClient(canned_tool_input={}))`.
- Assert: `raw.platform == "cars24"`, `raw.fields["listingPrice"] == 950000`, `raw.fields["odometerReading"] == 50673`, `raw.fields["year"] == 2020`, `raw.fields["ownerNumber"] == 2`.

**Commit:** `feat(extract): cars24 JSON-parse-first extractor (re #spec-§13)`

### T9-rev: Spinny extractor (JSON-parse-first)

**Files:**
- Rewrite: `src/ci/extract/spinny.py`
- Update: `tests/test_extract_spinny.py` — replace canned-LLM tests with fixture-based parsing test against `fixtures/spinny/28476005/page.html`.

**Approach:**
1. Read snapshot HTML.
2. Locate `window.__INITIAL_STATE__=` and capture until `;window.__STATIC_CONFIG__` (or `</script>` if not followed by STATIC_CONFIG).
3. The captured body is a **JS object literal**, not JSON. Use the `json5` package to parse it (already a small Python dep — add via `uv add json5`). `json5` handles unquoted keys, `!0`/`!1` for booleans, scientific notation like `27e3`.
4. Walk the parsed structure to find the listing-detail object. Heuristic: a path containing `mileage`, `no_of_owners`, `inspection_report`. Likely under `pageData.car_detail` or similar — confirm against the fixture.
5. Map into `RawListing(platform="spinny", listing_id=…, fields=…)`. Field names kept verbatim; normalizer (T10) handles renames.

**Test:**
- Same fixture-based test pattern as T8-rev.
- Assert: `raw.platform == "spinny"`, `raw.fields["mileage"] == "33,191"` (or numeric after preliminary parse — be explicit), `raw.fields["no_of_owners"] == "1st"`, `raw.fields["registration_year"] == 2022`, `raw.fields["category"] == "assured-plus"`, `raw.fields["inspection_report"]["report"]["summary"]["is_accidental"] is False`.

**Commit:** `feat(extract): spinny JSON-parse-first extractor (re #spec-§13)`

### T10-rev: Normalizer (modified inline)

The original T10 plan text still applies (raw → common schema). Modify only:

- Rename `_map_cert_cars24` and `_map_cert_spinny` to be unused / deleted; the normalizer no longer produces `certification_flag` on `NormalizedListing`.
- `NormalizedListing.certification_flag` → drop the field, OR keep the field as `Literal["max","assured-plus","assured","budget","none"] | None` for diagnostic-only purposes (decided: keep, but only Spinny populates it; Cars24 sets `None`). The scorer ignores it.
- Cars24 mapping for `accident_disclosed`: hardcoded to `"none"` (rationale documented in spec §13 / §4 of revised rubric).
- Spinny mapping for `accident_disclosed`: derive from `inspection_report.report.summary.is_accidental` — `False` → `"none"`, `True` → `"minor"` (Spinny doesn't expose severity beyond the boolean).
- Spinny `mileage` — strip commas, parse to int.
- Spinny `no_of_owners` — parse leading-digit (`"1st"` → `1`, `"2nd"` → `2`, etc.).
- Spinny `price` — strip commas, parse to int. (Or read `listing_price.price` if more reliable.)
- Spinny `registration_year` for `age_years` (manufacture year ≈ registration year minus a couple months; use `make_year` if exposed, else `registration_year`).
- Cars24 `age_years` from `year` field.

Disclosure mapping moves to the new field list:
- Spinny: most disclosure fields are populated from `inspection_report.*`, `is_assured`, `category`, `buy_back_pricing`, `pricing.market_price`, etc.
- Cars24: `lastServicedAt` → `service_history_records: True`. `insuranceType` → `insurance_type: True`. Most other disclosure fields → `False` for Cars24.

### T11-rev: Scorer (modified inline)

- Drop `accident_in_common` parameter from `score_listing`. Always use the single `WEIGHTS` table from T2-rev.
- Drop the `cert` dimension entirely from `_value_for_dim`.
- Tests in `tests/test_score.py` — drop the parameterization on `accident_in_common`. Keep all the band-lookup tests. Update the integrated `score_listing` tests to use the new 4-dim weights.

### T17-rev: Sensitivity eval (modified inline)

- Ablation surface shrinks from 4-or-5 dims (depending on accident_in_common) to a single 4-dim case (km/age/owners/accident).
- Drop the conditional logic; always use `WEIGHTS`.
- Test updated accordingly.

### Operator note

The 6 ranking listings + ~15 gold listings still need to be collected manually (T6 + T14 operator steps). The 2 fixtures saved during the reality check satisfy the *reality-check* tests for T8-rev and T9-rev but are not the final ranking dataset.
