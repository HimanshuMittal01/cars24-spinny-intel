# src/ci/report.py — full replacement
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ci.schemas import RankRow


def _x_value(r: RankRow) -> float:
    """Prefer composite_score (when vision ran), fall back to rule_score."""
    return r.composite_score if r.composite_score is not None else r.rule_score


def render_chart(rows: list[RankRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    has_visual = any(r.composite_score is not None for r in rows)
    x_label = (
        "composite score (α·rule + (1-α)·visual, set-relative)"
        if has_visual else
        "condition score (rank-based, 0–100, relative to this set)"
    )
    for plat, marker, color in [("cars24", "o", "#1f77b4"), ("spinny", "s", "#d62728")]:
        sub = [r for r in rows if r.platform == plat]
        if not sub:
            continue
        ax.scatter(
            [_x_value(r) for r in sub],
            [r.price / 1e5 for r in sub],
            marker=marker, color=color, label=plat, s=80,
        )
        for r in sub:
            ax.annotate(r.listing_id, (_x_value(r), r.price / 1e5),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel(x_label)
    ax.set_ylabel("price (₹ lakh)")
    title = "Cars24 vs Spinny — price vs " + ("composite" if has_visual else "rule") + " score"
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
