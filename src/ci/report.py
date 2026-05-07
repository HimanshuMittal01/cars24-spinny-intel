from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for tests / headless runs
import matplotlib.pyplot as plt

from ci.schemas import RankRow


def render_chart(rows: list[RankRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    for plat, marker, color in [("cars24", "o", "#1f77b4"), ("spinny", "s", "#d62728")]:
        sub = [r for r in rows if r.platform == plat]
        if not sub:
            continue
        ax.scatter(
            [r.score_common for r in sub],
            [r.price / 1e5 for r in sub],
            marker=marker, color=color, label=plat, s=80,
        )
        for r in sub:
            ax.annotate(r.listing_id, (r.score_common, r.price / 1e5),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel("score_common (0-100)")
    ax.set_ylabel("price (₹ lakh)")
    ax.set_title("Cars24 vs Spinny — price vs constructed condition score")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _format_inr(n: float) -> str:
    return f"{n:,.0f}"


def render_report(
    *,
    rows: list[RankRow],
    extraction_metrics_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
    sensitivity_summary: dict[str, Any],
    determinism_summary: dict[str, Any],
    tradeoff_md: str,
) -> str:
    lines: list[str] = []
    lines.append("# Cars24 vs Spinny — Competitive Intel Report\n")

    lines.append("## 1. Ranking (price-to-condition)\n")
    lines.append("| # | listing | platform | price (₹) | score_common | ratio | disclosure_count | imputed dims |")
    lines.append("|---|---------|----------|-----------|--------------|-------|------------------|--------------|")
    for i, r in enumerate(rows, 1):
        imp = ", ".join(r.imputed_dims) if r.imputed_dims else "—"
        lines.append(
            f"| {i} | `{r.listing_id}` | {r.platform} | {_format_inr(r.price)} "
            f"| {r.score_common:.1f} | {_format_inr(r.ratio)} | {r.disclosure_count} | {imp} |"
        )
    lines.append("")
    lines.append("![ranking chart](figures/ranking.png)\n")

    lines.append("## 2. Agent topology\n")
    lines.append(
        "Single explicit DAG, synchronous. Per-platform extractor agents (cars24, spinny) "
        "parse the platform's structured JSON payload (Cars24: `__next_f` streaming SSR; "
        "Spinny: `window.__INITIAL_STATE__`) and emit a common `RawListing`. The normalizer "
        "maps platform-specific raw fields to a common schema. Scoring and ranking are "
        "deterministic so the audit trail is auditable end-to-end. The trace store records "
        "every node call (input hash, output hash, latency, model, prompt version).\n"
    )
    lines.append("```\n"
                 "snapshots → extract.cars24 / extract.spinny → normalize → score → rank → report\n"
                 "```\n")
    lines.append(
        "Choosing deterministic scoring (rather than an LLM-as-judge second method) "
        "preserves auditability and lets the eval harness §3 rely on byte-identical re-runs. "
        "Per spec §13, certification is excluded from the common-set ranking score because "
        "Cars24 has no per-listing tier; the per-listing tier asymmetry is captured by "
        "`disclosure_count` instead.\n"
    )

    lines.append("## 3. Eval harness\n")
    lines.append("### E2 Extraction quality")
    lines.append(f"- field_recall: `{extraction_metrics_summary.get('field_recall', {})}`")
    if "hallucination_rate" in extraction_metrics_summary:
        lines.append(f"- hallucination_rate: `{extraction_metrics_summary['hallucination_rate']:.3f}`")
    lines.append("")

    lines.append("### E3 Calibration vs gold")
    lines.append(f"- MAE: `{calibration_summary.get('mae_overall', 0):.2f}`")
    lines.append(f"- Spearman ρ: `{calibration_summary.get('spearman_overall', 0):.3f}`")
    lines.append("- Reported as directional, not significant — gold N is small (≈15).\n")

    lines.append("### E4 Weight sensitivity")
    lines.append(f"- τ under ±25% perturbations: `{sensitivity_summary.get('tau_perturbed', {})}`")
    lines.append(f"- τ under leave-one-dim-out: `{sensitivity_summary.get('tau_leave_one_out', {})}`")
    lines.append(
        "- Claim: the ranking is stable under reasonable weight perturbations. "
        "Does *not* claim the weights are correct — the priors are not data-derived (see Limitations).\n"
    )

    lines.append("### E5 Determinism spot-check")
    lines.append(
        f"- identical across reps: `{determinism_summary.get('identical')}` "
        f"(distinct outputs: {determinism_summary.get('distinct_outputs')})\n"
    )

    lines.append("## 4. The tradeoff that bit\n")
    lines.append(tradeoff_md)
    lines.append("")

    lines.append("## 5. Limitations\n")
    lines.append("- N=6 ranking; conclusions are illustrative.")
    lines.append("- Gold N≈15; calibration confidence intervals are wide. Read directional, not significant.")
    lines.append("- Rubric weights are reasonable priors, not grounded in external data. E4 only proves robustness, not groundedness.")
    lines.append("- `disclosure_count` measures presence, not depth-of-disclosure (a single boolean disclosure counts the same as detailed exposure).")
    lines.append("- Snapshots are point-in-time; results apply to the captured state of each listing.")
    lines.append("- Single annotator on gold (no inter-rater data).")
    lines.append("- Cars24 'no_accident_history' platform-level promise is mapped to per-listing `accident_disclosed = none`. This is documented in spec §13 and should be read as a *modelling choice* rather than a per-listing extraction.\n")

    return "\n".join(lines)
