# Cars24 vs Spinny — Competitive Intel

**Hyundai Creta, used, Delhi-NCR, ₹7-13.5L. N=6 listings, 3 each platform.**

## Ranking (price-to-condition)

Lower ratio = more car per rupee. Rank-score is each listing's relative position across km / age / owners / accident-disclosed (35/25/25/15 weights), aggregated to a 0-100 composite.

| # | listing | platform | price | rank-score | **₹ per condition-pt** |
|---|---|---|---:|---:|---:|
| 1 | 10076268734 | cars24 | 7.64L | 70.5 | **10,837** |
| 2 | 28476005 | spinny | 13.47L | 82.5 | 16,327 |
| 3 | 10096166769 | cars24 | 7.00L | 39.0 | 17,959 |
| 4 | 10041693110 | cars24 | 9.50L | 41.0 | 23,171 |
| 5 | 28198885 | spinny | 7.47L | 32.0 | 23,344 |
| 6 | 27839393 | spinny | 9.87L | 35.0 | 28,200 |

![ranking chart](figures/ranking.png)

## Decision-relevant takeaways

- **Cars24 takes the top deal slot** (₹10,837/pt). Two of the top three deals are Cars24.
- **Spinny holds the highest-condition listing** (rank-score 82.5 — a 2022 / 33k km / 1 owner) but at premium ratio. Spinny's competitive position is at the *condition-leader* end of the band, not the *value* end.
- **Ranking is robust to ±25% weight perturbation** (Kendall τ ≥ 0.87). Different weights would not flip the top spot.

## One thing the CXO should know about this ranking

**km_driven dominates.** Drop km from the rubric and the ranking changes a lot (τ = 0.33). Defensible — km is the strongest single predictor in used-car valuation — but means **the ranking is essentially "lowest km wins, modulated by price"**. If a buyer or strategy assumption weighs another dimension higher (e.g. owner-count for fleet-buyer segments), the ranking shifts. Worth a sentence in any business interpretation.

## Limits of this read

- **N=6.** Illustrative, not statistically defensible.
- **Common pre-auth fields only.** With auth/API we'd score on the 200-point inspection report. The fair comparison given pre-auth data is on the fields both platforms expose. Spec §13 documents this choice.
- **Rank-based scoring is set-relative.** A score of 70 here means rank ~2.6 of 6 in *this* set, not 70% absolute condition.

---

Methodology, per-feature ranks, pairwise win matrices, eval harness numbers, tradeoffs, and the platform-positioning side observation: [`technical_appendix.md`](technical_appendix.md).
