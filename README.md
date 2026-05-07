# Cars24 vs Spinny — Competitive Intel

Multi-agent extraction + ranking pipeline for used-car listings. Scope: Hyundai Creta, used, Delhi-NCR, ₹7-13.5L. N=6 listings, 3 per platform.

## Result

| # | listing | platform | price | rank-score | ₹ per condition-pt |
|---|---|---|---:|---:|---:|
| 1 | 10076268734 | cars24 | 7.64L | 70.5 | **10,837** |
| 2 | 28476005 | spinny | 13.47L | 82.5 | 16,327 |
| 3 | 10096166769 | cars24 | 7.00L | 39.0 | 17,959 |
| 4 | 10041693110 | cars24 | 9.50L | 41.0 | 23,171 |
| 5 | 28198885 | spinny | 7.47L | 32.0 | 23,344 |
| 6 | 27839393 | spinny | 9.87L | 35.0 | 28,200 |

Score is rank-based across the 6 listings within each scoring dimension (km / age / owners / accident-disclosed; weights 35 / 25 / 25 / 15) and weight-summed. Lower ratio is better.

![ranking](docs/figures/ranking.png)

## Eval

| eval | result | reading |
|---|---|---|
| E2 — extraction recall vs gold | 1.0 across 4 fields, both platforms | extractor faithful to the page's structured data |
| E3 — score calibration vs gold | MAE = 0, ρ = 1.0 (N=6) | self-consistency (gold uses same rubric on same source) |
| E4 — weight perturbation ±25% | Kendall τ ≥ 0.87 | ranking robust to weight choice |
| E4 — leave-one-feature-out | km removal → τ = 0.33; others ≥ 0.73 | km is the load-bearing feature |
| E5 — determinism (3 reps) | byte-identical | pipeline deterministic given fixed snapshots |

## Caveats

- N=6 is illustrative, not statistically defensible.
- Pre-auth common fields only. With auth/API access the rubric would use the 200-point inspection report.
- Rank-based scoring is set-relative — a score of 70 means rank ~2.6 of 6 in this set, not 70% absolute condition.
- E3 is a self-consistency check, not an independent calibration. Independent calibration would need holistic gut-rated gold or third-party valuation.

## Reproduce

```
uv sync
uv run pytest                              # 55 tests
uv run python scripts/run_pipeline.py      # ranking on the 6 saved fixtures
```

Snapshots are committed under `fixtures/`. The pipeline replays from disk; no live network required.

## Further reading

- [`docs/technical_appendix.md`](docs/technical_appendix.md) — methodology, per-feature ranks, pairwise win matrices, full eval numbers, tradeoffs, platform-positioning side observation.
- [`docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md`](docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md) — design spec including §13 reality-check and §14 rank-based-scoring amendments.
- [`docs/tradeoffs.md`](docs/tradeoffs.md) — engineering tradeoffs journal.
