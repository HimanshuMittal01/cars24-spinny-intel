from ci.report import render_report, render_chart
from ci.schemas import RankRow


def _row(lid, plat, price, score, ratio, disclosure, imputed=None):
    return RankRow(
        listing_id=lid, platform=plat, price=price,
        score_common=score, ratio=ratio, disclosure_count=disclosure,
        imputed_dims=imputed or [],
    )


def test_render_report_contains_ranking_table():
    rows = [
        _row("a", "spinny", 900_000, 90.0, 10_000.0, 7),
        _row("b", "cars24", 1_000_000, 80.0, 12_500.0, 3),
    ]
    md = render_report(
        rows=rows,
        extraction_metrics_summary={"hallucination_rate": 0.0, "field_recall": {"price": 1.0}},
        calibration_summary={"mae_overall": 4.2, "spearman_overall": 0.78},
        sensitivity_summary={"tau_perturbed": {"km_driven+": 1.0}, "tau_leave_one_out": {"km_driven": 0.9}},
        determinism_summary={"identical": True, "distinct_outputs": 1},
        tradeoff_md="### The tradeoff that bit\n\nA real story from build.",
    )
    assert "Ranking" in md
    assert "spinny" in md and "cars24" in md
    # Ratio rendering — accept either with comma or without
    assert ("10,000" in md) or ("10000" in md)
    assert "Eval harness" in md
    assert "tradeoff" in md.lower()
    assert "Limitations" in md


def test_render_chart_writes_png(tmp_path):
    rows = [
        _row("a", "spinny", 900_000, 90.0, 10_000.0, 7),
        _row("b", "cars24", 1_000_000, 80.0, 12_500.0, 3),
        _row("c", "spinny", 1_100_000, 70.0, 15_714.0, 5),
    ]
    out = tmp_path / "chart.png"
    render_chart(rows, out)
    assert out.exists() and out.stat().st_size > 0
