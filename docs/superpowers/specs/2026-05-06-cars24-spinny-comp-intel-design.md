# Cars24 vs Spinny — Multi-Agent Competitive Intel — Design Spec

**Date:** 2026-05-06
**Author:** himanshu.mittal.dev@gmail.com
**Status:** v1, approved for implementation planning

---

## 1. Brief

> Build a multi-agent system for competitive intel. Pick 3 used-car listings on Cars24 and 3 on Spinny. Agents extract specs, condition, price. Rank all 6 on price-to-condition. Walk me through your agent topology, the eval harness (not just the result), and one engineering tradeoff that bit you.

### Hidden assumption in the brief

Neither platform exposes a numeric condition scalar. Cars24 surfaces tiered certification (e.g. Imperial / Royal Blue) plus categorical inspection results. Spinny surfaces a "Spinny Assured" badge and a 200-point inspection. **We must construct the condition score.** This construction is the methodological centerpiece.

### Headline finding (anticipated)

The two platforms expose materially different amounts of per-listing detail pre-auth. This data-disclosure asymmetry is itself a positioning signal — Spinny sells process / thoroughness, Cars24 sells curated tiers — and it forces an explicit choice about *fairness* in cross-platform ranking.

---

## 2. Scope

### Listings
- **6 ranking listings**: 3 Cars24 + 3 Spinny.
- Make/model/segment: **Hyundai Creta**, used.
- Region: **Delhi-NCR**.
- Price band: **₹8L – ₹14L** (covers approximately 2018–2022 mid trims; thick supply on both platforms).
- Single segment chosen so the price-to-condition ratio is comparable. Cross-segment ratios are meaningless.

### Gold dataset
- **~15 listings hand-labeled** (8 Cars24 / 7 Spinny), same filters.
- Hand-labeled by author against the rubric defined in §4.
- Single pass (no two-pass intra-rater check; cost not justified at this N).
- Per-dimension structured notes, not free text — reduces drift.

### Data acquisition
- **Public-only, no signup.** What each platform exposes pre-auth is itself part of what we are measuring.
- Snapshots saved to `/fixtures/<platform>/<listing_id>/{page.html, raw.json, captured_at.txt}`.
- All eval runs replay from snapshots. **No live scraping during eval.**

---

## 3. Common field set

This set is **locked before labeling begins**. It defines what the ranking score is built from. Drift here = noise we cannot recover from.

### Tentative common set

```
make, model, variant, year, km_driven, owners, registration_state,
fuel, transmission, body_color, price, certification_flag
```

### Conditional addition

```
accident_disclosed   # added to common set IF both platforms expose
                     # this field on the large majority of dataset
                     # listings (target: ≥90%). Verified during
                     # snapshot collection. Below threshold → drop
                     # from common set.
```

### Common-set locking process

The common set is **finalized after a first-pass snapshot pull**, not before. Process:

1. Pull HTML for all 6 ranking listings + 15 gold listings.
2. Inspect what fields each platform exposes.
3. Pick the common set so nulls are *rare* (target: <10% across the dataset for each chosen field).
4. Lock the set. Label gold against the locked set.

This way, null handling at scoring time is a corner case (handled by imputation, see §4), not the common case.

### Full schema (extracted, not used in ranking)

In addition to common fields, the extractor captures whatever the listing exposes — inspection issue lists, service history, NOC status, cosmetic notes, warranty terms, etc. These feed the disclosure metric (§4) and the report's qualitative observations.

### Null handling (summary)

- **Common fields:** chosen so nulls are rare; rare-case nulls are handled by per-dim imputation anchors (§4), not rebalancing or raising.
- **Disclosure-eligible / full-schema fields:** null is expected and meaningful — it is exactly what `disclosure_count` measures.

---

## 4. Condition rubric v1

### Single score per listing

**`score_common` (0-100)** — the only score. Used for ranking. Built only from the locked common field set. Same fields, same weights, same anchors for both platforms. This is the score that goes into the price-to-condition ratio.

