# Plan B — Vision Agent Core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the vision agent end-to-end: photo capture, schemas, inner inspector, outer agent loop, vision-score aggregation, composite score, pipeline integration. Ships a `scripts/run_pipeline.py --vision-listings <subset>` invocation that produces `visual_score` and `composite_score` columns in the ranking output.

**Architecture:** Two distinct VLM calls per inspection (outer agent decides which photo, inner inspector inspects). Inner cached on `(prompt_version, photo_sha256)`. Async vision phase contained inside an otherwise-sync pipeline; `asyncio.run` wraps it. Set-relative rank computation grows from 6 listings to 16 (10 gold + 6 ranking). Composite blend `α × rule + (1-α) × visual` with α=0.7 default.

**Tech Stack:** Python 3.11+, anthropic SDK, httpx, pydantic, pytest. Model: `claude-sonnet-4-6`.

**Spec reference:** `docs/superpowers/specs/2026-05-07-vision-agent-design.md` §3-§11, §15.

**Locked listing IDs (from Plan A):**

```
Gold (calibration, 10):
  cars24:  10017390119, 10041693110, 10142868769, 10182490193, 44546195190
  spinny:  27723929, 27741490, 28240497, 28260532, 28564392

Ranking (held-out, 6):
  cars24:  10067090111, 10096166769, 10126364760
  spinny:  27839393, 28198885, 28476005

Pipeline runs over the union (16 listings).
```

---

## File structure

**New files:**

```
src/ci/vision/
  __init__.py
  photos.py        # extract_photo_urls_{cars24,spinny}, manifest read/write
  cache.py         # InnerCache: on-disk key/value
  inspector.py     # async inspect_photo (one-shot VLM)
  tools.py         # Anthropic tool schemas for outer agent
  agent.py         # async run_vision_agent (outer loop)
  score.py         # compute_vision_scores (rank-based, set-relative)
  composite.py     # compute_composite (alpha blend)

scripts/
  capture_photos.py            # download + write fixtures/<>/photos/
  build_vision_gold_template.py # write eval/vision_gold.jsonl skeleton
```

**Modified files:**

```
pyproject.toml        # +anthropic, +httpx
src/ci/schemas.py     # +Vision* models, extend ScoreRecord/RankRow/TraceEvent
src/ci/pipeline.py    # async vision phase, run on 16-listing union
src/ci/rank.py        # composite_score-aware ranking
src/ci/report.py      # new columns
scripts/run_pipeline.py # CLI flags, build 16-listing union
```

---

## Task 1: Add anthropic + httpx dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit pyproject.toml dependencies**

Open `pyproject.toml` and update the `dependencies` list:

```toml
dependencies = [
    "anthropic>=0.40.0",
    "httpx>=0.27.0",
    "json5>=0.14.0",
    "matplotlib>=3.10.9",
    "pydantic>=2.13.4",
    "scipy>=1.17.1",
]
```

- [ ] **Step 2: Sync deps**

Run: `uv sync`
Expected: anthropic and httpx are installed; no errors.

- [ ] **Step 3: Verify imports**

Run: `uv run python -c "import anthropic, httpx; print('OK')"`
Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add anthropic and httpx for vision agent"
```

---

## Task 2: Schema additions and extensions

**Files:**
- Modify: `src/ci/schemas.py`
- Modify: `tests/test_schemas.py`

- [ ] **Step 1: Read existing schemas and tests**

Read `src/ci/schemas.py` and `tests/test_schemas.py` to understand current shape (Platform, RawListing, NormalizedListing, ScoreRecord, RankRow, GoldRecord, TraceEvent).

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_schemas.py`:

```python
from ci.schemas import (
    Aspect,
    Severity,
    VisionFinding,
    VisionAssessment,
    VisionScore,
)


def test_vision_finding_validates_aspect_and_severity():
    f = VisionFinding(
        aspect="exterior_panels",
        severity="light_wear",
        confidence="med",
        photo_refs=[0, 3],
        evidence_note="minor scuff on rear bumper",
    )
    assert f.aspect == "exterior_panels"
    assert f.severity == "light_wear"


def test_vision_finding_rejects_unknown_aspect():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VisionFinding(
            aspect="undercarriage",  # not in taxonomy
            severity="light_wear",
            confidence="med",
            photo_refs=[],
            evidence_note="x",
        )


def test_vision_finding_caps_evidence_note_at_200_chars():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VisionFinding(
            aspect="tyres",
            severity="moderate",
            confidence="low",
            photo_refs=[],
            evidence_note="x" * 201,
        )


def test_vision_assessment_holds_findings_and_metadata():
    findings = [
        VisionFinding(aspect=a, severity="not_visible", confidence="low",
                      photo_refs=[], evidence_note="")
        for a in ("exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay")
    ]
    a = VisionAssessment(
        listing_id="X1", platform="cars24",
        findings=findings, photos_inspected=[0, 1],
        photo_count_total=10, agent_turns=4,
        budget_exceeded=False, notes=None,
    )
    assert len(a.findings) == 5
    assert a.photo_count_total == 10


def test_vision_score_holds_aggregated_per_aspect_scores():
    s = VisionScore(
        listing_id="X1", platform="spinny",
        visual_score=72.5,
        per_aspect_score={"exterior_panels": 80.0, "interior_cabin": 70.0,
                          "dashboard_console": 75.0, "tyres": 70.0, "engine_bay": 67.5},
        imputed_aspects=[],
        assessment=VisionAssessment(
            listing_id="X1", platform="spinny",
            findings=[
                VisionFinding(aspect=a, severity="moderate", confidence="med",
                              photo_refs=[0], evidence_note="x")
                for a in ("exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay")
            ],
            photos_inspected=[0], photo_count_total=5, agent_turns=3,
        ),
    )
    assert s.visual_score == 72.5
    assert "tyres" in s.per_aspect_score


def test_score_record_accepts_optional_visual_and_composite():
    from ci.schemas import ScoreRecord
    sr = ScoreRecord(
        listing_id="X1", platform="cars24",
        score_common=42.0,
        per_dim={"km_driven": 50.0, "age_years": 50.0,
                 "owners": 50.0, "accident_disclosed": 50.0},
        imputed_dims=[], disclosure_count=4, disclosed_fields={"a": True},
        visual_score=80.0, composite_score=53.4,
    )
    assert sr.visual_score == 80.0
    assert sr.composite_score == 53.4


def test_rank_row_carries_rule_visual_composite():
    from ci.schemas import RankRow
    r = RankRow(
        listing_id="X1", platform="cars24",
        price=500000, rule_score=42.0, visual_score=80.0,
        composite_score=53.4, ratio=9363.3,
        disclosure_count=4, imputed_dims=[], imputed_aspects=["engine_bay"],
    )
    assert r.composite_score == 53.4
    assert r.imputed_aspects == ["engine_bay"]


def test_trace_event_accepts_optional_agent_fields():
    from ci.schemas import TraceEvent
    e = TraceEvent(
        run_id="r1", node="vision.inspect_photo.cars24", timestamp="2026-05-07T12:00:00Z",
        input_hash="abc", output_hash="def", latency_ms=120,
        event_id="ev1", parent_event_id="ev0",
        tool="inspect_photo", tool_params_preview={"idx": 3},
        tool_result_preview={"aspects_visible": ["tyres"]},
    )
    assert e.tool == "inspect_photo"
    assert e.parent_event_id == "ev0"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: ImportError on the new symbols.

- [ ] **Step 4: Add the new + extended models to `src/ci/schemas.py`**

Append (and modify `ScoreRecord`/`RankRow`/`TraceEvent` in place):

```python
# --- Vision agent additions (spec §6, §9) ---

Aspect = Literal[
    "exterior_panels",
    "interior_cabin",
    "dashboard_console",
    "tyres",
    "engine_bay",
]
Severity = Literal[
    "pristine", "light_wear", "moderate", "heavy", "defect", "not_visible",
]


class VisionFinding(BaseModel):
    aspect: Aspect
    severity: Severity
    confidence: Literal["low", "med", "high"]
    photo_refs: list[int]
    evidence_note: str = Field(max_length=200)


class VisionAssessment(BaseModel):
    listing_id: str
    platform: Platform
    findings: list[VisionFinding]
    photos_inspected: list[int]
    photo_count_total: int
    agent_turns: int
    budget_exceeded: bool = False
    notes: str | None = None


class VisionScore(BaseModel):
    listing_id: str
    platform: Platform
    visual_score: float
    per_aspect_score: dict[Aspect, float]
    imputed_aspects: list[Aspect]
    assessment: VisionAssessment
```

Modify `ScoreRecord` to add optional fields (after the existing fields):

```python
class ScoreRecord(BaseModel):
    listing_id: str
    platform: Platform
    score_common: float
    per_dim: dict[str, float]
    imputed_dims: list[str]
    disclosure_count: int
    disclosed_fields: dict[str, bool]
    # vision additions (optional, default None)
    visual_score: float | None = None
    composite_score: float | None = None
```

Replace `RankRow` entirely with:

```python
class RankRow(BaseModel):
    listing_id: str
    platform: Platform
    price: int
    rule_score: float                          # was score_common; renamed for clarity
    visual_score: float | None = None
    composite_score: float | None = None
    ratio: float
    disclosure_count: int
    imputed_dims: list[str]
    imputed_aspects: list[str] = Field(default_factory=list)
```

Modify `TraceEvent` to add optional agent-trace fields:

```python
class TraceEvent(BaseModel):
    run_id: str
    node: str
    timestamp: str
    input_hash: str
    output_hash: str
    latency_ms: int
    # vision additions (optional, default None)
    event_id: str | None = None
    parent_event_id: str | None = None
    tool: str | None = None
    tool_params_preview: dict | None = None
    tool_result_preview: dict | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: all new tests pass; existing tests still pass.

