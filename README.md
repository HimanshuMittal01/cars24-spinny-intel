# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 listings ranked, 3 per platform; 10 gold listings used for evaluation (reduced from 17; see note below).

## Why this scope

Ranking only makes sense between comparable cars. *Competitive intel* asks "which platform prices better?" — a BMW-vs-Mercedes comparison can't answer that. *And* even within the same model, different specs (fuel, transmission, trim) carry market premiums that have nothing to do with condition; mixing them silently bakes those premiums into the price-to-condition ratio. Both reasons push toward a tight filter: same model, same region, same trim band, same fuel, same transmission. We then score on the remaining quantitative dimensions (km, age, owners, accident).

## Ranking

Lower ₹ per condition-point = more car for your money.

| # | listing | platform | price | condition score | ₹ per condition-point |
|---|---|---|---:|---:|---:|
| 1 | 10096166769 | cars24 | 7.00L | 48.5 | **14,441** |
| 2 | 10126364760 | cars24 | 5.09L | 34.0 | 14,962 |
| 3 | 10067090111 | cars24 | 10.80L | 68.0 | 15,882 |
| 4 | 28476005 | spinny | 13.47L | 80.0 | 16,838 |
| 5 | 28198885 | spinny | 7.47L | 34.5 | 21,652 |
| 6 | 27839393 | spinny | 9.87L | 35.0 | 28,200 |

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

Before producing the ranking we built a small evaluation harness and ran it against a hand-labeled gold dataset of **10 separate listings (5 Cars24 + 5 Spinny)** — all matching the same SX-petrol-automatic filter, all distinct from the 6 listings being ranked above.

**Gold set note:** The gold set was reduced from 17 to 10 listings to support the vision-agent calibration (see [vision-agent design](docs/superpowers/specs/2026-05-07-vision-agent-design.md) §12.0). The 7 dropped listings remain on disk as archive but no longer feed `eval/gold.jsonl`. Statistical caveat at N=10: small-N metrics are noisy; treat individual numbers as directional, not precise.

- **Faithfulness check.** Extraction recall is **1.0 across all four score-bearing fields (price, km_driven, age_years, owners), on both Cars24 and Spinny.** The extractor matched our hand-labeled values on every field, on every listing.
- **Calibration note.** The gold's `score_common` values are defined as the scorer's own output on the 10-listing set (spec §14 algorithm). System-vs-gold MAE and Spearman are therefore not informative measures of calibration — they are trivially 0 and 1 by construction. Calibration figures are omitted.
- **Stability check.** We perturbed each of the four weights ±25% (one at a time, 8 variants) and re-ran on the gold. **The ordering was substantially preserved** (τ range 0.689–0.956) — small weight choices don't flip the ranking.
- **Dominance check.** We dropped each feature in turn and re-ran on the gold. **km_driven is the most influential dimension by a large margin** (LOO τ = 0.022 — nearly full rank shuffle when removed). age_years is secondary (LOO τ = 0.156), owners tertiary (LOO τ = 0.556). Accident-disclosed contributes effectively no signal in this data (LOO τ = 0.956) — none of the listings in the sample reported accidents.

## Caveats

- **N=6 is illustrative, not statistically defensible.** Conclusions about platforms shouldn't rest on this alone.
- **Public data only.** With auth/API access we'd use Spinny's 200-point inspection report and Cars24's deeper in-app fields. The fair comparison given pre-auth data is on the fields both platforms expose.
- **Trim line still spans SX / SX PLUS / SX (O).** These are different sub-trims of the SX family with their own MSRP differences. Tightening to a single sub-trim would shrink supply below the 6 + 17 we needed; the SX-line filter is the closest workable compromise.
- **Rank-based scoring is set-relative.** A score of 70 means roughly rank 2.6 of 6 *in this set*, not "this car is in 70% condition" in any absolute sense.

## Further reading

- [`docs/extraction_review.md`](docs/extraction_review.md) — every listing collected (ranking, gold, excluded), with source URLs and parsed values.
- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature ranks, pairwise win matrices, full eval numbers, corpus-scale view.
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal.
