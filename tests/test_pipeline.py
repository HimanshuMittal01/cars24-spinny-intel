import json

from ci.pipeline import run_pipeline


def test_pipeline_runs_end_to_end_against_real_fixtures(tmp_path):
    """Use the real fixtures saved during the reality check.

    Exercises both extractors against actual platform HTML.
    """
    rows = run_pipeline(
        ranking_listings=[
            ("cars24", "10041693110"),
            ("spinny", "28476005"),
        ],
        run_dir=tmp_path / "runs" / "r1",
        today_year=2026,
    )
    assert len(rows) == 2
    assert all(r.score_common > 0 for r in rows)
    # Sorted ascending by ratio
    assert rows[0].ratio <= rows[1].ratio


def test_pipeline_writes_trace_per_node(tmp_path):
    run_pipeline(
        ranking_listings=[("cars24", "10041693110")],
        run_dir=tmp_path / "runs" / "r2",
        today_year=2026,
    )
    trace_path = tmp_path / "runs" / "r2" / "trace.jsonl"
    assert trace_path.exists()
    nodes = [json.loads(l)["node"] for l in trace_path.read_text().splitlines() if l.strip()]
    # At minimum: snapshot.load, extract, normalize, score, rank
    assert "snapshot.load.cars24" in nodes
    assert "extract.cars24" in nodes
    assert "normalize.cars24" in nodes
    assert "score" in nodes
    assert "rank" in nodes
