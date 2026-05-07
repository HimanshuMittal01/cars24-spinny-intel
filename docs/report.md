# Cars24 vs Spinny — Competitive Intel Report

## 1. Ranking (price-to-condition)

| # | listing | platform | price (₹) | score_common | ratio | disclosure_count | imputed dims |
|---|---------|----------|-----------|--------------|-------|------------------|--------------|
| 1 | `10096166769` | cars24 | 700,389 | 80.8 | 8,674 | 4 | — |
| 2 | `10076268734` | cars24 | 764,000 | 80.8 | 9,461 | 4 | — |
| 3 | `28198885` | spinny | 747,000 | 75.5 | 9,894 | 12 | — |
| 4 | `10041693110` | cars24 | 950,000 | 74.5 | 12,752 | 4 | — |
| 5 | `27839393` | spinny | 987,000 | 75.5 | 13,073 | 11 | — |
| 6 | `28476005` | spinny | 1,347,000 | 91.0 | 14,802 | 12 | — |

![ranking chart](figures/ranking.png)

## 2. Agent topology

Single explicit DAG, synchronous. Per-platform extractor agents (cars24, spinny) parse the platform's structured JSON payload (Cars24: `__next_f` streaming SSR; Spinny: `window.__INITIAL_STATE__`) and emit a common `RawListing`. The normalizer maps platform-specific raw fields to a common schema. Scoring and ranking are deterministic so the audit trail is auditable end-to-end. The trace store records every node call (input hash, output hash, latency, model, prompt version).

```
snapshots → extract.cars24 / extract.spinny → normalize → score → rank → report
```

Choosing deterministic scoring (rather than an LLM-as-judge second method) preserves auditability and lets the eval harness §3 rely on byte-identical re-runs. Per spec §13, certification is excluded from the common-set ranking score because Cars24 has no per-listing tier; the per-listing tier asymmetry is captured by `disclosure_count` instead.

## 3. Eval harness

### E2 Extraction quality
- field_recall: `{}`

### E3 Calibration vs gold
- MAE: `nan`
- Spearman ρ: `nan`
- Reported as directional, not significant — gold N is small (≈15).

### E4 Weight sensitivity
- τ under ±25% perturbations: `{'km_driven+': 0.9999999999999999, 'km_driven-': 0.9999999999999999, 'age_years+': 0.9999999999999999, 'age_years-': 0.9999999999999999, 'owners+': 0.9999999999999999, 'owners-': 0.9999999999999999, 'accident_disclosed+': 0.9999999999999999, 'accident_disclosed-': 0.9999999999999999}`
- τ under leave-one-dim-out: `{'km_driven': 0.7333333333333333, 'age_years': 0.9999999999999999, 'owners': 0.9999999999999999, 'accident_disclosed': 0.9999999999999999}`
- Claim: the ranking is stable under reasonable weight perturbations. Does *not* claim the weights are correct — the priors are not data-derived (see Limitations).

### E5 Determinism spot-check
- identical across reps: `True` (distinct outputs: 1)

## 4. The tradeoff that bit

# Tradeoffs Journal

Append entries during build. Each entry: situation → decision → alternative
considered → what hurt. The "tradeoff that bit" answer in the report is
selected from here at report time.

---

## 2026-05-07 — speculative schema vs real data

**Situation.** Drafted Cars24 / Spinny extractor schemas based on prior assumptions
about what each platform exposes (Cars24 "Imperial / Royal Blue" tiers, per-listing
accident disclosure, generic 200-pt inspection on Spinny).

**Decision.** Pulled one real listing from each platform mid-build, discovered the
schemas were largely fictional, and pivoted: dropped certification from the
common-set, single 4-dim weights table, JSON-parse-first extraction (Next.js
streaming for Cars24, `window.__INITIAL_STATE__` for Spinny), revised disclosure
field list to 17 fields based on observed pre-auth data.

**Alternative considered.** Stay with LLM-as-extractor on raw HTML and let
hallucination rates surface in E2. Rejected: structured JSON is right there in
both pages; using an LLM to pull structured data out of structured data is the
wrong tool, costs more, and adds noise into a pipeline whose value is auditability.

**What hurt.** ~3 tasks of work (T2/T8/T9) were fully rewritten. The plan and
spec gained a "Reality Check (§13)" amendment. But the rework forced an honest
reckoning with the real Cars24 vs Spinny disclosure asymmetry — Cars24 has no
per-listing tier, only a uniform platform promise — which became *the* headline
finding rather than a plausible hypothesis.


## 5. Limitations

- N=6 ranking; conclusions are illustrative.
- Gold N≈15; calibration confidence intervals are wide. Read directional, not significant.
- Rubric weights are reasonable priors, not grounded in external data. E4 only proves robustness, not groundedness.
- `disclosure_count` measures presence, not depth-of-disclosure (a single boolean disclosure counts the same as detailed exposure).
- Snapshots are point-in-time; results apply to the captured state of each listing.
- Single annotator on gold (no inter-rater data).
- Cars24 'no_accident_history' platform-level promise is mapped to per-listing `accident_disclosed = none`. This is documented in spec §13 and should be read as a *modelling choice* rather than a per-listing extraction.
