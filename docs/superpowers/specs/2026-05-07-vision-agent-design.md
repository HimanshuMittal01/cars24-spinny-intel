# Vision Agent — Design Spec

**Date:** 2026-05-07
**Project:** cars24-comp-intel
**Status:** Approved design, pending implementation plan

---

## 1. Problem and goal

The existing pipeline is deterministic JSON-extract → normalize → rank-based score
→ rank → report. It contains zero LLM calls. The original brief asked for a
multi-agent system; the JSON-parse-first approach was the right engineering call
but eliminated the agent layer entirely.

**Goal:** add a *vision agent* that scores per-listing visual condition from
photos, integrates as a second signal alongside the deterministic rule score,
and produces a single composite ranking. The vision agent is a parallel
addition — the deterministic JSON path is unchanged.

**Why vision specifically:** photos contain signal that is not in the structured
JSON, and pixel-level interpretation genuinely requires a VLM. This is where an
LLM earns its keep, not theatre.

---

## 2. Non-goals

- Replacing the deterministic rule scorer.
- Cross-model ensemble or non-Claude VLMs.
- Per-wheel granularity (one `tyres` aspect, not four).
- Photo-fraud detection beyond what severity classification reveals.
- Real-time or streaming inference.

---

## 3. Architecture

```
per listing (sync, existing):
  snapshot.load → extract → normalize

once per run (NEW, async):
  vision_agent over the listing set, parallelized per listing

set-based (NEW + existing):
  vision_score    (rank-based, set-relative, NEW)
  rule_score      (rank-based, set-relative, existing)
  composite_score (NEW, blend)
  rank → report   (existing, augmented)
```

The vision step is opt-out via `--no-vision`. Without it the pipeline is
identical to today's deterministic flow. Async is contained to the vision step;
the pipeline body remains synchronous and wraps the async vision phase with a
single `asyncio.run` call.

---

## 4. Photo capture (one-time, on disk)

Photo bytes are snapshotted to disk once at capture time. The pipeline never
hits the live CDN.

```
fixtures/<platform>/<listing_id>/
  page.html            (existing)
  captured_at.txt      (existing)
  photos/<sha256>.jpg  (NEW, content-addressed)
  photos.json          (NEW, manifest)
```

**Manifest shape:**

```json
{
  "captured_at": "2026-05-07T12:00:00Z",
  "photos": [
    {
      "idx": 0,
      "sha256": "ab12...",
      "source_url": "https://spn-mda.spinny.com/img/...",
      "hint": "exterior_front"
    }
  ]
}
```

**Capture script:** `scripts/capture_photos.py <platform> <listing_id>`

1. Load `page.html` from existing snapshot.
2. Reuse the platform extractor's JSON path to enumerate photo URLs:
   - **Cars24:** photos under the `__next_f` listing payload's image fields.
   - **Spinny:** `galleryV3` (preferred) or `product_photos` from the
     `productDetail` block. `galleryV3` entries sometimes carry section labels
     (e.g. `"exterior"`, `"interior"`, `"engine"`); these become the optional
     `hint` field.
3. Async `httpx` parallel download, dedupe by SHA-256.
4. Write `photos/<sha256>.jpg` and `photos.json`. Idempotent — re-runs skip
   already-on-disk hashes.

Bytes total budget: ~138 MB across 23 fixtures. Add `fixtures/**/photos/*` to
`.gitignore`. Capture runs once; pipeline runs are zero-network.

---

## 5. Vision agent — outer/inner split

Two distinct VLM calls per inspection.

### 5.1 Outer agent (decision layer)

Async per listing. Anthropic Messages API with tools, model
`claude-sonnet-4-6`, temperature 0. Prompt caching on the system prompt and
tool definitions.

**Tools exposed to outer agent:**

