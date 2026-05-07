# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 ranked, 3 per platform; 17 additional gold listings hand-labeled for eval.

## Why this scope

Ranking only makes sense between comparable cars. *Competitive intel* asks "which platform prices better?" — a BMW-vs-Mercedes comparison can't answer that. And even within the same model, different specs (fuel, transmission, trim) carry market premiums unrelated to condition; mixing them bakes those premiums into the ratio. Both push toward a tight filter — same model, region, trim band, fuel, transmission — and scoring on what's left (km, age, owners, accident).

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

We score on the four fields **both** Cars24 and Spinny expose for every listing (anything else would advantage the more verbose platform on data quantity, not condition).

| Feature | Why it matters | Weight |
|---|---|---:|
| Kilometres driven | Strongest single predictor of mechanical wear | 35% |
| Age (years) | Wear is roughly time-driven; affects warranty and parts | 25% |
| Number of prior owners | First-owner cars carry a market premium; more owners = more variability | 25% |
| Accident disclosed | Coarse safety/structural signal (usually yes/no) | 15% |

For each feature, we **rank the 6 cars among themselves** — best gets 100, worst gets 0, others linearly interpolated by rank. Combine the per-feature scores using the weights above. Ranks come straight from the listings; no thresholds to defend.

## How we know the ranking holds up

Built and ran an eval harness against a hand-labeled gold dataset of **17 listings (7 Cars24 + 10 Spinny)** — all matching the SX-petrol-automatic filter, all distinct from the 6 ranked above.

- **Faithfulness check** *(17 gold listings).* Hand-labeled by reading the source page directly; the extractor matched on every field, both platforms.
- **Stability check** *(6 ranked listings).* Each of the four weights perturbed ±25%, ranking re-run for all 8 variants. Kendall's τ stayed between 0.87 and 1.0.
- **Dominance check** *(6 ranked listings).* Dropping each feature in turn: removing km drops τ to 0.60; others stay 0.73–0.87. km has the strongest single influence, but no feature alone determines the ranking.

## Caveats

- **N=6 is illustrative, not statistically defensible.**
- **Public data only.** With auth/API access we'd use Spinny's 200-point inspection report and Cars24's deeper in-app fields.
- **Trim spans SX / SX PLUS / SX (O).** Tightening to a single sub-trim wouldn't give us enough listings on both platforms; SX-line is the closest workable compromise.
- **Rank-based scoring is set-relative.** A score of 70 means rank ~2.6 of 6 *in this set*, not 70% absolute condition.

## Further reading

- [`docs/extraction_review.md`](docs/extraction_review.md) — all listings (ranking, gold, excluded), source URLs, fields read off them.
- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature rank breakdown, pairwise win matrices, full eval numbers, corpus-scale (hedonic regression) view.
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal.