- [ ] **Step 6: Run the full suite (callers of RankRow may need updating)**

Run: `uv run pytest -q`
Expected: regressions in `tests/test_rank.py` and `tests/test_report.py` because `RankRow` field `score_common` was renamed to `rule_score`.

Fix the regressions: in `src/ci/rank.py` and `src/ci/report.py`, find every `RankRow(score_common=...)` construction and change to `rule_score=...`. Find every `r.score_common` read on a RankRow and change to `r.rule_score`. Update the corresponding tests in `tests/test_rank.py` and `tests/test_report.py` to match.

Run: `uv run pytest -q` again. Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/ci/schemas.py src/ci/rank.py src/ci/report.py tests/
git commit -m "feat(schemas): add vision models, extend ScoreRecord/RankRow/TraceEvent"
```

---

## Task 3: Photo URL extractors per platform

**Files:**
- Create: `src/ci/vision/__init__.py` (empty)
- Create: `src/ci/vision/photos.py`
- Create: `tests/test_vision_photos.py`

- [ ] **Step 1: Create the vision package**

```bash
mkdir -p src/ci/vision
touch src/ci/vision/__init__.py
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_vision_photos.py
"""URL extraction from per-platform raw fields."""
from ci.vision.photos import (
    extract_photo_urls_cars24,
    extract_photo_urls_spinny,
)


def test_extract_cars24_walks_media_gallery_categories():
    fields = {
        "media": {
            "gallery": {
                "Exterior": [
                    {"image": "https://media.cars24.com/hello-ar/a.jpg",
                     "label": "Front"},
                    {"image": "https://media.cars24.com/hello-ar/b.jpg",
                     "label": "Side"},
                ],
                "Interior": [
                    {"image": "https://media.cars24.com/hello-ar/c.jpg",
                     "label": "Dashboard"},
                ],
                "Tyres": [],  # empty list OK
            }
        }
    }
    urls = extract_photo_urls_cars24(fields)
    assert len(urls) == 3
    assert all("url" in u and "hint" in u for u in urls)
    assert urls[0]["hint"] == "Exterior"
    assert urls[2]["hint"] == "Interior"


def test_extract_cars24_dedupes_within_categories():
    fields = {
        "media": {
            "gallery": {
                "Exterior": [
                    {"image": "https://media.cars24.com/hello-ar/a.jpg"},
                    {"image": "https://media.cars24.com/hello-ar/a.jpg"},  # dup
                ],
            }
        }
    }
    urls = extract_photo_urls_cars24(fields)
    assert len(urls) == 1


def test_extract_cars24_handles_missing_gallery():
    assert extract_photo_urls_cars24({}) == []
    assert extract_photo_urls_cars24({"media": {}}) == []