| Tool                                        | Semantics                                                                |
|---------------------------------------------|--------------------------------------------------------------------------|
| `list_photos()`                             | Returns `[{idx, sha256, hint?}]` for the current listing's photo set.   |
| `inspect_photo(idx: int)`                   | Fires inner VLM call. Returns multi-aspect findings JSON for that photo.|
| `note_evidence_gap(aspect: str, reason: str)` | Records that the agent looked but cannot evidence this aspect.           |
| `final_assessment(per_aspect: dict)`        | Structured-output terminator. Loop ends when this is invoked.            |

**Termination:** loop ends when `final_assessment` is called by the agent OR
when a budget cap is hit.

**Caps:**

- Max 12 outer turns per listing.
- Max 10 `inspect_photo` calls per listing.

When a cap is hit, the loop force-emits `final_assessment` with the agent's
findings so far; un-evidenced aspects default to `not_visible`. A
`vision_budget_exceeded` warning is written to the trace and reported in the
appendix. The listing still receives a visual score (with imputation) — the
pipeline does not fail.

**System prompt (sketch, finalized in implementation):**

> You are inspecting used-car listing photos to score visual condition across
> five aspects: `exterior_panels`, `interior_cabin`, `dashboard_console`,
> `tyres`, `engine_bay`. List photos first. Inspect strategically — do not
> inspect every photo, prioritize photos most likely to cover under-evidenced
> aspects. When you have enough evidence (or have explicitly used
> `note_evidence_gap`) for all five aspects, call `final_assessment` with your
> findings. Severity scale: `pristine`, `light_wear`, `moderate`, `heavy`,
> `defect`, or `not_visible`. Be conservative — if uncertain, mark
> `not_visible` rather than guess.

### 5.2 Inner inspector (per-photo VLM call)

When the outer agent calls `inspect_photo(idx)`, the tool implementation fires a
separate one-shot VLM call: single photo + a fixed prompt → structured
findings JSON. No tools, no loop.

**Reasons for the split:**

- **Token economy.** Photo bytes never live in the outer agent's growing
  message history. Outer turns send only structured text.
- **Caching.** Inner is a pure function of `(prompt_version, photo_sha256)` →
  trivial cache hit on rerun. Outer's growing message history is a poor cache
  key, so we don't try.
- **Determinism story.** Inner cached → fully reproducible. Outer is the layer
  that varies; E5 measures the right thing.

**Inner prompt (sketch):** "Examine this photo. For each visible aspect from
[exterior_panels, interior_cabin, dashboard_console, tyres, engine_bay],
classify severity from {pristine, light_wear, moderate, heavy, defect}. Aspects
not visible should not appear in `findings`. Return strict JSON matching the
schema."

**Inner output (per inspection):**

```json
{
  "aspects_visible": ["exterior_panels", "tyres"],
  "findings": {
    "exterior_panels": {"severity": "light_wear", "evidence_note": "minor scuff on rear bumper"},
    "tyres": {"severity": "moderate", "evidence_note": "rear-left tread visibly low"}
  }
}
```

The outer agent receives this as a `tool_result` and decides next action.

---

## 6. Aspect taxonomy

Five aspects. Equal weight (20 each). Severity scale shared across all.

| Aspect                | Cars24 coverage | Spinny coverage |
|-----------------------|-----------------|-----------------|
| `exterior_panels`     | yes             | yes             |
| `interior_cabin`      | yes             | yes             |
| `dashboard_console`   | yes             | yes             |
| `tyres`               | sometimes       | usually         |
| `engine_bay`          | rarely          | usually         |

**Severity scale (6-level):** `pristine`, `light_wear`, `moderate`, `heavy`,
`defect`, `not_visible`.

`not_visible` is *imputation*, not penalty — it maps to median per the existing
null-handling policy in `score.py`. This protects Cars24 from being scored
unfairly low on aspects it does not photograph.

**Why no `odometer_match`:** Cars24 does not consistently expose the odometer
in photos. Trying to match the listed km against a sometimes-present digital
readout would create asymmetric platform behavior. Dropped from the taxonomy.

---

## 7. Visual score computation

Mirror the existing rule scorer (`src/ci/score.py:_per_dim_scores`).

