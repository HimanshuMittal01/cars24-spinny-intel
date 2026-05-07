"""Generate the final report from the latest pipeline run.

Reads:
- runs/<latest>/ranking.json
- eval/gold.jsonl                 (optional)
- runs/<latest>/{extraction,calibration,sensitivity,determinism}.json (optional, populated by other harnesses)
- docs/tradeoffs.md

Writes:
- docs/report.md
- docs/figures/ranking.png
"""
import json

from ci.config import DOCS_DIR, RUNS_DIR
from ci.report import render_chart, render_report
from ci.schemas import RankRow


def _latest_run():
    runs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("no runs/ — execute scripts/run_pipeline.py first")
    return runs[-1]


def _read_optional(path):
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    run = _latest_run()
    rows = [RankRow.model_validate(d) for d in json.loads((run / "ranking.json").read_text())]

    extraction_summary = _read_optional(run / "extraction.json")
    calibration_summary = _read_optional(run / "calibration.json")
    sensitivity_summary = _read_optional(run / "sensitivity.json")
    determinism_summary = _read_optional(run / "determinism.json")

    tradeoff_path = DOCS_DIR / "tradeoffs.md"
    tradeoff_md = tradeoff_path.read_text() if tradeoff_path.exists() else "_no entries yet — see docs/tradeoffs.md_"

    figures_dir = DOCS_DIR / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    render_chart(rows, figures_dir / "ranking.png")

    md = render_report(
        rows=rows,
        extraction_metrics_summary=extraction_summary,
        calibration_summary=calibration_summary,
        sensitivity_summary=sensitivity_summary,
        determinism_summary=determinism_summary,
        tradeoff_md=tradeoff_md,
    )
    (DOCS_DIR / "report.md").write_text(md)
    print(f"wrote {DOCS_DIR / 'report.md'} and {figures_dir / 'ranking.png'}")


if __name__ == "__main__":
    main()
