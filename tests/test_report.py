from ci.report import render_chart
from ci.schemas import RankRow


def _row(lid, plat, price, score, ratio, disclosure, imputed=None):
    return RankRow(
        listing_id=lid, platform=plat, price=price,
        rule_score=score, ratio=ratio, disclosure_count=disclosure,
        imputed_dims=imputed or [],
    )


def test_render_chart_writes_png(tmp_path):
    rows = [
        _row("a", "spinny", 900_000, 90.0, 10_000.0, 7),
        _row("b", "cars24", 1_000_000, 80.0, 12_500.0, 3),
        _row("c", "spinny", 1_100_000, 70.0, 15_714.0, 5),
    ]
    out = tmp_path / "chart.png"
    render_chart(rows, out)
    assert out.exists() and out.stat().st_size > 0
