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

---

## 2026-05-07 — gold labeling on a deterministic JSON pipeline (E3 caveat)

**Situation.** Acted as honest annotator for all 6 ranking listings: read the
fixture HTML directly via independent regex extraction (separate from the
extractor's parser), hand-applied the rubric anchored bands, computed
score_common per listing, wrote per-dim notes citing what was visible.

**Result.** Gold values match system extractor values exactly. E2 field recall
is 1.0 across all dims, both platforms. E3 calibration MAE = 0.0, Spearman ρ
= 1.0.

**Why this is unsurprising and what it means.** Both platforms inject their
canonical listing data as inline JSON (`__next_f` payloads on Cars24,
`window.__INITIAL_STATE__` on Spinny). The deterministic extractor parses that
JSON; an honest annotator reading the same page sees the same JSON-derived
values. The rubric is then mechanical (anchored bands + weighted sum) — gold
score by construction equals system score. **E3 is acting as a self-consistency
check, not an independent calibration.**

**What this evidences.** Extraction faithfulness is structurally guaranteed for
the fields we care about (price/km/year/owners), modulo the JSON's truthfulness.
There is no extraction noise to measure here — the only failure mode would be
the JSON parser itself, which E5 (determinism) catches.

**What we'd actually need for an independent E3.** Either (a) a *holistic*
human gold score per listing (gut-rated 0-100 without using the formula) — would
test whether the rubric tracks what a thoughtful buyer feels, or (b) gold from
a third-party valuation source (OBV, CarWale) — would test whether the rubric
tracks revealed market judgments. Out of scope for this run; documented as a
limitation.

**Why we still ran E2/E3.** They confirm the pipeline doesn't drift over time
or across runs, and the per-platform breakdown surfaces if one extractor
silently degrades while the other stays correct. Their *current* values are
unsurprising; their *future* values would matter if either platform changes the
shape of its inline JSON.

---

## 2026-05-07 — anchored bands → rank-based scoring (spec §14)

**Situation.** Original scorer used hand-picked anchored-band tables
(`<20k km = 100`, `20-40k = 85`, …). Defensible only via sensitivity analysis
("ranking is robust to ±25% weight perturbations"). Bands themselves
ungroundable. Reviewer challenge from a brainstorm: pairwise comparison or
rank-based scoring would eliminate the band-cutoff prior entirely.

**Decision.** Replaced bands with rank-based per-feature scoring. For each
dimension, listings ranked among themselves; rank position → 0-100 score by
linear interpolation. Composite is the same weight-sum. Set-based scorer API
(`score_listings(listings)` instead of `score_listing(n)`).

**Alternative considered.** Pure pairwise binary (1/0 per pair per feature,
sum to feature-rank, weight-sum). Rejected as too lossy — landslide and narrow
wins counted equally. Rank-based is mathematically a smoothed pairwise
(average of pairwise wins × 2 / (n-1) × 100) but preserves some magnitude
through linear interpolation.

**What hurt.** Real rework: scorer/pipeline/sensitivity all changed APIs.
~half a day of focused work. Tests rewritten. Spec gained §14.

**What it bought.** The "where do these bands come from?" question is gone.
The score is now defensible by construction — no priors to defend on the
band side; only weights remain a prior, and E4 perturbation handles them.
Per-feature ranks become first-class exhibits (technical appendix), which is
real interpretability. **The ranking itself shifted** — rank-based amplifies
relative differences within the set, so the 2022 Spinny (best condition by a
clear margin within the 6) jumped from rank 6 to rank 2, and a 2019 Cars24
(low absolute condition but cheap) dropped from rank 1 to rank 3. The new
ranking is more defensible but the magnitudes shifted noticeably — flagged in
the limitations.

**Eval-side observation that fell out.** With magnitude removed from the
scorer, E4 leave-one-out τ became more sensitive. **km_driven removal drops
τ to 0.33** (from 0.73 under bands). km is the load-bearing feature in this
ranking — a real finding that band-based smoothing was hiding. Now surfaced
in the report and appendix.