def test_extract_spinny_prefers_galleryV3():
    fields = {
        "galleryV3": [
            {"url": "https://spn-mda.spinny.com/img/a/raw/file.jpg",
             "section": "exterior"},
            {"url": "https://spn-mda.spinny.com/img/b/raw/file.jpg",
             "section": "interior"},
        ],
        "product_photos": [
            {"url": "https://spn-mda.spinny.com/img/Z/raw/file.jpg"},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 2  # galleryV3 wins
    assert urls[0]["hint"] == "exterior"


def test_extract_spinny_falls_back_to_product_photos():
    fields = {
        "product_photos": [
            {"url": "https://spn-mda.spinny.com/img/x/raw/file.jpg"},
            {"url": "https://spn-mda.spinny.com/img/y/raw/file.jpg"},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 2
    assert urls[0]["hint"] is None


def test_extract_spinny_handles_missing_both():
    assert extract_photo_urls_spinny({}) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_vision_photos.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

```python
# src/ci/vision/photos.py
"""Per-platform photo URL extraction from raw listing fields.

Each function takes the platform's `RawListing.fields` dict and returns a list
of `{"url": str, "hint": str | None}` dicts representing distinct listing
photos. Hints are platform-specific category labels useful for the agent.
"""
from __future__ import annotations

from typing import Any


def extract_photo_urls_cars24(fields: dict[str, Any]) -> list[dict]:
    """Walk media.gallery.{Highlights, Exterior, Interior, Tyres, Features, ...}.

    Each gallery entry is a dict with at least an `image` URL. We use the
    category name as the `hint`. Within each category, dedupe by URL string.
    """
    out: list[dict] = []
    seen: set[str] = set()
    gallery = (fields.get("media") or {}).get("gallery") or {}
    for category, entries in gallery.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("image")
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "hint": category})
    return out


def extract_photo_urls_spinny(fields: dict[str, Any]) -> list[dict]:
    """Prefer `galleryV3` (richer + sectioned); fall back to `product_photos`.

    galleryV3 entries have a `url` and an optional `section` label; product_photos
    have only a `url`.
    """
    g3 = fields.get("galleryV3")
    if isinstance(g3, list) and g3:
        out: list[dict] = []
        seen: set[str] = set()
        for entry in g3:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "hint": entry.get("section")})
        return out

    pp = fields.get("product_photos")
    if isinstance(pp, list):
        out2: list[dict] = []
        seen2: set[str] = set()
        for entry in pp:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not isinstance(url, str) or not url or url in seen2:
                continue
            seen2.add(url)
            out2.append({"url": url, "hint": None})
        return out2

    return []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_vision_photos.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/ci/vision/__init__.py src/ci/vision/photos.py tests/test_vision_photos.py
git commit -m "feat(vision): per-platform photo URL extractors"
```

---

## Task 4: Photo capture script + manifest

**Files:**
- Create: `src/ci/vision/manifest.py`
- Create: `scripts/capture_photos.py`
- Create: `tests/test_vision_manifest.py`
- Create: `tests/test_capture_photos.py`

- [ ] **Step 1: Write failing tests for manifest**

```python
# tests/test_vision_manifest.py
"""Read/write helpers for fixtures/<platform>/<lid>/photos.json."""
import json
from pathlib import Path

from ci.vision.manifest import read_manifest, write_manifest


def test_round_trip(tmp_path: Path):
    p = tmp_path / "photos.json"
    data = {
        "captured_at": "2026-05-07T00:00:00Z",
        "photos": [
            {"idx": 0, "sha256": "ab12", "source_url": "https://x/a.jpg", "hint": "Exterior"},
            {"idx": 1, "sha256": "cd34", "source_url": "https://x/b.jpg", "hint": None},
        ],
    }
    write_manifest(p, data)
    assert read_manifest(p) == data


def test_read_missing_returns_none(tmp_path: Path):
    assert read_manifest(tmp_path / "nope.json") is None
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_vision_manifest.py -v`

- [ ] **Step 3: Implement manifest**

```python
# src/ci/vision/manifest.py
"""Read/write fixtures/<platform>/<lid>/photos.json manifest."""
from __future__ import annotations

import json
from pathlib import Path


def read_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_vision_manifest.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write failing tests for capture (mocking httpx)**

```python
# tests/test_capture_photos.py
"""Tests for the photo capture script (mocked httpx)."""
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.capture_photos import capture_for_listing


@pytest.fixture
def fake_fixture_dir(tmp_path: Path):
    d = tmp_path / "cars24" / "TESTLID"
    d.mkdir(parents=True)
    (d / "page.html").write_text("<html>x</html>")
    (d / "captured_at.txt").write_text("2026-05-07T00:00:00Z")
    return d


@pytest.mark.asyncio
async def test_capture_dedupes_by_content_hash(fake_fixture_dir: Path):
    """Two URLs returning identical bytes should produce one photo file."""
    same_bytes = b"jpegbytes-A"
    extracted = [
        {"url": "https://x/a.jpg", "hint": "Exterior"},
        {"url": "https://x/b.jpg", "hint": "Interior"},  # diff URL, same bytes
    ]

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = same_bytes
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.aclose = AsyncMock()

    with patch("scripts.capture_photos.httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        await capture_for_listing(
            platform="cars24",
            listing_id="TESTLID",
            extracted_urls=extracted,
            fixture_root=fake_fixture_dir.parent.parent,
        )

    photos_dir = fake_fixture_dir / "photos"
    files = list(photos_dir.glob("*.jpg"))
    assert len(files) == 1  # dedup by content hash

    manifest = json.loads((fake_fixture_dir / "photos.json").read_text())
    assert len(manifest["photos"]) == 2  # both URLs recorded
    assert manifest["photos"][0]["sha256"] == manifest["photos"][1]["sha256"]
    expected_sha = hashlib.sha256(same_bytes).hexdigest()
    assert manifest["photos"][0]["sha256"] == expected_sha


@pytest.mark.asyncio
async def test_capture_writes_distinct_files_for_distinct_bytes(fake_fixture_dir: Path):
    """Different bytes per URL → distinct files."""
    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"unique-" + url.encode()
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    extracted = [
        {"url": "https://x/a.jpg", "hint": "Exterior"},
        {"url": "https://x/b.jpg", "hint": "Interior"},
    ]
    with patch("scripts.capture_photos.httpx.AsyncClient", return_value=mock_client):
        await capture_for_listing(
            platform="cars24",
            listing_id="TESTLID",
            extracted_urls=extracted,
            fixture_root=fake_fixture_dir.parent.parent,
        )

    files = list((fake_fixture_dir / "photos").glob("*.jpg"))
    assert len(files) == 2
```

Add `pytest-asyncio` to dev deps in pyproject.toml:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-cov>=7.1.0",
    "pytest-asyncio>=1.2.0",
]
```

Add to `[tool.pytest.ini_options]`:

```toml
asyncio_mode = "auto"
```

Run: `uv sync`.

- [ ] **Step 6: Run failing**

Run: `uv run pytest tests/test_capture_photos.py -v`
Expected: ImportError on `scripts.capture_photos`.

- [ ] **Step 7: Implement capture script**

```python
# scripts/capture_photos.py
"""Download listing photos to fixtures/<platform>/<listing_id>/photos/<sha>.jpg.

Per spec §4. Idempotent — re-running skips already-on-disk hashes. Writes a
photos.json manifest alongside.

Usage:
  uv run python -m scripts.capture_photos cars24 10182490193
  uv run python -m scripts.capture_photos --all  # all 16 active fixtures
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ci.config import EVAL_DIR, FIXTURES_DIR
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.snapshot import load_snapshot
from ci.vision.manifest import write_manifest
from ci.vision.photos import extract_photo_urls_cars24, extract_photo_urls_spinny


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    return resp.content


async def capture_for_listing(
    *,
    platform: str,
    listing_id: str,
    extracted_urls: list[dict],
    fixture_root: Path,
) -> dict:
    """Download all extracted_urls' bytes, dedupe by sha256, write photos/ + photos.json."""
    listing_dir = fixture_root / platform / listing_id
    photos_dir = listing_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient() as client:
        tasks = [_download(client, e["url"]) for e in extracted_urls]
        all_bytes = await asyncio.gather(*tasks, return_exceptions=True)

    photos_meta: list[dict] = []
    for idx, (entry, body) in enumerate(zip(extracted_urls, all_bytes)):
        if isinstance(body, Exception):
            print(f"  WARN: skipping {entry['url']}: {body}")
            continue
        sha = hashlib.sha256(body).hexdigest()
        out_path = photos_dir / f"{sha}.jpg"
        if not out_path.exists():
            out_path.write_bytes(body)
        photos_meta.append({
            "idx": idx,
            "sha256": sha,
            "source_url": entry["url"],
            "hint": entry.get("hint"),
        })

    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "photos": photos_meta,
    }
    write_manifest(listing_dir / "photos.json", manifest)
    return manifest


def _active_listings() -> list[tuple[str, str]]:
    """Union of gold (10) + ranking (6) = 16 active fixtures."""
    gold = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    return [(g["platform"], g["listing_id"]) for g in gold] + \
           [(r["platform"], r["listing_id"]) for r in ranking]


async def _main_async(args: argparse.Namespace) -> None:
    if args.all:
        targets = _active_listings()
    else:
        targets = [(args.platform, args.listing_id)]

    for platform, lid in targets:
        print(f"--- {platform}/{lid} ---")
        snap = load_snapshot(platform, lid)
        if platform == "cars24":
            raw = extract_cars24(snap)
            urls = extract_photo_urls_cars24(raw.fields)
        elif platform == "spinny":
            raw = extract_spinny(snap)
            urls = extract_photo_urls_spinny(raw.fields)
        else:
            raise ValueError(f"unknown platform: {platform}")

        if not urls:
            print(f"  no photo URLs extracted; skipping")
            continue

        manifest = await capture_for_listing(
            platform=platform, listing_id=lid,
            extracted_urls=urls, fixture_root=FIXTURES_DIR,
        )
        print(f"  {len(manifest['photos'])} photos, "
              f"{len(set(p['sha256'] for p in manifest['photos']))} unique")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("platform", nargs="?", choices=["cars24", "spinny"])
    p.add_argument("listing_id", nargs="?")
    p.add_argument("--all", action="store_true",
                   help="capture for all 16 active fixtures (10 gold + 6 ranking)")
    args = p.parse_args()
    if not args.all and (not args.platform or not args.listing_id):
        p.error("specify <platform> <listing_id> or --all")
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Tests pass**

Run: `uv run pytest tests/test_capture_photos.py tests/test_vision_manifest.py -v`
Expected: all pass.

- [ ] **Step 9: Add fixtures/**/photos/* to .gitignore**

Append to `.gitignore`:
```
fixtures/**/photos/
```

- [ ] **Step 10: Commit**

```bash
git add src/ci/vision/manifest.py scripts/capture_photos.py tests/test_capture_photos.py tests/test_vision_manifest.py pyproject.toml uv.lock .gitignore
git commit -m "feat(vision): photo capture script with content-hash dedup + manifest"
```

---

## Task 5: Run capture for the 16 active fixtures (data step)

**Files:**
- Output: `fixtures/<platform>/<listing_id>/photos/*.jpg` and `photos.json` for 16 listings

**Note:** This is a one-time data collection step. Hits CDN. Estimate ~138 MB across 16 listings.

- [ ] **Step 1: Run for all 16**

Run: `uv run python -m scripts.capture_photos --all`
Expected: 16 lines like `<platform>/<lid>: <N> photos, <K> unique`. No fatal errors. CDN downloads happen in parallel within each listing.

- [ ] **Step 2: Verify photo presence**

Run:
```bash
uv run python -c "
import json
from pathlib import Path
from ci.config import EVAL_DIR, FIXTURES_DIR
gold = [json.loads(l) for l in (EVAL_DIR / 'gold.jsonl').read_text().splitlines() if l.strip()]
ranking = json.loads((EVAL_DIR / 'ranking_listings.json').read_text())
all_listings = [(g['platform'], g['listing_id']) for g in gold] + \
               [(r['platform'], r['listing_id']) for r in ranking]
for plat, lid in all_listings:
    manifest = FIXTURES_DIR / plat / lid / 'photos.json'
    photos_dir = FIXTURES_DIR / plat / lid / 'photos'
    n_manifest = len(json.loads(manifest.read_text())['photos'])
    n_files = len(list(photos_dir.glob('*.jpg')))
    print(f'{plat}/{lid}: manifest={n_manifest} files={n_files}')
    assert n_manifest > 0, f'{plat}/{lid} has zero photos'
print('OK')
"
```

Expected: each listing reports N>0; prints `OK`. Cars24 typically ~10-50, Spinny ~50-60.

- [ ] **Step 3: Disk-usage sanity check**

Run: `du -sh fixtures/*/`
Expected: total under 500 MB (likely ~150-300 MB).

- [ ] **No commit needed** — `fixtures/**/photos/` is gitignored.

---

## Task 6: Inner inspector cache

**Files:**
- Create: `src/ci/vision/cache.py`
- Create: `tests/test_vision_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vision_cache.py
"""On-disk cache for inner inspector results."""
import json
from pathlib import Path

from ci.vision.cache import InnerCache


def test_get_returns_none_on_miss(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1")
    assert c.get(photo_sha="abc") is None


def test_set_then_get_round_trips(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1")
    payload = {"aspects_visible": ["tyres"], "findings": {"tyres": {"severity": "moderate"}}}
    c.set(photo_sha="abc", value=payload)
    assert c.get(photo_sha="abc") == payload


def test_different_prompt_versions_dont_collide(tmp_path: Path):
    c1 = InnerCache(root=tmp_path, prompt_version="v1")
    c2 = InnerCache(root=tmp_path, prompt_version="v2")
    c1.set(photo_sha="abc", value={"x": 1})
    c2.set(photo_sha="abc", value={"x": 2})
    assert c1.get(photo_sha="abc") == {"x": 1}
    assert c2.get(photo_sha="abc") == {"x": 2}


def test_bypass_mode_always_misses_and_does_not_write(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1", bypass=True)
    c.set(photo_sha="abc", value={"x": 1})
    assert c.get(photo_sha="abc") is None
    # confirm no files written
    assert not list(tmp_path.glob("*.json"))
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_vision_cache.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/ci/vision/cache.py
"""On-disk cache for inner inspector results.

Key = sha256(prompt_version + photo_sha256). Value = inspector findings JSON.
Bypass mode disables both reads and writes (used by E5 cold-cache runs).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


class InnerCache:
    def __init__(self, *, root: Path, prompt_version: str, bypass: bool = False):
        self.root = Path(root)
        self.prompt_version = prompt_version
        self.bypass = bypass
        if not bypass:
            self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, *, photo_sha: str) -> str:
        h = hashlib.sha256()
        h.update(self.prompt_version.encode())
        h.update(b":")
        h.update(photo_sha.encode())
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, *, photo_sha: str) -> dict | None:
        if self.bypass:
            return None
        p = self._path(self._key(photo_sha=photo_sha))
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def set(self, *, photo_sha: str, value: dict) -> None:
        if self.bypass:
            return
        p = self._path(self._key(photo_sha=photo_sha))
        # atomic write: tempfile + rename
        fd, tmp = tempfile.mkstemp(dir=str(self.root), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(value, f)
            os.replace(tmp, p)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_vision_cache.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/vision/cache.py tests/test_vision_cache.py
git commit -m "feat(vision): on-disk cache for inner inspector keyed by prompt_version+photo_sha"
```

---

## Task 7: Inner inspector (one-shot VLM call)

**Files:**
- Create: `src/ci/vision/inspector.py`
- Create: `tests/test_vision_inspector.py`

- [ ] **Step 1: Write failing tests (mock client)**

```python
# tests/test_vision_inspector.py
"""Inner inspector: one-shot VLM call for a single photo."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ci.vision.cache import InnerCache
from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION


def _mock_client_returning(payload: dict) -> MagicMock:
    """Construct a mock anthropic AsyncAnthropic that returns a single text block."""
    client = MagicMock()
    response = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response.content = [block]
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def fake_photo(tmp_path: Path) -> Path:
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake jpeg bytes")
    return p


async def test_inspect_photo_returns_parsed_findings(fake_photo: Path, tmp_path: Path):
    payload = {
        "aspects_visible": ["exterior_panels"],
        "findings": {
            "exterior_panels": {"severity": "light_wear", "evidence_note": "scuff"}
        },
    }
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache", prompt_version=INSPECTOR_PROMPT_VERSION)
    result = await inspect_photo(
        photo_path=fake_photo, photo_sha="abc",
        client=client, cache=cache,
    )
    assert result == payload
    client.messages.create.assert_awaited_once()


async def test_inspect_photo_uses_cache_on_second_call(fake_photo: Path, tmp_path: Path):
    payload = {"aspects_visible": [], "findings": {}}
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache", prompt_version=INSPECTOR_PROMPT_VERSION)

    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    assert client.messages.create.await_count == 1  # second call hit cache


async def test_inspect_photo_skips_cache_in_bypass_mode(fake_photo: Path, tmp_path: Path):
    payload = {"aspects_visible": [], "findings": {}}
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache",
                       prompt_version=INSPECTOR_PROMPT_VERSION, bypass=True)

    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    assert client.messages.create.await_count == 2  # both calls hit the API
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_vision_inspector.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/ci/vision/inspector.py
"""Inner inspector: one-shot VLM call examining a single photo for all aspects.

Returns a structured findings JSON. Cached on (prompt_version, photo_sha256).
The outer agent uses this as a tool implementation.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ci.vision.cache import InnerCache

INSPECTOR_PROMPT_VERSION = "v1"
INSPECTOR_MODEL = "claude-sonnet-4-6"

INSPECTOR_SYSTEM_PROMPT = """\
You inspect a single photo of a used car and classify visible-aspect severity.

For each visible aspect from this list:
  - exterior_panels (paint, dents, scratches)
  - interior_cabin (seats, plastics, headliner wear)
  - dashboard_console (steering, screen, controls)
  - tyres (tread, sidewall)
  - engine_bay

classify severity as one of:
  - pristine
  - light_wear
  - moderate
  - heavy
  - defect

Aspects that are NOT visible in this photo MUST NOT appear in `findings`.
Be conservative: if uncertain, omit the aspect rather than guess.

Return strict JSON matching:
  {
    "aspects_visible": [<aspect-name>, ...],
    "findings": {
      <aspect-name>: {"severity": <severity>, "evidence_note": <≤200 char string>}
    }
  }
"""


async def inspect_photo(
    *,
    photo_path: Path,
    photo_sha: str,
    client: Any,
    cache: InnerCache,
) -> dict:
    """Single-photo VLM call. Returns the model's structured findings dict."""
    cached = cache.get(photo_sha=photo_sha)
    if cached is not None:
        return cached

    img_bytes = photo_path.read_bytes()
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    response = await client.messages.create(
        model=INSPECTOR_MODEL,
        max_tokens=1024,
        system=INSPECTOR_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64,
                    },
                },
                {
                    "type": "text",
                    "text": "Inspect this photo. Return strict JSON per the schema.",
                },
            ],
        }],
    )

    # Extract text from first text block
    text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
    if not text_blocks:
        raise ValueError("inspector: no text block in response")
    raw = text_blocks[0].text
    # Tolerate code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    parsed = json.loads(raw)
    cache.set(photo_sha=photo_sha, value=parsed)
    return parsed
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_vision_inspector.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/vision/inspector.py tests/test_vision_inspector.py
git commit -m "feat(vision): inner inspector with content-hash cache"
```

---

## Task 8: Outer agent (tools + loop)

**Files:**
- Create: `src/ci/vision/tools.py`
- Create: `src/ci/vision/agent.py`
- Create: `tests/test_vision_agent.py`

- [ ] **Step 1: Write tool definitions**

```python
# src/ci/vision/tools.py
"""Anthropic tool definitions for the outer vision agent."""

LIST_PHOTOS_TOOL = {
    "name": "list_photos",
    "description": "List all photos available for the current listing.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

INSPECT_PHOTO_TOOL = {
    "name": "inspect_photo",
    "description": (
        "Inspect a specific photo by index. Returns aspects_visible and per-aspect "
        "findings. Use this to gather evidence before final_assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "idx": {"type": "integer", "description": "Photo index from list_photos."},
        },
        "required": ["idx"],
    },
}

NOTE_EVIDENCE_GAP_TOOL = {
    "name": "note_evidence_gap",
    "description": (
        "Record that you looked but cannot evidence this aspect (e.g. no photo "
        "shows the engine bay). Use ONLY when no available photo evidences the aspect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "aspect": {
                "type": "string",
                "enum": ["exterior_panels", "interior_cabin",
                         "dashboard_console", "tyres", "engine_bay"],
            },
            "reason": {"type": "string"},
        },
        "required": ["aspect", "reason"],
    },
}

