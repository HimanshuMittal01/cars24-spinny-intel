# Technical Appendix — Cars24 vs Spinny Competitive Intel

_Run id: `20260507T085230-477ddc`_

_Companion to [`../README.md`](../README.md). All methodology, per-feature breakdown, eval harness numbers, and limitations live here._

## 1. Methodology

**Pipeline.** Single explicit DAG, synchronous, deterministic at scoring/ranking. Source: `src/ci/pipeline.py`.

```
snapshots → extract.cars24 / extract.spinny → normalize → score(set) → rank → report
```

**Extractors are JSON-parse-first.** Both platforms inject canonical listing data as inline JSON (Cars24 via Next.js streaming `__next_f` payloads; Spinny via `window.__INITIAL_STATE__` JS literal). The extractors parse that directly — no LLM in the scoring path. LLM client parameter retained for signature compatibility / future free-text fallback.

**Scoring is rank-based per spec §14.** For each scoring dimension, listings are sorted (best→worst), assigned 1-indexed rank with tie averaging, and converted to a 0-100 score by linear interpolation: `100 × (n - rank) / (n - 1)`. The composite is a weight-sum across dimensions:

| dimension | weight | direction |
|---|---:|---|
| km_driven | 35 | lower is better |
| age_years | 25 | lower is better |
| owners | 25 | lower is better |
| accident_disclosed | 15 | none > minor > major |

**Why rank-based, not anchored bands?** Anchored bands baked an unjustifiable prior ("<20k km is excellent") into every score. Rank-based asks only "is A's km better than B's km?" — trivially answerable from the data without inventing thresholds. Trade-off: loses absolute magnitude (a 50k-km gap and a 2k-km gap can map to the same rank delta). Magnitude lives in the raw fields and is available for any post-hoc analysis.

**Common-set scoring is the *fair* comparison given pre-auth data asymmetry.** Cars24 has no per-listing certification tier and no per-listing accident-detail field; Spinny has both. Mixing platform-specific fields into the score would advantage Spinny on data-disclosure rather than condition. Cars24's platform-level no-accident promise is mapped to per-listing `accident_disclosed = none`. Spec §13 / §14 documents the rationale.

## 2. Per-feature rank breakdown

Each feature, raw value, and rank-score (0-100) for the 6 listings. Composite is the weight-sum. Rows in ranking order.

| listing | platform | price | km | age | own | accident | km_score | age_score | own_score | acc_score | composite |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `10076268734` | cars24 | ₹764,000 | 50,208 | 5 | 1 | none | 80.0 | 80.0 | 60.0 | 50.0 | **70.5** |
| `28476005` | spinny | ₹1,347,000 | 33,191 | 4 | 1 | none | 100.0 | 100.0 | 60.0 | 50.0 | **82.5** |
| `10096166769` | cars24 | ₹700,389 | 66,306 | 7 | 1 | none | 40.0 | 10.0 | 60.0 | 50.0 | **39.0** |
| `10041693110` | cars24 | ₹950,000 | 50,673 | 6 | 2 | none | 60.0 | 50.0 | 0.0 | 50.0 | **41.0** |
| `28198885` | spinny | ₹747,000 | 88,785 | 7 | 1 | none | 20.0 | 10.0 | 60.0 | 50.0 | **32.0** |
| `27839393` | spinny | ₹987,000 | 90,428 | 6 | 1 | none | 0.0 | 50.0 | 60.0 | 50.0 | **35.0** |

## 3. Pairwise win matrices

Pairwise comparison per feature. `1` = row beats column on this feature, `0` = loses, `½` = tie. Diagonal blank. The rank-score in §2 is mathematically the average of these wins (× scale).

### km_driven

| | `…8734` | `…6005` | `…6769` | `…3110` | `…8885` | `…9393` |
|---|---:|---:|---:|---:|---:|---:|
| `…8734` | — | 0 | 1 | 1 | 1 | 1 |
| `…6005` | 1 | — | 1 | 1 | 1 | 1 |
| `…6769` | 0 | 0 | — | 0 | 1 | 1 |
| `…3110` | 0 | 0 | 1 | — | 1 | 1 |
| `…8885` | 0 | 0 | 0 | 0 | — | 1 |
| `…9393` | 0 | 0 | 0 | 0 | 0 | — |

### age_years

