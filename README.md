# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. **Scope: Hyundai Creta, Delhi-NCR, SX trim line, petrol, automatic.** N=6 listings ranked (3 per platform); 10 separate gold listings used for evaluation.

## Ranking

Sorted by composite score descending.

Rule signal: km, age, owners, accident disclosure.

Visual signal: a Claude-with-vision agent that inspects each listing's photos for 5 condition aspects (exterior panels, interior cabin, dashboard, tyres, engine bay).

```
composite = α × rule + (1 − α) × visual,    α = 0.7
```

*Note: α = 0.7 leans rule-heavy because the rule inputs are platform-disclosed hard facts; the visual signal is interpretive and earns a larger share only as eval coverage grows.*

| rank | listing_id | platform | price (₹L) | rule | visual | composite |
|---:|---|---|---:|---:|---:|---:|
| 1 | 28476005 | spinny | 13.47 | 73.50 | 56.67 | 68.45 |
| 2 | 10067090111 | cars24 | 10.80 | 62.50 | 48.00 | 58.15 |
| 3 | 10096166769 | cars24 | 7.00 | 44.67 | 40.00 | 43.27 |
| 4 | 27839393 | spinny | 9.87 | 41.17 | 48.00 | 43.22 |
| 5 | 28198885 | spinny | 7.47 | 37.67 | 38.00 | 37.77 |
| 6 | 10126364760 | cars24 | 5.09 | 34.17 | 22.00 | 30.52 |


![ranking](docs/figures/ranking_chart.png)

## How condition is scored

We score on the four fields **both** platforms expose for every listing — anything else would advantage the more verbose platform on data quantity rather than car condition. They also map directly onto the canonical drivers of used-car depreciation: mechanical wear (km), time-based aging (age), maintenance variability (owners), and structural risk (accident disclosure).

| Feature | Why it matters | Weight |
|---|---|---:|
| Kilometres driven | Strongest single predictor of mechanical wear | 35% |
| Age (years) | Wear is roughly time-driven | 25% |
| Number of prior owners | More owners = more variability in maintenance | 25% |
| Accident disclosed | Safety / structural signal; coarse data | 15% |

Per feature, we **rank the listings among themselves** (best = 100, worst = 0), then weighted-mean for the rule score. Visual score is computed the same way: per-aspect severity ranked across the set, equal weights. Scores are **set-relative** — meaningful as a comparison of these listings, not as absolute condition.

## Why the ranking is trustworthy

Before producing this ranking we tested the system against a **separate 10-listing benchmark** (5 Cars24 + 5 Spinny, hand-checked, distinct from the 6 ranked above). Three things had to hold up:

**1. The system reads listings correctly.** For every one of the 10 benchmark listings, the kilometres, age, owner count, and accident disclosure that the system extracted matched what we hand-verified — zero misreads, on either platform. So whatever ranking comes out isn't built on bad data.

**2. The top listing doesn't depend on a tuning choice.** We tried 8 variations of the rule weights (giving each of the four factors ±25% influence) and 6 different blends of rule-vs-photo signal (anywhere from 50/50 to rule-only). Across every combination tested, the rankings barely move and the top listing stays the same. Nobody got there by picking favourable knob settings.

**3. The vision agent's photo judgment matches a human's.** On the 10 benchmark listings, when the AI rated a photo "light wear" the human reviewer either agreed or was one step away. Across all five aspects (panels, interior, dashboard, tyres, engine bay), AI and human agreement within one severity step ran from 78% to 100%, depending on aspect. The AI isn't always exact — it isn't trying to be — but it doesn't disagree wildly either.

## Caveats

- **N=6 is illustrative, not statistically defensible.** Platform-level conclusions shouldn't rest on this alone.
- **Public data only.** Without auth/API access, the fair comparison is on the common fields both platforms expose.
- **Trim line still spans SX / SX PLUS / SX (O).** Tightening to a single sub-trim shrinks supply below the 16 listings we needed; SX-line is the closest workable filter.
- **Rank-based scoring is set-relative.** A score of 70 means rank ~2.6 of 6 in this set, not 70% condition in absolute terms.

## Further reading

- [`docs/extraction_review.md`](docs/extraction_review.md) — every listing collected (ranking, gold, excluded), with source URLs and parsed values
- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature ranks, full eval numbers (E3, E4, E6), corpus-scale view