FINAL_ASSESSMENT_TOOL = {
    "name": "final_assessment",
    "description": (
        "Submit your final per-aspect assessment. This terminates the loop. "
        "Include all 5 aspects; use 'not_visible' severity for any aspect with no evidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "per_aspect": {
                "type": "object",
                "properties": {
                    a: {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["pristine", "light_wear", "moderate",
                                         "heavy", "defect", "not_visible"],
                            },
                            "confidence": {
                                "type": "string", "enum": ["low", "med", "high"],
                            },
                            "photo_refs": {
                                "type": "array", "items": {"type": "integer"},
                            },
                            "evidence_note": {"type": "string", "maxLength": 200},
                        },
                        "required": ["severity", "confidence", "photo_refs", "evidence_note"],
                    }
                    for a in ("exterior_panels", "interior_cabin",
                              "dashboard_console", "tyres", "engine_bay")
                },
                "required": ["exterior_panels", "interior_cabin",
                             "dashboard_console", "tyres", "engine_bay"],
            }
        },
        "required": ["per_aspect"],
    },
}

ALL_TOOLS = [LIST_PHOTOS_TOOL, INSPECT_PHOTO_TOOL,
             NOTE_EVIDENCE_GAP_TOOL, FINAL_ASSESSMENT_TOOL]
```

- [ ] **Step 2: Write failing tests for the agent loop**

```python
# tests/test_vision_agent.py
"""Outer agent loop with mocked client + inspector."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ci.vision.agent import run_vision_agent


def _tool_use_block(tool_name: str, tool_input: dict, tool_use_id: str = "tu1"):
    b = MagicMock()
    b.type = "tool_use"
    b.name = tool_name
    b.input = tool_input
    b.id = tool_use_id
    return b


def _text_block(text: str):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _make_client(scripted_responses: list[list]):
    """Build a mock client that returns scripted content blocks per call."""
    client = MagicMock()
    responses = []
    for blocks in scripted_responses:
        r = MagicMock()
        r.content = blocks
        # stop_reason is "tool_use" if last block is tool_use, else "end_turn"
        r.stop_reason = "tool_use" if blocks and blocks[-1].type == "tool_use" else "end_turn"
        responses.append(r)
    client.messages = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


_FINAL_PAYLOAD = {
    "per_aspect": {
        a: {"severity": "not_visible", "confidence": "low",
            "photo_refs": [], "evidence_note": ""}
        for a in ("exterior_panels", "interior_cabin",
                  "dashboard_console", "tyres", "engine_bay")
    }
}


@pytest.fixture
def fake_manifest():
    return {
        "captured_at": "2026-05-07T00:00:00Z",
        "photos": [
            {"idx": 0, "sha256": "aaa", "source_url": "https://x/a.jpg", "hint": "Exterior"},
            {"idx": 1, "sha256": "bbb", "source_url": "https://x/b.jpg", "hint": "Interior"},
        ],
    }


async def test_agent_calls_list_then_final(fake_manifest):
    client = _make_client([
        [_tool_use_block("list_photos", {})],
        [_tool_use_block("final_assessment", _FINAL_PAYLOAD)],
    ])

    async def noop_inspect(idx):
        return {"aspects_visible": [], "findings": {}}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=noop_inspect,
    )
    assert len(assessment.findings) == 5
    assert assessment.agent_turns == 2
    assert assessment.budget_exceeded is False


async def test_agent_invokes_inspector_when_inspect_photo_called(fake_manifest):
    findings_for_idx_0 = {
        "aspects_visible": ["exterior_panels"],
        "findings": {"exterior_panels": {"severity": "light_wear", "evidence_note": "scuff"}},
    }
    client = _make_client([
        [_tool_use_block("inspect_photo", {"idx": 0})],
        [_tool_use_block("final_assessment", _FINAL_PAYLOAD)],
    ])

    inspector = AsyncMock(return_value=findings_for_idx_0)

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
    )
    inspector.assert_awaited_once_with(0)
    assert 0 in assessment.photos_inspected


async def test_agent_force_finalizes_on_inspect_budget_exceeded(fake_manifest):
    """If max_inspects=2 is hit, agent is forced to finalize."""
    client = _make_client([
        [_tool_use_block("inspect_photo", {"idx": 0})],
        [_tool_use_block("inspect_photo", {"idx": 1})],
        # no third tool call — this would be the 3rd inspect, blocked by budget
        [_tool_use_block("inspect_photo", {"idx": 0})],
    ])

    async def inspector(idx):
        return {"aspects_visible": [], "findings": {}}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
        max_outer_turns=12, max_inspects=2,
    )
    assert assessment.budget_exceeded is True
    # All findings present, defaulted to not_visible
    assert all(f.severity == "not_visible" for f in assessment.findings)


async def test_agent_force_finalizes_on_outer_turn_budget(fake_manifest):
    # Agent never calls final_assessment; force-finalize after max_outer_turns
    blocks = [[_tool_use_block("list_photos", {})] for _ in range(20)]
    client = _make_client(blocks)

    async def inspector(idx):
        return {}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
        max_outer_turns=3, max_inspects=10,
    )
    assert assessment.budget_exceeded is True
    assert assessment.agent_turns == 3
```

- [ ] **Step 3: Run failing**

Run: `uv run pytest tests/test_vision_agent.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement the outer agent**

```python
# src/ci/vision/agent.py
"""Outer vision agent: orchestrates tool-use turns until final_assessment.