```
1. severity → numeric:
     pristine=0, light_wear=1, moderate=2, heavy=3, defect=4
     not_visible → None (imputation marker)

2. per aspect, across the 23-listing set:
     rank listings by numeric severity (lower=better)
     ties get averaged ranks
     rank → 0-100 via _rank_to_score(rank, n)
     not_visible listings → median of valid scores  (existing null policy)

3. visual_score = mean of the 5 aspect scores  (equal weights)
```

Reuses `_rank_to_score` and the imputation pattern verbatim — no new scoring
helpers to defend.

---

## 8. Composite scoring and ranking

```
composite_score = α × rule_score + (1 − α) × visual_score
final_rank      = rank by composite_score (set-relative)
ratio           = price / composite_score
```

Both sub-scores are 0-100, set-based, same units → clean blend.

**α default = 0.7** (rule-leaning). Higher α = more rule weight; lower α =
more visual weight. Defended by audit story: rule score is the deterministic
core; visual is the new supplementary signal that has not yet been validated
by E6 at run time. After E6 reports per-aspect Cohen's κ against the vision
gold:

- κ ≥ 0.6: **lower** α toward 0.5 (visual earned its weight; give it more share).
- κ < 0.4: **hold or raise** α toward 0.85; flag in report as low-trust visual signal.

**α as new E4 sensitivity dim.** Sweep over α ∈ {0.5, 0.6, 0.7, 0.8, 0.9, 1.0}
plus the existing weight-perturbation sweep. Joint analysis: rank stability
under combined perturbation.

**Rationale for composite over side-column:** a "disagreement" flag without a
tiebreaker is just a system artifact. If visual is real signal it should move
the rank; if it isn't we shouldn't compute it. Composite forces the honest
decision.

---

## 9. Schemas

New / modified Pydantic models in `src/ci/schemas.py`:

```python
Aspect = Literal[
    "exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay"
]
Severity = Literal[
    "pristine", "light_wear", "moderate", "heavy", "defect", "not_visible"
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
    findings: list[VisionFinding]   # exactly 5, one per aspect
    photos_inspected: list[int]
    photo_count_total: int
    agent_turns: int
    budget_exceeded: bool = False
    notes: str | None = None


class VisionScore(BaseModel):
    listing_id: str
    platform: Platform
    visual_score: float                        # 0-100, equal-weighted mean
    per_aspect_score: dict[Aspect, float]      # 0-100 each, rank-based
    imputed_aspects: list[Aspect]              # severity == not_visible
    assessment: VisionAssessment


# Existing models: additive, backward-compatible
class ScoreRecord(BaseModel):
    # existing fields unchanged
    ...
    visual_score: float | None = None
    composite_score: float | None = None       # filled when vision step runs


class RankRow(BaseModel):
    listing_id: str
    platform: Platform
    price: int
    rule_score: float                          # was score_common; renamed in serialization
    visual_score: float | None
    composite_score: float | None
    ratio: float                               # price / composite_score (or rule_score if vision off)
    disclosure_count: int
    imputed_dims: list[str]
    imputed_aspects: list[str] = Field(default_factory=list)
```

`score_common` is retained inside `ScoreRecord` for backward compat with the
existing rule gold; `RankRow` exposes it as `rule_score` for the new report
format.

---

## 10. Trace schema extension

In-place extension of `TraceEvent`. One `trace.jsonl` per run, no fork.

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

**Concurrency:** per-listing trace events buffered in memory during the agent
loop, flushed to disk under an `asyncio.Lock` at end-of-loop. Within a listing
the order is preserved; cross-listing order is by completion time.

**New trace nodes:**

- `vision.list_photos.<platform>` — outer agent tool call.
- `vision.inspect_photo.<platform>` — outer turn invoking inspect; result
  preview includes inner findings JSON.
- `vision.inspector.<platform>` — child event of `inspect_photo`; the inner
  VLM call itself.
