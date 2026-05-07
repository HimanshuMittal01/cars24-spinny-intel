from pathlib import Path

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
            [r.rule_score for r in sub],
            [r.price / 1e5 for r in sub],
            marker=marker, color=color, label=plat, s=80,
        )
        for r in sub:
            ax.annotate(r.listing_id, (r.rule_score, r.price / 1e5),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel("condition score (rank-based, 0–100, relative to this set)")
    ax.set_ylabel("price (₹ lakh)")
    ax.set_title("Cars24 vs Spinny — price vs condition score")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