Caps:
  - max_outer_turns (default 12): force-finalize after this many model turns
  - max_inspects (default 10): force-finalize after this many inspect_photo calls

On force-finalize, missing aspects default to severity="not_visible" and
budget_exceeded=True is set on the assessment.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from ci.schemas import VisionAssessment, VisionFinding
from ci.vision.tools import ALL_TOOLS

OUTER_MODEL = "claude-sonnet-4-6"
OUTER_PROMPT_VERSION = "v1"

OUTER_SYSTEM_PROMPT = """\
You are inspecting used-car listing photos to score visual condition across five aspects:
  exterior_panels, interior_cabin, dashboard_console, tyres, engine_bay.

You have these tools:
  - list_photos(): see what photos are available for this listing
  - inspect_photo(idx): get per-aspect findings for one photo
  - note_evidence_gap(aspect, reason): record an aspect you cannot evidence
  - final_assessment(per_aspect): submit your final per-aspect assessment (5 entries required)

Strategy:
  - Call list_photos() first to see what's available (use the hints to prioritize).
  - Inspect strategically — do not inspect every photo. Aim for ≤10 inspections.
  - When you have enough evidence (or have explicitly noted gaps for all uncovered aspects),
    call final_assessment with all 5 aspects.

Severity scale: pristine, light_wear, moderate, heavy, defect, not_visible.
Be conservative — if uncertain, mark not_visible rather than guess.
"""

_ASPECTS = ("exterior_panels", "interior_cabin",
            "dashboard_console", "tyres", "engine_bay")


def _default_assessment(
    listing_id: str, platform: str,
    manifest: dict, photos_inspected: list[int], turns: int,
    *, budget_exceeded: bool = False, partial_per_aspect: dict | None = None,
) -> VisionAssessment:
    """Build a VisionAssessment with not_visible defaults for any missing aspect."""
    per_aspect = partial_per_aspect or {}
    findings = []
    for a in _ASPECTS:
        if a in per_aspect:
            d = per_aspect[a]
            findings.append(VisionFinding(
                aspect=a,  # type: ignore[arg-type]
                severity=d.get("severity", "not_visible"),
                confidence=d.get("confidence", "low"),
                photo_refs=d.get("photo_refs", []),
                evidence_note=d.get("evidence_note", "")[:200],
            ))
        else:
            findings.append(VisionFinding(
                aspect=a,  # type: ignore[arg-type]
                severity="not_visible", confidence="low",
                photo_refs=[], evidence_note="",
            ))
    return VisionAssessment(
        listing_id=listing_id, platform=platform,  # type: ignore[arg-type]
        findings=findings,
        photos_inspected=photos_inspected,
        photo_count_total=len(manifest.get("photos", [])),
        agent_turns=turns,
        budget_exceeded=budget_exceeded,
    )


async def run_vision_agent(
    *,
    listing_id: str,
    platform: str,
    manifest: dict,
    client: Any,
    inspector_fn: Callable[[int], Awaitable[dict]],
    max_outer_turns: int = 12,
    max_inspects: int = 10,
) -> VisionAssessment:
    """Run the outer agent loop until final_assessment or budget exceeded."""
    photos_inspected: list[int] = []
    inspect_count = 0
    messages: list[dict] = []
    turn = 0
    final_payload: dict | None = None

    while turn < max_outer_turns and final_payload is None:
        turn += 1
        resp = await client.messages.create(
            model=OUTER_MODEL,
            max_tokens=2048,
            system=OUTER_SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": resp.content})

        tool_results: list[dict] = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            tool_use_id = block.id
            inp = block.input

            if name == "list_photos":
                result = [{"idx": p["idx"], "sha256": p["sha256"], "hint": p.get("hint")}
                          for p in manifest.get("photos", [])]
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": str(result)}],
                })
            elif name == "inspect_photo":
                if inspect_count >= max_inspects:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tool_use_id,
                        "content": [{"type": "text",
                                     "text": "ERROR: inspect budget exceeded; call final_assessment now"}],
                        "is_error": True,
                    })
                else:
                    idx = int(inp["idx"])
                    inspect_count += 1
                    if idx not in photos_inspected:
                        photos_inspected.append(idx)
                    findings = await inspector_fn(idx)
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tool_use_id,
                        "content": [{"type": "text", "text": str(findings)}],
                    })
            elif name == "note_evidence_gap":
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": "ack"}],
                })
            elif name == "final_assessment":
                final_payload = inp
                break  # terminate outer loop after this turn
            else:
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": f"ERROR: unknown tool {name}"}],
                    "is_error": True,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    if final_payload is not None:
        return _default_assessment(
            listing_id=listing_id, platform=platform,
            manifest=manifest, photos_inspected=photos_inspected, turns=turn,
            partial_per_aspect=final_payload.get("per_aspect", {}),
        )

    # Force-finalize on budget exceeded
    return _default_assessment(
        listing_id=listing_id, platform=platform,
        manifest=manifest, photos_inspected=photos_inspected, turns=turn,
        budget_exceeded=True,
    )
```

- [ ] **Step 5: Tests pass**

Run: `uv run pytest tests/test_vision_agent.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/ci/vision/tools.py src/ci/vision/agent.py tests/test_vision_agent.py
git commit -m "feat(vision): outer agent loop with tool-use orchestration and budget caps"
```

---

## Task 9: Vision score aggregation

**Files:**
- Create: `src/ci/vision/score.py`
- Create: `tests/test_vision_score.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vision_score.py
"""Set-relative rank-based aggregation of VisionAssessments to VisionScores."""
from ci.schemas import VisionAssessment, VisionFinding
from ci.vision.score import compute_vision_scores, _severity_to_int


def _assess(lid: str, sev_map: dict[str, str]) -> VisionAssessment:
    return VisionAssessment(
        listing_id=lid, platform="cars24",
        findings=[
            VisionFinding(aspect=a, severity=sev_map[a], confidence="med",  # type: ignore[arg-type]
                          photo_refs=[], evidence_note="")
            for a in ("exterior_panels", "interior_cabin",
                      "dashboard_console", "tyres", "engine_bay")
        ],
        photos_inspected=[], photo_count_total=0, agent_turns=0,
    )


def test_severity_to_int_mapping():
    assert _severity_to_int("pristine") == 0
    assert _severity_to_int("light_wear") == 1
    assert _severity_to_int("moderate") == 2
    assert _severity_to_int("heavy") == 3
    assert _severity_to_int("defect") == 4
    assert _severity_to_int("not_visible") is None


def test_two_listing_set_pristine_vs_defect_get_extreme_scores():
    a = _assess("A", {a: "pristine" for a in ("exterior_panels", "interior_cabin",
                                              "dashboard_console", "tyres", "engine_bay")})
    b = _assess("B", {a: "defect" for a in ("exterior_panels", "interior_cabin",
                                            "dashboard_console", "tyres", "engine_bay")})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    assert by_id["A"].visual_score == 100.0
    assert by_id["B"].visual_score == 0.0


def test_not_visible_imputes_to_median_score():
    """One listing visible, one not_visible — not_visible gets median of visible."""
    a = _assess("A", {a: "moderate" for a in ("exterior_panels", "interior_cabin",
                                              "dashboard_console", "tyres", "engine_bay")})
    b = _assess("B", {a: "not_visible" for a in ("exterior_panels", "interior_cabin",
                                                 "dashboard_console", "tyres", "engine_bay")})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    # Single visible listing → 100; not_visible → median = 100
    assert by_id["A"].visual_score == 100.0
    assert by_id["B"].visual_score == 100.0
    assert "engine_bay" in by_id["B"].imputed_aspects


def test_visual_score_is_mean_of_per_aspect_scores():
    a = _assess("A", {"exterior_panels": "pristine", "interior_cabin": "pristine",
                      "dashboard_console": "defect", "tyres": "defect", "engine_bay": "defect"})
    b = _assess("B", {"exterior_panels": "defect", "interior_cabin": "defect",
                      "dashboard_console": "pristine", "tyres": "pristine", "engine_bay": "pristine"})
    scores = compute_vision_scores([a, b])
    by_id = {s.listing_id: s for s in scores}
    # A: 100, 100, 0, 0, 0 → mean 40; B: 0, 0, 100, 100, 100 → mean 60
    assert by_id["A"].visual_score == 40.0
    assert by_id["B"].visual_score == 60.0
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_vision_score.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/ci/vision/score.py
"""Set-relative rank-based aggregation of vision findings.

Mirrors src/ci/score.py:_per_dim_scores semantics: per aspect, rank listings
by numeric severity (lower is better), map rank to 0-100, missing values get
median of valid scores. Per-listing visual_score = mean of 5 aspect scores.
"""
from __future__ import annotations

from typing import get_args

from ci.schemas import Aspect, Severity, VisionAssessment, VisionScore

_ASPECTS: tuple[str, ...] = get_args(Aspect)

_SEVERITY_ORDER: dict[str, int] = {
    "pristine": 0,
    "light_wear": 1,
    "moderate": 2,
    "heavy": 3,
    "defect": 4,
}


def _severity_to_int(severity: str) -> int | None:
    return _SEVERITY_ORDER.get(severity)  # not_visible → None


def _rank_to_score(rank: float, n: int) -> float:
    if n <= 1:
        return 100.0
    return round(100.0 * (n - rank) / (n - 1), 2)