There is no parallel `score_full`. Earlier drafts proposed a diagnostic full-info score; we dropped it because (a) its weights are not gold-validated and would need separate defense, and (b) the disclosure-asymmetry signal it was meant to surface is captured more cleanly by the disclosure metric below.

### Ranking inputs (explicit)

The ranking is computed as `ratio = price / score_common` and sorted ascending.

- **`price`** and **`score_common`** are the *only* inputs to the ranking.
- **`disclosure_count`** is a descriptive metric. It is reported in the ranking table (§7) and powers a separate cross-platform observation, but it does **not** enter the ratio or the sort. Mixing it in would conflate "what's exposed" with "what's the condition", which are different questions.

### Single scoring method

LLM-based **extraction** → **deterministic composite** scoring.

- Extraction is LLM-driven because free-text inspection notes and tier descriptions need NLP normalization.
- Scoring is deterministic (anchored bands + weighted sum) because the rubric needs to be auditable, reproducible, and defensible. There is no second LLM-judge method; we have gold to validate against, which removes the need for a methods triangulation.

### Weights — `score_common`

If `accident_disclosed` ends up in the locked common set:

| Dimension | Weight |
|---|---|
| km_driven | 30 |
| age | 20 |
| owners | 20 |
| certification_flag | 15 |
| accident_disclosed | 15 |
| **Total** | **100** |

