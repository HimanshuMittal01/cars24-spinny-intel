# Cars24 vs Spinny — Competitive Intel

A multi-agent pipeline that extracts specs and condition signals from used-car listings on Cars24 and Spinny, then ranks them by price-to-condition. Scope: Hyundai Creta, used, Delhi-NCR, ₹7-13.5L. N=6 listings, 3 per platform.

## Ranking

Lower ₹ per condition-point = more car for your money.

| # | listing | platform | price | condition score | ₹ per condition-point |
|---|---|---|---:|---:|---:|
| 1 | 10076268734 | cars24 | 7.64L | 70.5 | **10,837** |
| 2 | 28476005 | spinny | 13.47L | 82.5 | 16,327 |
| 3 | 10096166769 | cars24 | 7.00L | 39.0 | 17,959 |
| 4 | 10041693110 | cars24 | 9.50L | 41.0 | 23,171 |
| 5 | 28198885 | spinny | 7.47L | 32.0 | 23,344 |
| 6 | 27839393 | spinny | 9.87L | 35.0 | 28,200 |

![ranking](docs/figures/ranking.png)

## How condition is scored

Each platform exposes different fields publicly. We score on the four fields **both** Cars24 and Spinny expose for every listing — anything else would advantage the more verbose platform on data quantity rather than on car condition.

| Feature | Why it matters | Weight |
|---|---|---:|
| Kilometres driven | Strongest single predictor of mechanical wear and resale value | 35% |
| Age (years) | Wear is roughly time-driven; affects warranty and parts availability | 25% |
| Number of prior owners | More owners = more variability in maintenance history; first-owner cars carry a market premium | 25% |
| Accident disclosed | Safety / structural signal; weighted lower because the data is coarse (usually yes/no, not severity) | 15% |

For each of the four features, we **rank the 6 cars among themselves** — the best gets 100, the worst gets 0, the rest fall in between by their position. Then we combine the per-feature scores using the weights above to get the condition score in the ranking table.

Why ranks rather than absolute thresholds (e.g., "<20k km is excellent")? Thresholds would be a guess we couldn't defend with data. Ranks come straight from the listings; they don't need defending.

## How we know the ranking holds up

Before producing the ranking we built and ran a small evaluation harness against a hand-labeled gold dataset.

- **Faithfulness check.** We hand-labeled all 6 listings by reading the source pages directly, then compared the extractor's output to our labels. **The extractor matched our values on every field, on both platforms.**
- **Stability check.** We bumped each of the four weights up and down by 25% (one at a time, 8 variants) and re-ran the ranking. **The ordering was substantially preserved across all 8 variants** — the ranking is not sensitive to small weight choices.
- **Dominance check.** We dropped each feature in turn and re-ran. **Removing km changes the ranking a lot; removing any of the other three barely moves it.** Kilometres is the load-bearing feature — worth knowing if a business interpretation weighs another dimension more.
- **Determinism check.** Three identical reruns of the pipeline produced byte-identical output. No silent randomness in the scoring path.

**Honest framing on the faithfulness check.** The hand-labels were read from the same source pages the extractor parses, so the check confirms *the extractor faithfully captures what the page exposes*, not that our scoring formula matches some external valuation. An independent calibration would need either gut-rated condition labels (subjective) or a third-party valuation source — out of scope here, called out below.

## Caveats

- **N=6 is illustrative, not statistically defensible.** Conclusions about platforms shouldn't rest on this alone.
- **Public data only.** With auth/API access we'd use Spinny's 200-point inspection report and Cars24's deeper in-app fields. The fair comparison given pre-auth data is on the fields both platforms expose. Spec §13 documents this choice.
- **Score is set-relative.** A score of 70 means roughly the 2.6th-best of 6 *in this set*, not "this car is in 70% condition" in any absolute sense.

## Further reading

- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature rank breakdown, pairwise win matrices, full eval numbers, the platform-positioning side observation.
- [`docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md`](docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md) — design spec (§13 reality-check, §14 rank-based-scoring amendments).
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal.