- `vision.note_gap.<platform>` — agent flagged an evidence gap.
- `vision.final_assessment.<platform>` — terminator.
- `vision.budget_exceeded.<platform>` — cap hit.
- `vision_score.aggregate` — set-based rank aggregation across the 23-listing set.
- `composite_score.compute` — blend of rule_score and visual_score.

Parent/child events are linked via `event_id` / `parent_event_id`. The inner
inspector is always a child of the outer tool call that triggered it.

---

## 11. Caching

Two layers. Both on-disk under `runs/.cache/vision/`.

| Layer  | Cached?     | Key                                                | Value           |
|--------|-------------|----------------------------------------------------|-----------------|
| Inner  | yes         | `sha256(prompt_version + photo_sha256)`            | findings JSON   |
| Outer  | no          | n/a                                                | n/a             |

**Why not cache outer:** the outer agent's growing message history is a poor
cache key, hit rate would be near zero, and we want re-runs to actually
re-exercise the agent's decision-making for E5 determinism.

**Cache invalidation:** prompt_version is a constant in code; bumping it
invalidates the inner cache. Photo content changes → new SHA-256 → new key,
old entries become orphaned (cleaned by a separate vacuum script if size
grows; not in scope for v1).

`--vision-no-cache` flag bypasses the inner cache for E5 cold-cache runs.

---

## 12. Eval additions

| Eval               | Scope                                                            | What it measures                                                                                       |
|--------------------|------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| **vision gold**    | all 23 listings × 5 aspects, hand-labeled by user                | ground truth for E6 + α calibration                                                                    |
| **E6** (new)       | full 23, exact + adjacent + Cohen's κ per aspect per platform    | agent quality vs gold                                                                                  |
| **E3** (extended)  | 23 listings, three-way Spearman: rule / gold-visual / agent-visual | how the rubric, the photos, and the agent agree on ranking                                            |
| **E4** (extended)  | weights × α joint sensitivity sweep                              | rank stability under combined perturbation                                                             |
| **E5** (extended)  | 5 listings × 3 cold-cache runs                                   | vision determinism: exact agreement, adjacent (±1), score range; targets ≥ 0.7, ≥ 0.85, < 5pt range  |

### 12.1 Vision gold format

`eval/vision_gold.jsonl`, one row per fixture:

```jsonl
{"listing_id": "27723929", "platform": "spinny", "vision_gold": {
    "exterior_panels": "light_wear",
    "interior_cabin":  "pristine",
    "dashboard_console": "pristine",
    "tyres":           "moderate",
    "engine_bay":      "light_wear"
}, "notes": {"tyres": "rear-left tread visibly low"}}
```

Header comment lists the allowed severity values and the optional `notes` shape.

### 12.2 Labeling support tooling

`scripts/build_vision_gold_template.py` produces the empty template with all 23
fixtures pre-populated as `null`s, and writes
`eval/vision_gold.anchors.md` — a small reference doc with one or two example
photos at each severity level (drawn from the dataset itself) so the user has
calibration anchors before starting. Reduces severity-drift across the
labeling session.

The script does **not** auto-fill severities. Hand-labeling is the eval; any
auto-fill defeats it.

### 12.3 E6 — agent vs gold

Per aspect, per platform, computed in `src/ci/eval/vision_agreement.py`:

- **Exact agreement**: `(agent == gold)` rate.
- **Adjacent agreement**: `abs(agent_severity_int - gold_severity_int) ≤ 1`
  rate.
- **Cohen's κ**: ordinal κ on the 5-level wear scale (treat `not_visible` as a
  separate "missing" category for the kappa or restrict to mutually-visible
  rows; both computed and reported).

### 12.4 E5 — vision determinism (cold-cache)

`src/ci/eval/vision_determinism.py`. 5 listings × 3 runs with
`--vision-no-cache`. Per aspect and per listing:

- Exact agreement across all 3 runs.
- Adjacent agreement across all 3 runs.
- Per-listing visual_score range = `max(score) − min(score)`.

Acceptance thresholds: exact ≥ 0.7, adjacent ≥ 0.85, range < 5 points.

### 12.5 E3 — three-way cross-method

