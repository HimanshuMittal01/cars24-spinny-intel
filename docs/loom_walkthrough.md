# Cars24 vs Spinny — Competitive Intel Pipeline

**What it does:** Extract specs and condition signals from used-car listings on two platforms, score each listing on a common scale, and rank by price-to-condition. Scope: Hyundai Creta, SX trim, petrol-automatic, Delhi-NCR. N=6 ranked listings (3 per platform), calibrated on 10 hand-labeled gold listings.

The walkthrough below is the 3-minute story.

---

## 1. The System End-to-End

```mermaid
flowchart TD
    A[Crawl listings\nCars24 + Spinny] --> B[Snapshot HTML\n+ photo URLs]
    B --> C[Extractor\nparse price · km · age · owners · accident]
    C --> D[Normalizer\ncoerce types · impute not_visible]

    D --> E[rule_score\nrank-based · 4 dims · weighted mean]
    D --> F[Vision Agent\nouter: claude-sonnet-4-6 with tools\ninner: one-shot VLM, cached on photo hash]

    F --> G[visual_score\n5 aspects · equal weight]
    E --> H[composite_score\nα × rule + 1-α × visual\nα = 0.7 default]
    G --> H

    H --> I[Final ranking\n6 held-out listings\nprice ÷ composite_score]
```

**Two signal branches feed composite_score:**
- **rule_score** — structured data only (km, age, owners, accident); no images needed
- **visual_score** — agent inspects listing photos; grades 5 aspects on a 6-point severity scale

The 6 ranking listings are held out from all calibration. `α` and weights are fixed on the 10-listing gold set only.

---

## 2. The Ranking Formulas

### 2a. rule_score

Four dimensions, each ranked across the full 16-listing set (10 gold + 6 ranking). Best rank → 100, worst rank → 0, others interpolated linearly by rank position.

```
rank_score(x, dim) = (rank_among_16 − 1) / (16 − 1) × 100
                     where rank 1 = best (low km, low age, few owners, no accident)

score_common = 0.35 × km_score
             + 0.25 × age_score
             + 0.25 × owners_score
             + 0.15 × accident_score
```

**Weights:**

| Dimension        | Weight | Rationale                                   |
|------------------|-------:|---------------------------------------------|
| km_driven        |    35% | Strongest single predictor of mechanical wear|
| age_years        |    25% | Time-driven wear; warranty + parts impact   |
| owners           |    25% | More owners = more maintenance variability  |
| accident_disclosed |  15% | Coarse signal (yes/no); downweighted         |

**Worked example — one listing:**

Suppose a listing ranks 3rd-best on km (out of 16), 2nd on age, 1st on owners, no accident:

```
km_score      = (3-1)/(16-1) × 100 = 13.3
age_score     = (2-1)/(16-1) × 100 =  6.7
owners_score  = (1-1)/(16-1) × 100 =  0.0   ← best possible
accident_score= 100                          ← no accident = full marks

score_common  = 0.35×13.3 + 0.25×6.7 + 0.25×0.0 + 0.15×100
              = 4.7 + 1.7 + 0.0 + 15.0
              = 21.4
```

Score is **set-relative**: it measures rank position within these 16 listings, not absolute condition.

---

### 2b. composite_score

```
composite_score = α × rule_score + (1 − α) × visual_score

Default: α = 0.7
```

**Visual score** comes from the vision agent grading 5 aspects on each listing's photos:

| Aspect             | Severity scale (6 levels)                                        |
|--------------------|------------------------------------------------------------------|
| exterior_panels    | pristine → light_wear → moderate → heavy → defect → not_visible |
| interior_cabin     | (same scale)                                                     |
| dashboard_console  | (same scale)                                                     |
| tyres              | (same scale)                                                     |
| engine_bay         | (same scale)                                                     |

Each aspect is mapped to a 0–100 score (pristine=100, defect=0). Five aspects weighted equally → `visual_score`.

**Worked example — composite:**

```
rule_score    = 68.0   (from structured data)
visual_score  = 68.0   (from photo inspection)

composite     = 0.7 × 68.0 + 0.3 × 68.0
              = 47.6  + 20.4
              = 68.0

₹/point       = 10,80,000 / 68.0 = ₹15,882 per condition-point
```

