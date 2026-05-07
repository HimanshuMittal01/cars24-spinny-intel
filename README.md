# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 listings ranked, 3 per platform; 10 gold listings used for evaluation.

## Why this scope

Ranking only makes sense between comparable cars. *Competitive intel* asks "which platform prices better?" — a BMW-vs-Mercedes comparison can't answer that. *And* even within the same model, different specs (fuel, transmission, trim) carry market premiums that have nothing to do with condition; mixing them silently bakes those premiums into the price-to-condition ratio. Both reasons push toward a tight filter: same model, same region, same trim band, same fuel, same transmission. We then score on the remaining quantitative dimensions (km, age, owners, accident).

## Ranking

Sorted by composite_score descending. Lower ratio = more car for your money.

**Composite formula:** `composite_score = α × rule_score + (1−α) × visual_score`, α = 0.7 (rule-leaning). Rule score is based on km, age, owners, and accident disclosure. Visual score comes from the vision agent's per-aspect condition assessments. For the 3 Cars24 listings the agent returned `not_visible` for all 5 visual aspects; their visual_score is median-imputed (43.75, the median of the 3 Spinny visual scores) rather than agent-observed — Spinny visual is real signal, Cars24 visual is not.

| rank | listing_id | platform | price (₹L) | rule_score | visual_score | composite_score | ratio (₹/pt) | imputed_aspects |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | 28476005 | spinny | 13.47 | 73.50 | 55.00 | 67.95 | 19,823 | — |
| 2 | 10067090111 | cars24 | 10.80 | 62.50 | 43.75 | 56.88 | 18,987 | all 5 (imputed) |
| 3 | 10096166769 | cars24 | 7.00 | 44.67 | 43.75 | 44.39 | 15,778 | all 5 (imputed) |
| 4 | 27839393 | spinny | 9.87 | 41.17 | 35.00 | 39.32 | 25,102 | — |
| 5 | 10126364760 | cars24 | 5.09 | 34.17 | 43.75 | 37.04 | 13,734 | all 5 (imputed) |
| 6 | 28198885 | spinny | 7.47 | 37.67 | 31.25 | 35.74 | 20,901 | — |

ratio = price / composite_score. Because Cars24 visual_score is median-imputed, the composite ranking for Cars24 listings is effectively driven by rule_score alone; cross-platform ratio comparisons should be read with that asymmetry in mind.

![ranking](docs/figures/ranking.png)

## How condition is scored

We score on the four fields **both** Cars24 and Spinny expose for every listing (anything else would advantage the more verbose platform on data quantity rather than on car condition).

| Feature | Why it matters | Weight |
|---|---|---:|
| Kilometres driven | Strongest single predictor of mechanical wear and resale value | 35% |
| Age (years) | Wear is roughly time-driven; affects warranty and parts availability | 25% |
| Number of prior owners | More owners = more variability in maintenance history; first-owner cars carry a market premium | 25% |
| Accident disclosed | Safety / structural signal; weighted lower because the data is coarse (usually yes/no, not severity) | 15% |

For each of the four features, we **rank the 6 cars among themselves** — the best gets 100, the worst gets 0, the rest fall in between by their position. Then we combine the per-feature scores using the weights above to get the condition score.

The score is **relative to the cars in this comparison set**. Adding more cars or swapping one out would shift each car's rank position and therefore its score. The ranking is meaningful as a comparison of *these six*, not as an absolute condition rating.

## How we know the ranking holds up

Before producing the ranking we built a small evaluation harness and ran it against a hand-labeled gold dataset of **10 separate listings (5 Cars24 + 5 Spinny)** — all matching the same SX-petrol-automatic filter, all distinct from the 6 listings being ranked above. Statistical caveat at N=10: small-N metrics are noisy; treat individual numbers as directional, not precise. Full methodology and per-experiment tables are in [`docs/technical_appendix.md`](docs/technical_appendix.md).

- **Faithfulness check.** Extraction recall is **1.0 across all four score-bearing fields (price, km_driven, age_years, owners), on both Cars24 and Spinny.** The extractor matched our hand-labeled values on every field, on every listing.
- **Calibration note.** The gold's rule scores are defined as the scorer's own output on the 10-listing set. System-vs-gold MAE and Spearman are therefore trivially 0 and 1 by construction. Calibration figures are omitted.
- **Stability check.** We perturbed each of the four weights ±25% (one at a time, 8 variants) and re-ran on the gold. **The ordering was substantially preserved** (τ range 0.689–0.956) — small weight choices don't flip the ranking.
- **Dominance check.** We dropped each feature in turn and re-ran on the gold. **km_driven is the most influential dimension by a large margin** (LOO τ = 0.022 — nearly full rank shuffle when removed). age_years is secondary (LOO τ = 0.156), owners tertiary (LOO τ = 0.556). Accident-disclosed contributes effectively no signal in this data (LOO τ = 0.956) — none of the listings in the sample reported accidents.

### Evaluation results

**E6 — vision-agent agreement with hand-labeled gold (N=10, Spinny listings only for visual):** Adjacent agreement is 1.0 across all 5 visual aspects (exterior_panels, interior_cabin, dashboard_console, tyres, engine_bay) — the agent is always within ±1 ordinal step of the human label. Exact agreement ranges from 0.25 to 1.0 per aspect; Cohen's κ is low (0.0–1.0, pooled small) because the gold labels are homogeneous (predominantly pristine and light_wear), leaving little variance for κ to reward. The pattern of 4 of 5 Cars24 gold listings returning all-`not_visible` assessments confirms the systematic timing-out issue on Cars24's larger photo manifests; this is a known implementation limit and not fixed in the current demo scope.

**E4 — α-sweep ranking stability:** Kendall τ ≥ 0.91 when comparing the composite ranking produced at every α ∈ {0.5, 0.6, 0.8, 0.9, 1.0} against the α=0.7 baseline. The top listing is identical across all α values. The composite ranking is robust to the rule/visual weighting choice within the tested range.

**E3 — rule vs visual independence:** Spearman ρ between rule_score and gold-labeled visual_score on the 10-listing gold set is 0.51 — moderate correlation, not near 1. Vision adds genuinely independent condition signal rather than merely echoing the rule score. Agent-recovered visual ordering correlates with gold-visual at ρ ≈ 0.44, imperfect at small N but directionally consistent.

## Caveats

- **N=6 is illustrative, not statistically defensible.** Conclusions about platforms shouldn't rest on this alone.
- **Public data only.** With auth/API access we'd use Spinny's 200-point inspection report and Cars24's deeper in-app fields. The fair comparison given pre-auth data is on the fields both platforms expose.
- **Trim line still spans SX / SX PLUS / SX (O).** These are different sub-trims of the SX family with their own MSRP differences. Tightening to a single sub-trim would shrink supply below the 16 listings (6 ranking + 10 gold) we needed; the SX-line filter is the closest workable compromise.
- **Rank-based scoring is set-relative.** A score of 70 means roughly rank 2.6 of 6 *in this set*, not "this car is in 70% condition" in any absolute sense.

## Further reading

- [`docs/extraction_review.md`](docs/extraction_review.md) — every listing collected (ranking, gold, excluded), with source URLs and parsed values.
- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature ranks, pairwise win matrices, full eval numbers (E3, E4, E6), corpus-scale view.
- [`docs/loom_walkthrough.md`](docs/loom_walkthrough.md) — screen-recorded walkthrough of the pipeline end-to-end.
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal.
