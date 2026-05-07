# Cars24 vs Spinny — Competitive Intel

**Hyundai Creta, used, Delhi-NCR, ₹7-13.5L, N=6 listings (3 each).**

## Headline

**The two platforms compete on different axes — and the data shows it before you log in.**

- **Cars24 sells uniform process.** Every listing same 12-month warranty, same 140-point quality check, **no per-listing tier**. Buyer trusts the platform.
- **Spinny sells per-listing transparency.** Tier per car (`assured-plus` / `assured` / `budget`), per-section inspection ratings, accident booleans, buy-back tables. Buyer reads the report.
- **Disclosure asymmetry: Cars24 exposes 4 of 17 condition-relevant fields per listing. Spinny exposes 11-12.** ~3× ratio. Concrete and observable, not constructed.

**Implication:** Cars24 likely wins price-conscious buyers in trust-the-brand mode. Spinny likely wins informed buyers who want a paper trail. Both rational.

## The 6-listing ranking (price-to-condition)

Lower ratio = more car per rupee.

| # | listing | platform | price | rank-score | ratio (₹/pt) | disclosure |
|---|---|---|---:|---:|---:|---:|
| 1 | 10076268734 | cars24 | 7.64L | 70.5 | **10,837** | 4/17 |
| 2 | 28476005 | spinny | 13.47L | **82.5** | 16,327 | 12/17 |
| 3 | 10096166769 | cars24 | 7.00L | 39.0 | 17,959 | 4/17 |
| 4 | 10041693110 | cars24 | 9.50L | 41.0 | 23,171 | 4/17 |
| 5 | 28198885 | spinny | 7.47L | 32.0 | 23,344 | 12/17 |
| 6 | 27839393 | spinny | 9.87L | 35.0 | 28,200 | 11/17 |

Score is rank-based across the 6 within each feature (km / age / owners / accident-disclosed) and weight-summed. **Top spot is Cars24, top condition is Spinny.**

![ranking chart](figures/ranking.png)

## What this measures vs what it doesn't

**Measures:** *relative* price-to-condition rank within these 6 listings, on common pre-auth fields. Robust to ±25% weight perturbation (Kendall τ ≥ 0.87).

**Doesn't measure:** absolute condition. The rubric is a reasonable prior, not grounded against external valuation. With auth/API access we'd use the 200-point inspection report; pre-auth only fair to compare on shared fields.

**Caveat that surfaced in eval:** km_driven dominates the ranking. Removing km drops Kendall τ to 0.33 (i.e. a different ranking). If the buyer cares more about another dimension, the ranking changes — see [technical appendix](technical_appendix.md).

## One-line takeaway

If Cars24 is competing on transparency, it's losing 3 to 1 on the count of condition-relevant fields exposed pre-auth. If Cars24 is competing on curated trust, the ranking suggests it's working — they take the top deal slot in our N=6.

---

*Methodology, per-feature ranks, pairwise win matrix, eval harness numbers, tradeoffs, and limitations: see [technical_appendix.md](technical_appendix.md).*