Extends existing cross-method eval. For all 23 listings, compute:

- `rule_rank` (existing, from `score_common`).
- `gold_visual_rank` (NEW, from gold-derived `visual_score`).
- `agent_visual_rank` (NEW, from agent-derived `visual_score`).

Pairwise Spearman ρ, scatterplot triptych, top-divergence-listings table in
the appendix.

### 12.6 E4 — weights × α joint sweep

α ∈ {0.5, 0.6, 0.7, 0.8, 0.9, 1.0}. Existing weight perturbations applied
within `rule_score`. Report rank-stability of the top-5 listings under joint
perturbation.

---

## 13. Reporting

### 13.1 README ranking table

Columns:

```
rank | listing_id | platform | price | rule_score | visual_score | composite_score | ratio | imputed
```

`ratio = price / composite_score`. When `--no-vision` is used,
`visual_score` and `composite_score` are blanked and `ratio = price /
rule_score` (today's behavior).

### 13.2 Technical appendix — new section

`docs/technical_appendix.md` gains a "Vision agent topology" section:

1. **Topology diagram**: outer agent → tools → inner inspector. Mermaid.
2. **Tool semantics**: table from §5.1.
3. **Worked example**: full agent trace for one listing (every tool call, every
   finding, every gap), pulled from a real run.
4. **Per-listing visual scores**: table with per-aspect breakdown and imputed
   aspects.
5. **E6 per-aspect κ**: agent vs gold table, per platform.
6. **E5 determinism**: stability table.
7. **E3 three-way**: Spearman matrix + scatter triptych.
8. **E4 α-sweep**: rank-stability under joint perturbation.
9. **Symmetry caveat**: explicit note that visual_score measures
   *platform-mediated visual evidence* (showroom-style vs inspection-style),
   not vehicle truth. Per-aspect rank-norm + median imputation help; do not
   eliminate.
10. **Divergence transparency table**: top-5 listings where `rule_score` and
    `visual_score` diverge most. Annotation only — not a primary deliverable.

---

## 14. Cost and latency budget

Estimated for 23 fixtures, claude-sonnet-4-6, with prompt caching on system
prompt + tool definitions.

| Component                  | Calls         | Tokens (approx) |
|----------------------------|---------------|-----------------|
| Outer agent (23 × ~6 turns) | ~138          | ~70K total      |
| Inner inspector (115)       | ~115          | ~265K total     |
| **Baseline first run**      |               | **~$3.50**      |
| Determinism re-runs (15)    | +30 outer +25 inner | +~$0.50 |
| **Subsequent runs (cached)**|               | **~$0.50**      |

**Latency target:** under 2 minutes for the full 23-listing vision phase, with
`asyncio.gather` parallelizing across listings and sequential within a listing.

---

## 15. CLI flags

```
--no-vision              skip the vision agent; pipeline is purely deterministic
--vision-no-cache        bypass the inner cache (used by E5 cold-cache runs)
--vision-listings <ids>  comma-separated listing-id subset (debug / cost-cap)
--vision-budget <n>      override max inspect_photo calls per listing (default 10)
```

---

## 16. Out of scope (explicit)

- Outer-agent caching.
- Photo-fraud heuristics beyond what severity classification captures.
- Per-wheel tyre granularity.
- Cross-VLM ensemble.
- Real-time / streaming inference.
- Photo deduplication smarter than SHA-256 byte equality (perceptual hashing).
- Vacuum / cache eviction tooling.

---

## 17. Approval and next step

This design has been reviewed and approved in conversation. Next step: invoke
the `writing-plans` skill to produce the implementation plan covering:

1. Photo capture script + extractor URL-list helpers.
2. Schema additions and trace-schema extension.
3. Inner inspector and outer agent loop.
4. Inner cache.
5. Vision-score aggregation reusing `_per_dim_scores` patterns.
6. Composite score + RankRow + report changes.
7. Vision-gold template builder + anchors doc.
8. E3, E4, E5, E6 eval additions.
9. Technical appendix updates.
10. Tests and CLI flags.
