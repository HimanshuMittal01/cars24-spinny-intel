# Tradeoffs Journal

Append entries during build. Each entry: situation → decision → alternative
considered → what hurt. The "tradeoff that bit" answer in the report is
selected from here at report time.

---

## 2026-05-07 — speculative schema vs real data

**Situation.** Drafted Cars24 / Spinny extractor schemas based on prior assumptions
about what each platform exposes (Cars24 "Imperial / Royal Blue" tiers, per-listing
accident disclosure, generic 200-pt inspection on Spinny).

**Decision.** Pulled one real listing from each platform mid-build, discovered the
schemas were largely fictional, and pivoted: dropped certification from the
common-set, single 4-dim weights table, JSON-parse-first extraction (Next.js
streaming for Cars24, `window.__INITIAL_STATE__` for Spinny), revised disclosure
field list to 17 fields based on observed pre-auth data.

**Alternative considered.** Stay with LLM-as-extractor on raw HTML and let
hallucination rates surface in E2. Rejected: structured JSON is right there in
both pages; using an LLM to pull structured data out of structured data is the
wrong tool, costs more, and adds noise into a pipeline whose value is auditability.

**What hurt.** ~3 tasks of work (T2/T8/T9) were fully rewritten. The plan and
spec gained a "Reality Check (§13)" amendment. But the rework forced an honest
reckoning with the real Cars24 vs Spinny disclosure asymmetry — Cars24 has no
per-listing tier, only a uniform platform promise — which became *the* headline
finding rather than a plausible hypothesis.