If `accident_disclosed` is not common (i.e. one platform doesn't expose it):

| Dimension | Weight |
|---|---|
| km_driven | 35 |
| age | 25 |
| owners | 25 |
| certification_flag | 15 |
| **Total** | **100** |

### Null handling — imputation anchors, not rebalancing

A common field that comes back null at runtime is treated by **imputation against a fixed per-dim anchor** — same kind of anchor as the other bands. The dim still contributes its full weight; the imputed value just becomes the "missing" anchor for that dim.

```
km_driven       missing → 60   # most listings expose this; treat as moderate
age             missing → 60   # rarely missing; treat as moderate
owners          missing → 60   # default toward "more than one"
accident_disclosed missing → 60 # uncertainty, neutral-leaning
certification_flag missing → 40 # no badge ≈ uncertified
```

The score is still over 100. Weights are not touched. Listings remain comparable across the dataset because every listing is scored over the same denominator with the same dim coverage.

**Why this is better than rebalancing:** rebalancing across listings makes scores non-comparable — a listing scaled over 4 of 5 dims and one over 5 of 5 are not measuring the same thing. Imputation keeps the rubric uniform.

**Why imputation values aren't 0 or 50:** 0 is a hard penalty that conflates "we don't know" with "it's bad". 50 is the linear-interpolation default which is fine but slightly more pessimistic than the empirical mid-band of most dims. The values above are conservative midpoints chosen to express *moderate uncertainty*; they're priors and exposed as configurable in the rubric file.

**Reporting:** any listing that hit at least one imputation is flagged in the ranking table footnote, so the reader can see which scores are partially imputed. The common set is intentionally chosen (§3) so this footnote is rare.

Nullness in the disclosure-eligible set is a different beast — it is *exactly* what `disclosure_count` measures, and never enters the score.

### Anchored bands (deterministic composite)

```
km_driven:
  <20k = 100,  20-40k = 85,  40-70k = 70,
  70-100k = 55,  100-150k = 40,  >150k = 25

age (years):
  <2 = 100,  2-4 = 85,  4-7 = 65,  7-10 = 45,  >10 = 25

owners:
  1 = 100,  2 = 75,  3 = 50,  4+ = 25

accident_disclosed:
  none = 100,  minor / cosmetic = 70,  major / structural = 30

certification_flag:
  top tier (e.g. Imperial / Royal Blue / Spinny Assured Plus) = 100
  mid tier                                                    = 75
  base / certified                                            = 60
  not certified / unknown                                     = 40
```

These anchors are **reasonable priors, not data-derived**. They are defended via the sensitivity analysis in §6 (E4) — the claim is not "these numbers are correct" but "the ranking is stable under reasonable perturbations of these numbers".

### Disclosure metric

Separate from the score, every listing carries a disclosure metric that captures *how much condition-relevant information the platform exposed pre-auth*. This is what powers the cross-platform positioning observation in the report — replacing the earlier `score_full` vs `score_common` gap.

#### `disclosed_fields[]`

A boolean per field in the **disclosure-eligible set** below. `true` if the listing exposes a non-null value for that field, `false` if not.

#### `disclosure_count`

`int` — count of `true` entries in `disclosed_fields[]`. Range: 0 to `len(disclosure-eligible set)`.

#### Disclosure-eligible field set (locked)

Condition-relevant fields that lie *beyond* the common field set in §3. Each is named explicitly so the metric is auditable.

```
accident_history_detail        # severity / location, not just yes/no
service_history_records        # presence of any service record list
inspection_issue_list          # itemized issue findings
inspection_points_passed       # e.g. "194/200" style
cosmetic_exterior_notes        # specific exterior wear notes
cosmetic_interior_notes        # specific interior wear notes
tire_condition                 # per-tire or aggregate state
engine_remarks                 # engine inspection commentary
transmission_remarks           # transmission inspection commentary
battery_status                 # battery health / age
ac_remarks                     # AC inspection commentary
electrical_remarks             # electrical inspection commentary
previous_use_type              # personal / commercial / taxi
noc_status                     # NOC clear / pending
hypothecation_status           # loan / hypothecation cleared
insurance_status               # insurance type + validity
rc_type                        # original / duplicate
challan_status                 # pending dues / e-challans
warranty_remaining_months      # platform warranty term
inspection_photo_count         # count of inspection photos exposed
```

20 fields. Locked at spec time. Adding or removing a field is a spec amendment, not a runtime decision.

#### Why this is better than `score_full`

- **Grounded, not constructed.** Disclosure is observable: a field is either exposed or not. There is no rubric to defend.
- **Single ablation surface.** Only `score_common` weights need sensitivity testing.
- **Cleaner claim.** "Spinny exposes more condition fields than Cars24" is concrete and falsifiable. "Spinny `score_full` differs more from `score_common`" required readers to trust two sets of weights.

---

## 5. Architecture

Single explicit DAG. Synchronous execution. No framework. Each node has typed Pydantic input/output. Failures raise; no silent fallback.

```
                            ┌────────────────────────────────────┐
                            │         snapshot loader            │
                            │  (reads /fixtures/<platform>/...)  │
                            └─────────────┬──────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  │                                               │
        ┌─────────▼──────────┐                          ┌─────────▼──────────┐
        │ extractor: cars24  │                          │ extractor: spinny  │
        │  (LLM, structured  │                          │  (LLM, structured  │
        │   output schema)   │                          │   output schema)   │
        └─────────┬──────────┘                          └─────────┬──────────┘
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  normalizer            │
                              │  (→ common schema)     │
                              └───────────┬────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  scorer (composite)    │
                              │  produces score_common │
                              │  + disclosure_count    │
                              └───────────┬────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  ranker + analyzer     │
                              │  (price/score_common)  │
                              └───────────┬────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  reporter              │
                              │  (markdown + charts)   │
                              └────────────────────────┘

  trace store: every node writes input_hash, output, model, prompt_version,
               latency_ms, tokens_in, tokens_out, cost — keyed by run_id
```

### Why this shape

- **Per-platform extractor agents** — the brief says "multi-agent". Per-platform is the natural axis: each agent owns its platform's quirks (page structure, vocabulary, certification taxonomy). Extractors share a common output schema enforced by the normalizer.
- **Normalizer as a separate node** — not folded into extractors. Keeps platform-specific extraction prompts focused on faithful capture, and centralizes the schema-conformance check (E2 hallucination rate).
- **Scorer is deterministic and standalone** — no LLM at scoring time. Produces `score_common` from common fields and `disclosure_count` / `disclosed_fields[]` from the full extracted record. Output is byte-identical given the same extracted record, which makes E5 (determinism spot-check) trivial and shifts all non-determinism into extraction (where it can be measured directly).
- **Trace store is the substrate of the eval harness** — every node writes a record. Eval is just queries over this store + the gold file.

---

## 6. Eval harness

Five evals. Each one catches a specific class of failure. Each is queried against the trace store + gold dataset.

### E1 — Gold dataset
- ~15 listings, hand-labeled against the rubric in §4.
- For each listing the gold record contains: full extracted-field values (including the disclosure-eligible fields, with `null` where the listing did not expose them), per-dimension condition notes, and final `score_common`.
- `disclosed_fields[]` and `disclosure_count` are **not labeled separately** — they are computed from the gold's full record by the same function the system applies to its own extractor output. (Labeling them would be redundant.)
- File: `/eval/gold.jsonl`.
- Labeled cold (no LLM-suggested values; avoids contaminating LLM-as-extractor evaluation).

### E2 — Extraction quality
- **Per-field precision / recall** vs gold (string and numeric fields handled separately; numeric uses tolerance bands).
- **Schema conformance**: % of extractions that pass Pydantic validation on the first try.
- **Hallucination rate**: fields present in extractor output but not present in source HTML (sampled manually for 5 listings).
- Reported per-platform (so we can see if one extractor is weaker).

### E3 — Condition score calibration
- **MAE** of `score_common` vs gold `score_common`, per platform and overall.
- **Spearman ρ** between system ranking and gold ranking on the 15-listing set.
- Caveat: at N=15 / N=8 / N=7, confidence intervals are wide. Reported with a "directional, not significant" framing.

### E4 — Weight sensitivity (robustness, not groundedness)
- Scope: only `score_common` weights. There is no `score_full`, and `disclosure_count` is unweighted (just a count over a locked field set), so the ablation surface is small — 4 or 5 dimensions depending on whether `accident_disclosed` ends up common.
- For each dimension weight, perturb by ±25% (one at a time) and recompute the 6-listing ranking. Report Kendall's τ vs the unperturbed ranking.
- Leave-one-dimension-out: drop each dim individually, rescale, re-rank, report τ.
- **What this proves:** the ranking is stable under reasonable weight perturbations.
- **What this does *not* prove:** that the weights are correct. The weights are reasonable priors. There is no calibration target that grounds them — gold scores are themselves rubric-derived (circular), and a holistic-score regression fit on N=15 with 4-5 weights is overfit. Calling sensitivity analysis "grounding" would be overclaim.
- The honest framing in the report: "the ranking is consistent with our priors, and is stable across reasonable variations of those priors". Not "these are the right weights".

### E5 — Determinism spot-check
- One listing, three repetitions of the full pipeline, temp=0.
- Expected: identical extractions, identical scores. If not, that is a bug (not a finding).
- Cheap. Catches structured-output instability and prompt nondeterminism.

### What we deliberately did not include

| Dropped | Reason |
|---|---|
| LLM-as-judge as second scoring method | Gold validates the single method; second method was double-counting evidence |
| Prompt robustness ablation (Kendall's τ on rubric variants) | Luxury at N=6; weight sensitivity (E4) covers the analogous question |
| Formal claim-grounding system (every claim → metric_id) | Overkill for a 5-claim report; will hand-link instead |
| Bootstrap CIs on the 6 ranking | Theatre at N=6; CIs at N=15 reported as directional only |
| Per-platform regression (price ~ condition) | Off-brief; consistent with framing the brief literally |
| Async extraction | 36 sync calls is clearer and fast enough |
| Two-pass intra-rater labeling | Marginal value at N=15 |
| Live scraping during eval | Replay from snapshots — eval must be reproducible |

---

## 7. Reporting

Order follows the brief literally.

1. **The 6-listing ranking** — table (listing, platform, price, score_common, disclosure_count, ratio) plus a small badge per row listing the **top-3 disclosed-only fields** for that listing (i.e. up to 3 of the disclosure-eligible fields that this particular listing exposed; chosen for reader-relevance — accident detail, inspection issue list, service history are typical). A price-vs-condition chart accompanies the table with the 6 points labeled.
2. **Agent topology walkthrough** — DAG diagram from §5 + per-node contract (input schema, output schema, what it owns, what it explicitly does not own).
3. **Eval harness walkthrough** — for each of E1–E5, what failure mode it catches, what the result was, what it told us.
4. **One engineering tradeoff that bit** — drawn from the tradeoffs journal kept during build (`docs/tradeoffs.md`). Concrete, not invented.
5. **Limitations** — N=6, hand-built rubric, snapshot vintage, weight sensitivity bounds.
6. **Methodology appendix** — full rubric, full schema, prompt versions, weight tables, anchored bands.

### Headline observation (expected, not yet validated)

We expect the report to surface that **`disclosure_count` is systematically higher on Spinny than on Cars24** — Spinny exposes more condition-relevant fields pre-auth. The metric is concrete and observable, not a constructed score, so the claim sits on solid ground (modulo the obvious N=6 caveat — the gold N=15 trend should reinforce the same direction). This becomes a one-paragraph competitive observation: the two platforms compete on different axes — process depth (Spinny) vs curation tier (Cars24) — which shows up in *what they show you before you sign in*.

---

## 8. Tech stack

- **Python 3.11+**.
- **`uv`** for env, dependency management, and script running. `pyproject.toml` + `uv.lock` committed.
- **Pydantic v2** for all schemas (extraction, normalized, gold, eval results).
- **Anthropic SDK** with structured output (tool use / response_format) for extraction. Temp=0.
- **Sonnet 4.6** (`claude-sonnet-4-6`) for extraction. No second model.
- Synchronous execution. No async, no LangChain, no agent framework — the DAG is small enough that explicit Python is clearer than abstraction.
- Charts: `matplotlib` (single dependency, output to PNG referenced from the report).
- Trace store: append-only JSONL at `/runs/<run_id>/trace.jsonl`.

---

## 9. Tradeoffs journal

`docs/tradeoffs.md` — append entries during implementation. Each entry: situation, decision, alternative considered, what hurt. The "one tradeoff that bit you" deliverable is selected from this journal at report time, not invented.

---

## 10. Limitations (explicit, in spec)

- **N=6 ranking is illustrative.** Strategic conclusions about platforms cannot rest on 3 listings each.
- **Gold N=15** → calibration confidence intervals are wide. MAE / Spearman reported as directional.
- **Rubric weights are reasonable priors, not grounded in data.** E4 only proves the ranking is *robust* to perturbations of those priors. It does not prove the priors are correct. There is no non-circular calibration available at this scale (gold itself uses the rubric; N=15 is too small for an honest holistic-score regression). All ranking conclusions should be read as "consistent with our priors", not "objectively true".
- **The absolute `score_common` value is not portable** to comparisons outside this rubric. It is valid within this study only.
- **`disclosure_count` is binary per field** — a listing that says "no accident reported" gets the same point as one that publishes full accident severity and photos. The metric counts presence, not depth-of-disclosure. Acceptable for the cross-platform claim we're making, but it's a flat measure.
- **Snapshots are point-in-time.** Listings change; pages change. All findings apply to snapshot vintage as recorded.
- **Single annotator on gold** (the author). No inter-rater data. Two-pass intra-rater check was scoped out as marginal at this N.

---

## 11. Out of scope

- Live scraping or any non-public access path.
- Authentication / signed-in flows.
- Paid valuation APIs or third-party valuation cross-checks.
- Multi-segment ranking (only Hyundai Creta in band).
- Multi-region (only Delhi-NCR).
- Production deployment, monitoring, alerting.
- LLM-as-judge scoring; prompt robustness ablation; bootstrap CIs; per-platform regression; async; intra-rater two-pass — see §6 table for reasons.

---

## 12. Effort allocation (target)

- **40% build** — extraction agents, normalizer, scorer, ranker, trace store, snapshot loader.
- **35% eval** — gold labeling, E1–E5 implementation and runs.
- **25% report** — writing, charts, topology diagram, tradeoff selection.

Brief-literal framing → build slightly more than original 30% allocation. Eval slightly less. Report slightly more (the topology + tradeoff sections need real care, not a paragraph each).