def _per_aspect_scores_for_set(
    assessments: list[VisionAssessment], aspect: str
) -> dict[str, float]:
    """Return {listing_id: 0-100 score} for one aspect across the listing set."""
    pairs: list[tuple[str, int | None]] = []
    for a in assessments:
        sev = next((f.severity for f in a.findings if f.aspect == aspect), "not_visible")
        pairs.append((a.listing_id, _severity_to_int(sev)))

    valid = [(lid, v) for lid, v in pairs if v is not None]
    missing_ids = [lid for lid, v in pairs if v is None]
    k = len(valid)

    out: dict[str, float] = {}
    if k == 0:
        return {lid: 50.0 for lid, _ in pairs}

    # Lower severity is better → sort ascending and rank 1..k
    valid_sorted = sorted(valid, key=lambda x: x[1])
    i = 0
    while i < len(valid_sorted):
        j = i
        while j < len(valid_sorted) and valid_sorted[j][1] == valid_sorted[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for idx in range(i, j):
            out[valid_sorted[idx][0]] = _rank_to_score(avg_rank, k)
        i = j

    if missing_ids:
        valid_scores = sorted(out.values())
        m = len(valid_scores)
        if m % 2 == 1:
            median = valid_scores[m // 2]
        else:
            median = (valid_scores[m // 2 - 1] + valid_scores[m // 2]) / 2
        for lid in missing_ids:
            out[lid] = median

    return out


def compute_vision_scores(assessments: list[VisionAssessment]) -> list[VisionScore]:
    """Per-listing VisionScore from a set of assessments. Set-relative ranks per aspect."""
    per_aspect_table: dict[str, dict[str, float]] = {
        aspect: _per_aspect_scores_for_set(assessments, aspect) for aspect in _ASPECTS
    }
    out: list[VisionScore] = []
    for a in assessments:
        per_aspect_score = {asp: per_aspect_table[asp][a.listing_id] for asp in _ASPECTS}
        visual = round(sum(per_aspect_score.values()) / len(_ASPECTS), 2)
        imputed = [
            f.aspect for f in a.findings if f.severity == "not_visible"
        ]
        out.append(VisionScore(
            listing_id=a.listing_id, platform=a.platform,
            visual_score=visual,
            per_aspect_score=per_aspect_score,  # type: ignore[arg-type]
            imputed_aspects=imputed,
            assessment=a,
        ))
    return out
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_vision_score.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ci/vision/score.py tests/test_vision_score.py
git commit -m "feat(vision): set-relative rank-based vision_score aggregation"
```

---

## Task 10: Composite score + ranking

**Files:**
- Create: `src/ci/vision/composite.py`
- Modify: `src/ci/rank.py`
- Modify: `src/ci/report.py`
- Create: `tests/test_vision_composite.py`
- Modify: `tests/test_rank.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Write failing tests for composite**

```python
# tests/test_vision_composite.py
from ci.vision.composite import compute_composite, DEFAULT_ALPHA


def test_default_alpha_is_0_7_rule_leaning():
    assert DEFAULT_ALPHA == 0.7


def test_compute_composite_with_default_alpha():
    # 0.7 * 80 + 0.3 * 60 = 56 + 18 = 74
    assert compute_composite(rule_score=80.0, visual_score=60.0) == 74.0


def test_compute_composite_with_alpha_1_returns_rule_only():
    assert compute_composite(rule_score=80.0, visual_score=60.0, alpha=1.0) == 80.0


def test_compute_composite_with_alpha_0_returns_visual_only():
    assert compute_composite(rule_score=80.0, visual_score=60.0, alpha=0.0) == 60.0


def test_compute_composite_rounds_to_2dp():
    # 0.333... * 90 + 0.666... * 60 = 30 + 40 = 70 — just check 2dp
    out = compute_composite(rule_score=90.0, visual_score=60.0, alpha=1/3)
    assert out == round(out, 2)
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_vision_composite.py -v`

- [ ] **Step 3: Implement composite**

```python
# src/ci/vision/composite.py
"""Composite score: alpha-weighted blend of rule_score and visual_score."""

DEFAULT_ALPHA: float = 0.7


def compute_composite(
    *, rule_score: float, visual_score: float, alpha: float = DEFAULT_ALPHA
) -> float:
    """composite = alpha * rule + (1 - alpha) * visual; rounded to 2dp."""
    return round(alpha * rule_score + (1 - alpha) * visual_score, 2)
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_vision_composite.py -v`
Expected: 5 passed.

- [ ] **Step 5: Read the current rank.py and report.py**

Run: `cat src/ci/rank.py src/ci/report.py`. Note the current ranking logic — it ranks by `score_common`, builds `RankRow` with `rule_score=...` (after Task 2's rename).

- [ ] **Step 6: Modify `src/ci/rank.py` to be composite-aware**

Replace `rank_listings` with a version that accepts an optional `vision_scores: dict[str, VisionScore]` and computes composite when provided.

```python
# src/ci/rank.py — full replacement (preserve any helpers above the function)
from ci.schemas import NormalizedListing, RankRow, ScoreRecord, VisionScore
from ci.vision.composite import compute_composite, DEFAULT_ALPHA


def rank_listings(
    pairs: list[tuple[NormalizedListing, ScoreRecord]],
    *,
    vision_scores: dict[str, VisionScore] | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> list[RankRow]:
    """Sort listings by composite_score (or rule_score if no vision); produce RankRows.

    When vision_scores is None: ratio = price / rule_score (today's behavior).
    When vision_scores is provided: ratio = price / composite_score.
    """
    rows: list[RankRow] = []
    for n, sc in pairs:
        vs = (vision_scores or {}).get(n.listing_id)
        rule_score = sc.score_common
        visual_score = vs.visual_score if vs else None
        composite_score = (
            compute_composite(rule_score=rule_score, visual_score=visual_score, alpha=alpha)
            if visual_score is not None else None
        )
        denom = composite_score if composite_score is not None else rule_score
        ratio = round(n.price / denom, 2) if denom > 0 else 0.0
        imputed_aspects = list(vs.imputed_aspects) if vs else []
        rows.append(RankRow(
            listing_id=n.listing_id, platform=n.platform, price=n.price,
            rule_score=rule_score, visual_score=visual_score,
            composite_score=composite_score, ratio=ratio,
            disclosure_count=sc.disclosure_count, imputed_dims=sc.imputed_dims,
            imputed_aspects=imputed_aspects,
        ))
    # Sort by composite_score (or rule_score if absent), descending.
    rows.sort(key=lambda r: (r.composite_score if r.composite_score is not None else r.rule_score),
              reverse=True)
    return rows
```

- [ ] **Step 7: Update `src/ci/report.py`**

Current report.py is a small chart renderer using `r.score_common` on the x-axis. Update to use `composite_score` if present, else `rule_score`:

```python
# src/ci/report.py — full replacement
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ci.schemas import RankRow


def _x_value(r: RankRow) -> float:
    """Prefer composite_score (when vision ran), fall back to rule_score."""
    return r.composite_score if r.composite_score is not None else r.rule_score


def render_chart(rows: list[RankRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    has_visual = any(r.composite_score is not None for r in rows)
    x_label = (
        "composite score (α·rule + (1-α)·visual, set-relative)"
        if has_visual else
        "condition score (rank-based, 0–100, relative to this set)"
    )
    for plat, marker, color in [("cars24", "o", "#1f77b4"), ("spinny", "s", "#d62728")]:
        sub = [r for r in rows if r.platform == plat]
        if not sub:
            continue
        ax.scatter(
            [_x_value(r) for r in sub],
            [r.price / 1e5 for r in sub],
            marker=marker, color=color, label=plat, s=80,
        )
        for r in sub:
            ax.annotate(r.listing_id, (_x_value(r), r.price / 1e5),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel(x_label)
    ax.set_ylabel("price (₹ lakh)")
    title = "Cars24 vs Spinny — price vs " + ("composite" if has_visual else "rule") + " score"
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
```

If `tests/test_report.py` references `score_common` or asserts a specific x-label string, update those assertions to match the new field names and conditional label.

- [ ] **Step 8: Update tests**

`tests/test_rank.py`: existing tests pass `pairs` to rank_listings without `vision_scores`. They should still work (vision_scores defaults to None). Verify by running.

Add a new test:

```python
# Append to tests/test_rank.py
def test_rank_with_vision_scores_uses_composite():
    from ci.schemas import (
        NormalizedListing, ScoreRecord, VisionScore,
        VisionAssessment, VisionFinding,
    )
    from ci.rank import rank_listings

    n1 = NormalizedListing(
        platform="cars24", listing_id="L1", price=500000,
        km_driven=50000, age_years=3, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={}, full_fields={},
    )
    sc1 = ScoreRecord(
        listing_id="L1", platform="cars24", score_common=80.0,
        per_dim={}, imputed_dims=[], disclosure_count=0, disclosed_fields={},
    )
    vs1 = VisionScore(
        listing_id="L1", platform="cars24",
        visual_score=60.0, per_aspect_score={
            "exterior_panels": 60.0, "interior_cabin": 60.0,
            "dashboard_console": 60.0, "tyres": 60.0, "engine_bay": 60.0,
        }, imputed_aspects=[],
        assessment=VisionAssessment(
            listing_id="L1", platform="cars24", findings=[
                VisionFinding(aspect=a, severity="moderate", confidence="med",
                              photo_refs=[], evidence_note="")
                for a in ("exterior_panels", "interior_cabin",
                          "dashboard_console", "tyres", "engine_bay")
            ],
            photos_inspected=[], photo_count_total=5, agent_turns=2,
        ),
    )
    rows = rank_listings([(n1, sc1)], vision_scores={"L1": vs1})
    assert rows[0].composite_score == 74.0  # 0.7*80 + 0.3*60
    assert rows[0].ratio == round(500000 / 74.0, 2)
```

- [ ] **Step 9: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass (including any test_report.py adjustments needed).

- [ ] **Step 10: Commit**

```bash
git add src/ci/vision/composite.py src/ci/rank.py src/ci/report.py tests/
git commit -m "feat(vision): composite-aware ranking and report columns"
```

---

## Task 11: Pipeline integration + CLI flags

**Files:**
- Modify: `src/ci/pipeline.py`
- Modify: `scripts/run_pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Read existing pipeline.py + run_pipeline.py + test_pipeline.py**

Read `src/ci/pipeline.py` (run_pipeline function), `scripts/run_pipeline.py` (CLI entrypoint), `tests/test_pipeline.py` (current tests).

- [ ] **Step 2: Modify `src/ci/pipeline.py`**

Add an async vision phase:

```python
# Add at top of src/ci/pipeline.py
import asyncio
from pathlib import Path

from ci.schemas import VisionScore  # add to imports
from ci.vision.score import compute_vision_scores
from ci.vision.composite import DEFAULT_ALPHA


async def _run_vision_for_set(
    *, norms, manifests_root: Path, run_dir: Path,
    inner_cache_root: Path, no_cache: bool,
    listings_subset: set[str] | None = None,
    max_outer_turns: int = 12, max_inspects: int = 10,
):
    """Run the outer agent + inner inspector across the listing set; return list[VisionScore]."""
    from anthropic import AsyncAnthropic
    from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION
    from ci.vision.cache import InnerCache
    from ci.vision.agent import run_vision_agent
    from ci.vision.manifest import read_manifest

    client = AsyncAnthropic()
    cache = InnerCache(root=inner_cache_root,
                       prompt_version=INSPECTOR_PROMPT_VERSION, bypass=no_cache)

    async def run_one(n):
        if listings_subset is not None and n.listing_id not in listings_subset:
            return None
        manifest_path = manifests_root / n.platform / n.listing_id / "photos.json"
        manifest = read_manifest(manifest_path)
        if manifest is None or not manifest.get("photos"):
            return None  # no photos captured for this listing

        async def inspector_fn(idx: int) -> dict:
            entry = next((p for p in manifest["photos"] if p["idx"] == idx), None)
            if entry is None:
                return {"aspects_visible": [], "findings": {}}
            photo_path = manifests_root / n.platform / n.listing_id / "photos" / f"{entry['sha256']}.jpg"
            if not photo_path.exists():
                return {"aspects_visible": [], "findings": {}}
            return await inspect_photo(
                photo_path=photo_path, photo_sha=entry["sha256"],
                client=client, cache=cache,
            )

        return await run_vision_agent(
            listing_id=n.listing_id, platform=n.platform,
            manifest=manifest, client=client, inspector_fn=inspector_fn,
            max_outer_turns=max_outer_turns, max_inspects=max_inspects,
        )

    results = await asyncio.gather(*(run_one(n) for n in norms))
    assessments = [r for r in results if r is not None]
    return compute_vision_scores(assessments)
```

Modify `run_pipeline` signature and body to accept vision params and call the vision phase:

```python
def run_pipeline(
    *,
    listings: list[tuple[str, str]],  # full active set (16: 10 gold + 6 ranking)
    ranking_listing_ids: set[str],     # of the 16, which are the deliverable rows
    run_dir: Path,
    today_year: int | None = None,
    enable_vision: bool = True,
    vision_no_cache: bool = False,
    vision_listings_subset: set[str] | None = None,
    vision_max_inspects: int = 10,
    alpha: float = DEFAULT_ALPHA,
) -> list[RankRow]:
    """Run the full pipeline. Vision phase optional via enable_vision flag."""
    run_id = run_dir.name
    store = TraceStore(run_dir=run_dir)
    norms: list[NormalizedListing] = []

    for platform, lid in listings:
        t0 = time.time()
        snap = load_snapshot(platform, lid)
        _trace(store, run_id, f"snapshot.load.{platform}", t0,
               {"platform": platform, "listing_id": lid},
               {"captured_at": snap.captured_at})

        t0 = time.time()
        if platform == "cars24":
            raw = extract_cars24(snap)
        elif platform == "spinny":
            raw = extract_spinny(snap)
        else:
            raise ValueError(f"unsupported platform: {platform}")
        _trace(store, run_id, f"extract.{platform}", t0,
               {"listing_id": lid}, {"fields_keys": list(raw.fields.keys())[:20]})

        t0 = time.time()
        norm = normalize(raw, today_year=today_year)
        _trace(store, run_id, f"normalize.{platform}", t0,
               {"listing_id": lid}, norm.model_dump(exclude={"full_fields"}))

        norms.append(norm)

    t0 = time.time()
    score_records = score_listings(norms)
    _trace(store, run_id, "score", t0,
           [{"id": n.listing_id} for n in norms],
           [{"id": s.listing_id, "score_common": s.score_common} for s in score_records])

    vision_scores: dict[str, VisionScore] = {}
    if enable_vision:
        from ci.config import FIXTURES_DIR
        from pathlib import Path as _Path
        cache_root = _Path("runs/.cache/vision")
        t0 = time.time()
        vs_list = asyncio.run(_run_vision_for_set(
            norms=norms, manifests_root=FIXTURES_DIR, run_dir=run_dir,
            inner_cache_root=cache_root, no_cache=vision_no_cache,
            listings_subset=vision_listings_subset,
            max_inspects=vision_max_inspects,
        ))
        for vs in vs_list:
            vision_scores[vs.listing_id] = vs
        _trace(store, run_id, "vision_score.aggregate", t0,
               [{"id": n.listing_id} for n in norms],
               [{"id": v.listing_id, "visual_score": v.visual_score} for v in vs_list])

    pairs = list(zip(norms, score_records))
    t0 = time.time()
    rows = rank_listings(pairs, vision_scores=vision_scores or None, alpha=alpha)
    _trace(store, run_id, "rank", t0,
           [{"id": p[0].listing_id} for p in pairs],
           [{"id": r.listing_id, "ratio": r.ratio} for r in rows])

    # Filter output to ranking listings (the 6 held-out)
    return [r for r in rows if r.listing_id in ranking_listing_ids]
```

Note: the function now returns the **filtered** ranking rows (6 of 16), even though it ranks all 16 internally for set-relative scoring. This matches spec §13.1's "the 6 ranking listings receive composite_score under the fixed-on-gold α, and that scored output is the deliverable".

- [ ] **Step 3: Modify `scripts/run_pipeline.py`**

```python
# scripts/run_pipeline.py — full replacement
"""Run the end-to-end pipeline on the 16-listing active set (10 gold + 6 ranking).

Vision phase is on by default; turn off with --no-vision for a pure deterministic run.
Output ranking is filtered to the 6 ranking listings.
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

from ci.config import EVAL_DIR, RUNS_DIR
from ci.pipeline import run_pipeline


def _load_active_listings() -> tuple[list[tuple[str, str]], set[str]]:
    """Return (16-listing union, set of ranking listing ids)."""
    gold_rows = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking_rows = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    listings = (
        [(g["platform"], g["listing_id"]) for g in gold_rows]
        + [(r["platform"], r["listing_id"]) for r in ranking_rows]
    )
    ranking_ids = {r["listing_id"] for r in ranking_rows}
    return listings, ranking_ids


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-vision", action="store_true",
                   help="Skip the vision agent; pipeline runs deterministically.")
    p.add_argument("--vision-no-cache", action="store_true",
                   help="Bypass inner inspector cache (E5 cold-cache runs).")
    p.add_argument("--vision-listings", default=None,
                   help="Comma-separated listing-id subset for vision (debug / cost-cap).")
    p.add_argument("--vision-budget", type=int, default=10,
                   help="Max inspect_photo calls per listing (default 10).")
    p.add_argument("--alpha", type=float, default=None,
                   help="Override default composite alpha (0.7).")
    args = p.parse_args()

    listings, ranking_ids = _load_active_listings()

    vision_subset = None
    if args.vision_listings:
        vision_subset = set(s.strip() for s in args.vision_listings.split(",") if s.strip())

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-" + uuid.uuid4().hex[:6]
    )
    run_dir = RUNS_DIR / run_id

    from ci.vision.composite import DEFAULT_ALPHA
    alpha = args.alpha if args.alpha is not None else DEFAULT_ALPHA

    rows = run_pipeline(
        listings=listings,
        ranking_listing_ids=ranking_ids,
        run_dir=run_dir,
        enable_vision=not args.no_vision,
        vision_no_cache=args.vision_no_cache,
        vision_listings_subset=vision_subset,
        vision_max_inspects=args.vision_budget,
        alpha=alpha,
    )
    out = run_dir / "ranking.json"
    out.write_text(json.dumps([r.model_dump() for r in rows], indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `tests/test_pipeline.py`**

Replace the file with the new signature + vision-off:

```python
# tests/test_pipeline.py — full replacement
import json

from ci.pipeline import run_pipeline


def test_pipeline_runs_end_to_end_against_real_fixtures(tmp_path):
    rows = run_pipeline(
        listings=[
            ("cars24", "10041693110"),
            ("spinny", "28476005"),
        ],
        ranking_listing_ids={"10041693110", "28476005"},
        run_dir=tmp_path / "runs" / "r1",
        today_year=2026,
        enable_vision=False,
    )
    assert len(rows) == 2
    assert all(r.rule_score > 0 for r in rows)
    # Sorted descending by composite (= rule_score when no vision); ratio descending check is too strict
    assert rows[0].rule_score >= rows[1].rule_score


def test_pipeline_writes_trace_per_node(tmp_path):
    run_pipeline(
        listings=[("cars24", "10041693110")],
        ranking_listing_ids={"10041693110"},
        run_dir=tmp_path / "runs" / "r2",
        today_year=2026,
        enable_vision=False,
    )
    trace_path = tmp_path / "runs" / "r2" / "trace.jsonl"
    assert trace_path.exists()
    nodes = [json.loads(l)["node"] for l in trace_path.read_text().splitlines() if l.strip()]
    assert "snapshot.load.cars24" in nodes
    assert "extract.cars24" in nodes
    assert "normalize.cars24" in nodes
    assert "score" in nodes
    assert "rank" in nodes
```

Note: the assertion changes from "ratio ascending" to "rule_score descending" because `rank_listings` now sorts by score descending (highest score first). If the existing rank.py sorted ascending by ratio, you'll see the new order. Adjust the assertion if the original semantics were different — read the existing rank.py before this task to confirm.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest -q`
Expected: all green. (Vision agent code remains mocked in its own tests; pipeline integration test runs vision OFF.)

- [ ] **Step 6: Commit**

```bash
git add src/ci/pipeline.py scripts/run_pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): integrate vision agent on 16-listing union; preserve --no-vision"
```

---

## Task 12: End-to-end smoke test (real API, small subset)

**Note:** This task hits the real Anthropic API. Cost estimate: ~$0.05-0.15 for 2 listings. Confirm `ANTHROPIC_API_KEY` is set in `.env` before running.

- [ ] **Step 1: Confirm API key present**

Run: `grep -c ANTHROPIC_API_KEY .env`
Expected: 1.

- [ ] **Step 2: Run pipeline against 2 listings (1 cars24 + 1 spinny) with vision on**

Run:
```bash
uv run python -m scripts.run_pipeline --vision-listings 10182490193,27741490
```

Expected:
- Process completes within ~90 seconds
- Prints `wrote runs/<ts>/ranking.json`
- No unhandled exceptions

- [ ] **Step 3: Verify output**

Run:
```bash
uv run python -c "
import json, glob
latest = sorted(glob.glob('runs/2*'))[-1]
rows = json.loads(open(f'{latest}/ranking.json').read())
print('rows:', len(rows))
for r in rows:
    print(f\"  {r['listing_id']:14} rule={r['rule_score']:5.2f} \"
          f\"visual={r.get('visual_score') or 'NA':>6} \"
          f\"composite={r.get('composite_score') or 'NA':>6} \"
          f\"ratio={r['ratio']}\")
trace = open(f'{latest}/trace.jsonl').read().splitlines()
vision_events = [l for l in trace if 'vision' in l]
print(f'vision trace events: {len(vision_events)}')
"
```
Expected: 6 rows (filtered ranking output). 2 of them (the subset we ran vision on, IF they happen to be in the ranking set... actually they won't be — gold listings won't appear in output). 

**Wait — important:** the subset listings 10182490193 and 27741490 are *gold* listings, not ranking listings. So the filter at the end of `run_pipeline` will drop them from output. That's correct behavior, but the smoke test won't show vision data.

Adjust: pick a subset of 2 RANKING listings for visible smoke output:

Re-run:
```bash
uv run python -m scripts.run_pipeline --vision-listings 10067090111,27839393
```

Now expect 2 of the 6 output rows to have non-null `visual_score` and `composite_score`.

- [ ] **Step 4: Sanity-check trace events**

Run:
```bash
uv run python -c "
import json, glob
latest = sorted(glob.glob('runs/2*'))[-1]
trace = [json.loads(l) for l in open(f'{latest}/trace.jsonl').read().splitlines() if l.strip()]
nodes = [e['node'] for e in trace]
print('vision nodes seen:', sorted(set(n for n in nodes if 'vision' in n)))
"
```
Expected: at minimum `vision_score.aggregate` appears.

- [ ] **Step 5: No commit needed.** This is a smoke run; outputs go to gitignored `runs/`.

If the smoke test reveals bugs, address them before proceeding to Task 13. Common issues:
- API key misconfigured → set in `.env`
- Manifest not present for a listing → run `uv run python -m scripts.capture_photos --all` (Task 5)
- Anthropic SDK API mismatch → check installed version against `client.messages.create` signature

---

## Task 13: Vision gold template builder + anchors doc

**Files:**
- Create: `scripts/build_vision_gold_template.py`
- Create: `eval/vision_gold.jsonl` (template, all severities null — output)
- Create: `eval/vision_gold.anchors.md` (output)
- Create: `tests/test_build_vision_gold_template.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_build_vision_gold_template.py
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
```

- [ ] **Step 2: Run failing**

Run: `uv run pytest tests/test_build_vision_gold_template.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# scripts/build_vision_gold_template.py
"""Generate eval/vision_gold.jsonl template (16 listings × 5 aspects, all nulls).

Also generates eval/vision_gold.anchors.md — a calibration doc that points the
hand-labeller at example photos for each severity level. Anchors are picked as
the first inspectable photo per listing/aspect; the human still does the rating.

Usage:
  uv run python -m scripts.build_vision_gold_template
"""
from __future__ import annotations

import json
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR

ASPECTS = ("exterior_panels", "interior_cabin",
           "dashboard_console", "tyres", "engine_bay")


def _active_listings() -> list[dict]:
    """16-listing union: 10 gold + 6 ranking."""
    gold = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    return [{"platform": g["platform"], "listing_id": g["listing_id"]} for g in gold] \
         + [{"platform": r["platform"], "listing_id": r["listing_id"]} for r in ranking]


def build_template_rows(listings: list[dict]) -> list[dict]:
    return [
        {
            "listing_id": l["listing_id"],
            "platform": l["platform"],
            "vision_gold": {a: None for a in ASPECTS},
            "notes": {},
        }
        for l in listings
    ]


def _write_anchors_doc(listings: list[dict], out_path: Path) -> None:
    """Reference doc with the first photo per listing for the labeler's eye."""
    lines = [
        "# Vision Gold Anchors\n",
        "Reference photos for severity calibration. Open these before labeling so",
        "your `pristine`/`light_wear`/`moderate`/`heavy`/`defect` calls are consistent",
        "across the session.\n",
        "## Severity definitions\n",
        "- **pristine**: no visible wear. Looks new.",
        "- **light_wear**: minor scuffs, light usage marks. Normal aging.",
        "- **moderate**: visible wear. Multiple small dents/scratches OR significant fade.",
        "- **heavy**: prominent damage. Multiple large dings, deep scratches, severe fade.",
        "- **defect**: structural / functional fault visible (cracked panel, missing trim).",
        "- **not_visible**: no photo evidences this aspect.\n",
        "## Per-listing photo index\n",
    ]
    for l in listings:
        lid, plat = l["listing_id"], l["platform"]
        manifest_path = FIXTURES_DIR / plat / lid / "photos.json"
        if not manifest_path.exists():
            lines.append(f"### {plat}/{lid} — NO PHOTOS CAPTURED\n")
            continue
        manifest = json.loads(manifest_path.read_text())
        photos = manifest.get("photos", [])
        lines.append(f"### {plat}/{lid} ({len(photos)} photos)\n")
        for p in photos[:8]:  # cap at 8 per listing in the anchor doc
            hint = p.get("hint") or "?"
            lines.append(f"- idx {p['idx']:>3} ({hint:<10}) `{p['source_url']}`")
        if len(photos) > 8:
            lines.append(f"- ... +{len(photos) - 8} more")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    listings = _active_listings()
    rows = build_template_rows(listings)
    out_jsonl = EVAL_DIR / "vision_gold.jsonl"
    header = (
        "# severity ∈ {pristine, light_wear, moderate, heavy, defect, not_visible}\n"
        "# notes: optional per-aspect comment, e.g. {\"tyres\": \"rear-left tread visibly low\"}\n"
    )
    out_jsonl.write_text(header + "\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} template rows to {out_jsonl}")

    anchors = EVAL_DIR / "vision_gold.anchors.md"
    _write_anchors_doc(listings, anchors)
    print(f"Wrote anchors doc to {anchors}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_build_vision_gold_template.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the script**

Run: `uv run python -m scripts.build_vision_gold_template`
Expected: prints `Wrote 16 template rows ...` and `Wrote anchors doc ...`.

- [ ] **Step 6: Verify outputs**

Run:
```bash
wc -l eval/vision_gold.jsonl eval/vision_gold.anchors.md
head -1 eval/vision_gold.jsonl
```
Expected:
- `eval/vision_gold.jsonl` has 18 lines (2 header comments + 16 rows)
- `eval/vision_gold.anchors.md` exists with content
- First non-comment row is a JSON object with `vision_gold` containing 5 nulls

- [ ] **Step 7: Commit**

```bash
git add scripts/build_vision_gold_template.py tests/test_build_vision_gold_template.py eval/vision_gold.jsonl eval/vision_gold.anchors.md
git commit -m "feat(eval): vision-gold template builder + calibration anchors doc"
```

---

## Task 14: Final verification + tag

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 2: Verify pipeline runs cleanly with vision OFF**

Run:
```bash
uv run python -m scripts.run_pipeline --no-vision
```
Expected: produces 6 ranking rows in `runs/<ts>/ranking.json`, all with `visual_score=null` and `composite_score=null`. Sanity-check by reading the file.

- [ ] **Step 3: Tag**

```bash
git tag -a plan-b-complete -m "Plan B complete: vision agent integrated; vision_gold template ready for hand-labeling"
```

- [ ] **Step 4: Hand-off note**

After Plan B is done, the user hand-labels `eval/vision_gold.jsonl` (16 rows × 5 aspects = 80 cells, ~60-90 min). Then Plan C is authored to add E3/E4/E5/E6 evals + reporting.

---

## Plan B complete. User hand-labels next, then Plan C is authored.