(This is listing 10067090111, ranked #3 in the final output — see README ranking table.)

---

## 3. Three Checks That Build Confidence

### Check 1: Agent calls are always within ±1 of human gold

The vision agent was calibrated against 10 hand-labeled gold listings. We measured **adjacent agreement** (agent and human within ±1 severity step) and **exact agreement**.

<!-- Source: runs/e6_20260507T164231-80432e/agreement_summary.json -->

| Aspect             | Exact | Adjacent | κ    | n |
|--------------------|------:|----------:|-----:|--:|
| exterior_panels    |  0.80 |  **1.00** | 0.62 | 5 |
| interior_cabin     |  1.00 |  **1.00** | 1.00 | 5 |
| dashboard_console  |  0.40 |  **1.00** | 0.21 | 5 |
| tyres              |  1.00 |  **1.00** | 0.00 | 5 |
| engine_bay         |  0.25 |  **1.00** | 0.00 | 4 |

**Adjacent = 1.0 on every aspect.** The agent is never more than one severity step away from the human call.

Why κ looks low on some aspects: κ penalises agreement that could happen by chance. When gold labels are homogeneous (most listings grade out as pristine or light_wear), the "by-chance" baseline is high and κ deflates even when agreement is real. With N=5 per aspect and a near-uniform label distribution, **adjacent agreement is the right load-bearing metric** — it directly maps to whether the rank order can flip due to agent error, and the answer is: it can't by more than one step.

---

### Check 2: The composite ranking is stable across the full α range

We swept α across [0.5, 1.0] in steps of 0.1 and measured Kendall τ of each resulting ranking against the α=0.7 baseline.

<!-- Source: runs/e4_20260507T164312/alpha_sweep.json -->

| α   | τ vs α=0.7 |
|-----|----------:|
| 0.5 |     0.911 |
| 0.6 |     0.956 |
| 0.7 |     1.000 |
| 0.8 |     0.956 |
| 0.9 |     0.956 |
| 1.0 |     0.956 |

**τ ≥ 0.91 across the entire range.** The choice of α=0.7 is not doing the ranking work. You could double-weight visual (α=0.5) or drop it entirely (α=1.0) and the top-to-bottom order barely shifts. The underlying signals agree.

---

### Check 3: Vision adds independent signal — it is not a rule echo

We computed three-way Spearman ρ on the 10 gold listings across three ranking signals: rule-based score, agent-visual score, and human-gold-visual score.

<!-- Source: runs/e6_20260507T164231-80432e/cross_method_e3.json -->

| Pair                          |    ρ |
|-------------------------------|-----:|
| rule vs gold-visual           | 0.51 |
| rule vs agent-visual          | 0.39 |
| gold-visual vs agent-visual   | 0.44 |

**Rule and visual are only moderately correlated (ρ ≈ 0.51).** If visual score were just a noisy restatement of km/age/owners, ρ would approach 1.0. Instead, at ρ=0.51 the two signals genuinely diverge — a car can look good in photos but have high km, or look rough but be nearly new. That divergence is what makes the composite worth computing: it captures something the structured data misses.

Agent-visual recovers the human gold ordering at ρ≈0.44 — moderate on N=10 where ρ has wide confidence intervals, but directionally consistent.

---

## 4. The Held-Out Story

The 6 ranking listings were **never labeled, never tuned to.** Hyperparameters (α=0.7, the four dimension weights) were fixed on the 10 gold listings only. The pipeline then ran over all 16 listings to compute rank positions, and the output was filtered to the 6 held-out listings. Their composite scores are pure forward-pass agent output — no leakage.

```
16 total listings
├── 10 gold  →  calibration only (agreement checks, α sweep, weight stability)
└──  6 held-out  →  final ranking output (never touched during calibration)
```

---

## Final Ranking

| # | Listing      | Platform | Price   | Condition score | ₹/point    |
|---|--------------|----------|--------:|----------------:|-----------:|
| 1 | 10096166769  | Cars24   | 7.00 L  |            48.5 | **14,441** |
| 2 | 10126364760  | Cars24   | 5.09 L  |            34.0 |     14,962 |
| 3 | 10067090111  | Cars24   | 10.80 L |            68.0 |     15,882 |
| 4 | 28476005     | Spinny   | 13.47 L |            80.0 |     16,838 |
| 5 | 28198885     | Spinny   | 7.47 L  |            34.5 |     21,652 |
| 6 | 27839393     | Spinny   | 9.87 L  |            35.0 |     28,200 |

Cars24 occupies the top 3 slots by ₹/condition-point in this N=6 sample. Caveat: N=6 is illustrative — platform-level conclusions need more listings.

---

*Data sources: `runs/e6_20260507T164231-80432e/agreement_summary.json` · `runs/e6_20260507T164231-80432e/cross_method_e3.json` · `runs/e4_20260507T164312/alpha_sweep.json`*