| | `…8734` | `…6005` | `…6769` | `…3110` | `…8885` | `…9393` |
|---|---:|---:|---:|---:|---:|---:|
| `…8734` | — | 0 | 1 | 1 | 1 | 1 |
| `…6005` | 1 | — | 1 | 1 | 1 | 1 |
| `…6769` | 0 | 0 | — | 0 | ½ | 0 |
| `…3110` | 0 | 0 | 1 | — | 1 | ½ |
| `…8885` | 0 | 0 | ½ | 0 | — | 0 |
| `…9393` | 0 | 0 | 1 | ½ | 1 | — |

### owners

| | `…8734` | `…6005` | `…6769` | `…3110` | `…8885` | `…9393` |
|---|---:|---:|---:|---:|---:|---:|
| `…8734` | — | ½ | ½ | 1 | ½ | ½ |
| `…6005` | ½ | — | ½ | 1 | ½ | ½ |
| `…6769` | ½ | ½ | — | 1 | ½ | ½ |
| `…3110` | 0 | 0 | 0 | — | 0 | 0 |
| `…8885` | ½ | ½ | ½ | 1 | — | ½ |
| `…9393` | ½ | ½ | ½ | 1 | ½ | — |

### accident_disclosed

| | `…8734` | `…6005` | `…6769` | `…3110` | `…8885` | `…9393` |
|---|---:|---:|---:|---:|---:|---:|
| `…8734` | — | ½ | ½ | ½ | ½ | ½ |
| `…6005` | ½ | — | ½ | ½ | ½ | ½ |
| `…6769` | ½ | ½ | — | ½ | ½ | ½ |
| `…3110` | ½ | ½ | ½ | — | ½ | ½ |
| `…8885` | ½ | ½ | ½ | ½ | — | ½ |
| `…9393` | ½ | ½ | ½ | ½ | ½ | — |

## 4. Eval harness results

### E2 — Extraction quality (vs hand-labeled gold, N=6)

- field_recall (overall): `{'price': 1.0, 'km_driven': 1.0, 'age_years': 1.0, 'owners': 1.0}`
- per_platform: `{"spinny": {"price": 1.0, "km_driven": 1.0, "age_years": 1.0, "owners": 1.0}, "cars24": {"price": 1.0, "km_driven": 1.0, "age_years": 1.0, "owners": 1.0}}`

Both platforms: 100% recall on the 4 score-bearing fields. Gold was hand-labeled by reading the same inline JSON the extractor parses — this is a self-consistency check, not an independent calibration. See limitations.

### E3 — Score calibration (vs gold)

- MAE (overall): `0.0`
- Spearman ρ (overall): `1.0`
- per_platform_MAE: `{"spinny": 0.0, "cars24": 0.0}`
- per_platform_ρ: `{"spinny": 1.0, "cars24": 1.0}`

MAE = 0 by construction (gold uses the same rubric on the same source data). Useful as a regression guard for future runs, not as an independent calibration.

### E4 — Weight sensitivity (Kendall's τ vs unperturbed ranking)

**±25% perturbation per dim:**

| dim direction | τ |
|---|---:|
| km_driven+ | 1.000 |
| km_driven- | 0.867 |
| age_years+ | 1.000 |
| age_years- | 0.867 |
| owners+ | 0.867 |
| owners- | 1.000 |
| accident_disclosed+ | 0.867 |
| accident_disclosed- | 1.000 |

**Leave-one-dim-out:**

| dim removed | τ |
|---|---:|
| km_driven | 0.333 |
| age_years | 0.733 |
| owners | 0.867 |
| accident_disclosed | 1.000 |

Readings:
- Ranking is **stable to ±25% weight perturbation** (τ ≥ 0.87).
- **km_driven is the dominant feature** — removing it drops τ to 0.33. If a buyer cared more about owners, age, or accident than about km, the ranking changes materially.
- This is a real signal about what the rubric is doing — worth flagging to anyone interpreting the ranking.

### E5 — Determinism

- 3 reps on `cars24/10041693110`: identical = `True`, distinct outputs = `1`
- Pipeline is byte-deterministic given fixed snapshots. Any non-determinism would surface here.

## 5. Disclosure asymmetry — side observation, not a ranking input

`disclosure_count` is **not** a scoring dimension. It does not affect the ranking in `README.md`. It is reported as a descriptive metric because the gap between the two platforms is large and structural — but it speaks to platform *positioning*, not to *which-listing-is-the-better-deal*. Anyone acting on the ranking should set it aside.

### The numbers

