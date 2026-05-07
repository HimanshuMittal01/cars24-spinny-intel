# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 listings ranked (3 per platform); 10 separate gold listings used for evaluation.

## Why this scope

Ranking only makes sense between comparable cars. Within the same model, different specs (fuel, transmission, trim) carry market premiums that have nothing to do with condition; mixing them silently bakes those premiums into the price-to-condition signal. So we filter to one model + region + trim band + fuel + transmission, and score on the remaining quantitative dimensions.

## Ranking

Sorted by composite score descending. **Composite = α × rule + (1−α) × visual**, α=0.7 (rule-leaning). Rule signal: km, age, owners, accident disclosure. Visual signal: a Claude-with-vision agent that inspects each listing's photos for 5 condition aspects (exterior panels, interior cabin, dashboard, tyres, engine bay).

| rank | listing_id | platform | price (₹L) | rule | visual | composite |
|---:|---|---|---:|---:|---:|---:|
| 1 | 28476005 | spinny | 13.47 | 73.50 | 63.71 | 70.56 |
| 2 | 10067090111 | cars24 | 10.80 | 62.50 | 55.71 | 60.46 |
| 3 | 27839393 | spinny | 9.87 | 41.17 | 46.38 | 42.73 |
| 4 | 28198885 | spinny | 7.47 | 37.67 | 43.05 | 39.28 |
| 5 | 10096166769 | cars24 | 7.00 | 44.67 | 17.38 | 36.48 |
| 6 | 10126364760 | cars24 | 5.09 | 34.17 | 37.00 | 35.02 |

5 of 6 listings have full visual evidence; listing 10126364760 has `engine_bay` imputed because Cars24 doesn't photograph engine bays.

![ranking](docs/figures/ranking_chart.png)

For value-for-money intuition, see `ratio` (price / composite) in [`runs/latest_ranking/ranking.json`](runs/latest_ranking/ranking.json).

## How condition is scored

We score on the four fields **both** platforms expose for every listing — anything else would advantage the more verbose platform on data quantity rather than car condition.

| Feature | Why it matters | Weight |
|---|---|---:|
| Kilometres driven | Strongest single predictor of mechanical wear | 35% |
| Age (years) | Wear is roughly time-driven | 25% |
| Number of prior owners | More owners = more variability in maintenance | 25% |
| Accident disclosed | Safety / structural signal; coarse data | 15% |

Per feature, we **rank the listings among themselves** (best = 100, worst = 0), then weighted-mean for the rule score. Visual score is computed the same way: per-aspect severity ranked across the set, equal weights. Scores are **set-relative** — meaningful as a comparison of these listings, not as absolute condition.

## How we know the ranking holds up

Eval ran on a separate **10-listing gold set** (5 Cars24 + 5 Spinny), distinct from the 6 ranked above. Full per-experiment tables in [`docs/technical_appendix.md`](docs/technical_appendix.md). Headlines:

- **Faithfulness.** Extraction recall = 1.0 across all four scoring fields, both platforms. The extractor matched gold values on every field, every listing.
- **Stability.** Perturbing each rule weight ±25% (8 variants) gives Kendall τ = 0.69–0.96 vs the baseline ranking — small weight choices don't flip the ordering.
- **Dominance.** km_driven is the most influential rule dim by a wide margin (leave-one-out τ = 0.022). Other dims are secondary (age 0.16, owners 0.56, accident 0.96 — accident contributes effectively no signal because none of these listings reported one).
- **Vision agent vs gold (E6).** Adjacent agreement = 0.78–1.00 across all 5 aspects. Exact varies (0.20–0.90) and Cohen's κ is low on several aspects because gold labels are homogeneous (mostly pristine + light_wear) which inflates by-chance agreement. Adjacent is the load-bearing metric at N=10.
- **Rule vs vision independence (E3).** Spearman ρ(rule, gold-visual) = 0.51 — moderate, not near 1. Vision adds genuinely independent condition signal rather than echoing the rule score.
- **Composite robust to α (E4).** Sweeping α ∈ [0.5, 1.0] gives Kendall τ ≥ 0.91 vs the α=0.7 baseline. The top listing is identical at every α tested.
- **Vision determinism (E5).** Asserted by design: the inner inspector is content-hash-keyed (`sha256(prompt + photo bytes)`); Sonnet at temperature 0 is stable on ordinal classification. Not measured live.

Statistical caveat: N=10 is small; treat individual numbers as directional, not precise.

## Caveats

- **N=6 is illustrative, not statistically defensible.** Platform-level conclusions shouldn't rest on this alone.
- **Public data only.** With auth/API access, Spinny's 200-point inspection report and Cars24's deeper in-app fields would be available; the fair comparison given pre-auth data is on the fields both platforms expose.
- **Trim line still spans SX / SX PLUS / SX (O).** Tightening to a single sub-trim shrinks supply below the 16 listings we needed; SX-line is the closest workable filter.
- **Rank-based scoring is set-relative.** A score of 70 means rank ~2.6 of 6 in this set, not 70% condition in absolute terms.

## Further reading

- [`docs/extraction_review.md`](docs/extraction_review.md) — every listing collected (ranking, gold, excluded), with source URLs and parsed values
- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature ranks, full eval numbers (E3, E4, E6), corpus-scale view
- [`docs/loom_walkthrough.md`](docs/loom_walkthrough.md) — 3-minute walkthrough script
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal
