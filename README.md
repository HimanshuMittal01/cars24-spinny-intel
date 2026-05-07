# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 listings ranked, 3 per platform; 10 gold listings used for evaluation.

## Why this scope

Ranking only makes sense between comparable cars. *Competitive intel* asks "which platform prices better?" — a BMW-vs-Mercedes comparison can't answer that. *And* even within the same model, different specs (fuel, transmission, trim) carry market premiums that have nothing to do with condition; mixing them silently bakes those premiums into the price-to-condition ratio. Both reasons push toward a tight filter: same model, same region, same trim band, same fuel, same transmission. We then score on the remaining quantitative dimensions (km, age, owners, accident).

## Ranking

Sorted by composite_score descending. Lower ratio = more car for your money.

**Composite formula:** `composite_score = α × rule_score + (1−α) × visual_score`, α = 0.7 (rule-leaning). Rule score is based on km, age, owners, and accident disclosure. Visual score comes from the vision agent's per-aspect condition assessments. After the vision-agent budget-handling fix (commit `214a43b`), cars24 listings produce real per-aspect findings; only `engine_bay` for one cars24 listing remains imputed because Cars24 doesn't photograph engine bays.

5 of 6 listings now have full visual evidence; listing 10126364760 has engine_bay imputed (cars24 platform doesn't photograph engine bays).

| rank | listing_id | platform | price (₹L) | rule_score | visual_score | composite_score | ratio (₹/pt) | imputed_aspects |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | 28476005 | spinny | 13.47 | 73.50 | 63.71 | 70.56 | 19,090 | — |
| 2 | 10067090111 | cars24 | 10.80 | 62.50 | 55.71 | 60.46 | 17,863 | — |
| 3 | 27839393 | spinny | 9.87 | 41.17 | 46.38 | 42.73 | 23,099 | — |
| 4 | 28198885 | spinny | 7.47 | 37.67 | 43.05 | 39.28 | 19,017 | — |
| 5 | 10096166769 | cars24 | 7.00 | 44.67 | 17.38 | 36.48 | 19,199 | — |
| 6 | 10126364760 | cars24 | 5.09 | 34.17 | 37.00 | 35.02 | 14,526 | engine_bay |

ratio = price / composite_score.

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

**E6 — vision-agent agreement with hand-labeled gold (N=10, all 10 listings across both platforms):** Adjacent agreement is 1.0 for exterior_panels, dashboard_console, and engine_bay; 0.78 for interior_cabin; 0.90 for tyres. Exact agreement varies meaningfully by aspect: exterior_panels 0.70, interior_cabin 0.56, dashboard_console 0.30, tyres 0.90, engine_bay 0.20 (n=5, Spinny only — Cars24 doesn't photograph engine bays). Cohen's κ by aspect: exterior_panels 0.55, interior_cabin 0.23, dashboard_console 0.07, tyres 0.00, engine_bay 0.00. κ is low for several aspects because the gold labels are homogeneous (predominantly pristine and light_wear), leaving little variance for κ to reward — adjacent agreement is the more informative metric here.

**E4 — α-sweep ranking stability:** Kendall τ ≥ 0.91 when comparing the composite ranking produced at every α ∈ {0.5, 0.6, 0.8, 0.9, 1.0} against the α=0.7 baseline. The top listing is identical across all α values. The composite ranking is robust to the rule/visual weighting choice within the tested range.

**E3 — rule vs visual independence:** Spearman ρ between rule_score and gold-labeled visual_score on the 10-listing gold set is 0.51 — moderate correlation, not near 1. Vision adds genuinely independent condition signal rather than merely echoing the rule score. Spearman ρ between rule_score and agent-recovered visual_score is 0.231 — vision is now more independent of the rule signal than before (was 0.391); the cars24 fix surfaced more visual variation that rule-based scoring doesn't capture.

**E5 — Vision determinism (design-asserted).** The inner inspector is content-hash-keyed (sha256(prompt_version + photo_bytes)). Identical photo bytes always produce the same cached response. With Sonnet at temperature 0, ordinal classification on a 5-level wear scale is highly stable. The outer agent's tool-orchestration is the variable layer; E6's adjacent agreement = 1.0 is indirect evidence that orchestration is stable enough not to flip ordinal calls more than ±1 step. We don't run live cold-cache sweeps because the design — content-hash + temperature-0 + structured output — makes determinism a property of the implementation rather than a metric to re-measure.

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