- Cars24: **4 of 17** condition-relevant fields exposed per listing (uniform across all 3 Cars24 listings in this sample).
- Spinny: **11-12 of 17** per listing.
- ~3× ratio. Concrete and observable, not constructed.

### What the gap means (positioning interpretation)

The ~13-field gap isn't evenly spread. Spinny exposes the *judgment-bearing* fields — inspection sub-ratings, repair statements, tier, accident boolean, market-price-delta. Cars24 exposes only metadata (price, km, year, insurance type) plus a platform-level promise.

So:
- **Cars24's product is "trust the platform — same warranty, same 140-pt promise on every car."** The buyer doesn't read condition specifics; the platform vouches.
- **Spinny's product is "read the report — here's exactly what was inspected, what was found, what tier this car is in."** The buyer self-serves.

Both are coherent strategies. They likely target different buyer segments (price-sensitive trust-the-brand vs informed read-the-paper-trail). **This is a signal about how each platform competes, not a signal about which listing is a better deal.**

### Why it's deliberately not in the ranking

Mixing disclosure breadth into the score would conflate "exposes more data" with "is in better condition". A Cars24 listing in objectively excellent mechanical shape with sparse disclosure should not be penalised for being on a platform that markets opacity-as-uniformity.

### 17 disclosure-eligible fields

A listing scores 1 per field if any non-null value is exposed pre-auth.

- `accident_history_detail`
- `inspection_per_section_ratings`
- `inspection_repair_statements`
- `tyre_condition_per_wheel`
- `service_history_records`
- `warranty_remaining_months`
- `noc_status`
- `rc_type`
- `insurance_type`
- `insurance_validity`
- `previous_use_type`
- `challan_status`
- `hypothecation_status`
- `inspection_photo_count`
- `per_listing_certification_tier`
- `buy_back_pricing`
- `market_price_delta`

The ~13-field gap isn't even spread — Spinny exposes the *judgment-bearing* ones (inspection ratings, repair statements, tier, market-price delta), not just metadata. That's the part that maps to *positioning*, not just *quantity*.

## 6. Tradeoffs journal

See [`tradeoffs.md`](tradeoffs.md) for the full journal. Headlines:

1. **Speculative schema vs real data (2026-05-07).** Mid-build, fetched real listings and discovered the schemas were largely fictional. Pivoted to JSON-parse-first extraction. Rewrote 3 tasks. The pivot turned the disclosure asymmetry from hypothesis to measurement.
2. **Gold-labeling on a deterministic pipeline.** E2/E3 against hand-labeled gold come out perfect by construction. Honest framing in the limitations section.
3. **Anchored bands → rank-based scoring (spec §14).** Bands were defensible only via sensitivity analysis. Rank-based is defensible by construction ("is A's km better than B's km — yes"). Tradeoff: lost magnitude, gained groundedness.

## 7. Limitations

- **N=6 ranking.** Strategic conclusions are illustrative. The 4 additional listings were collected mid-band; ratio differences between rank 1 and 6 are informative but not statistically defensible.
- **Rank-based scoring depends on the set composition.** Same listing in a different 6-set could rank differently. The composite is a relative-position score, not an absolute condition score.
- **km_driven dominates the ranking** (E4 LOO τ = 0.33). Defensible given km is the strongest single predictor in used-car valuation, but worth surfacing.
- **E3 calibration is a self-consistency check**, not an independent eval. Gold uses the same rubric on the same JSON the extractor parses. True calibration would require holistic gut-rated scores or third-party valuation.
- **Cars24 platform-level no-accident promise is *modelled* as per-listing `accident_disclosed = none`.** Defensible mapping, not a per-listing extraction. Documented and acknowledged.
- **disclosure_count is binary per field.** A single boolean (Spinny `is_accidental: false`) counts the same as detailed exposure (per-section inspection sub-ratings). Measures *presence*, not *depth*.
- **Gold annotated by one annotator** (the author). No inter-rater data.
- **Snapshots are point-in-time.** Findings apply to vintage as recorded in `fixtures/<platform>/<id>/captured_at.txt`.

## 8. Reproducibility

```
uv run pytest                              # 55 tests
uv run python scripts/run_pipeline.py      # produces runs/<id>/ranking.json
```
Latest run: `runs/20260507T085230-477ddc/`
Per-fixture metadata: `fixtures/<platform>/<id>/{page.html, captured_at.txt, url.txt}`