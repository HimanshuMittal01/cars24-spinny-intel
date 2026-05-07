import json

from ci.pipeline import run_pipeline


def test_pipeline_runs_end_to_end_against_real_fixtures(tmp_path):
    rows = run_pipeline(
        listings=[
            ("cars24", "10041693110"),
            ("spinny", "28476005"),
        ],
        ranking_listing_ids={"10041693110", "28476005"},
        run_dir=tmp_path / "runs" / "r1",
        today_year=2026,
        enable_vision=False,
    )
    assert len(rows) == 2
    assert all(r.rule_score > 0 for r in rows)
    # Sorted descending by composite (= rule_score when no vision)
    assert rows[0].rule_score >= rows[1].rule_score


def test_pipeline_writes_trace_per_node(tmp_path):
    run_pipeline(
        listings=[("cars24", "10041693110")],
        ranking_listing_ids={"10041693110"},
        run_dir=tmp_path / "runs" / "r2",
        today_year=2026,
        enable_vision=False,
    )
    trace_path = tmp_path / "runs" / "r2" / "trace.jsonl"
    assert trace_path.exists()
    nodes = [json.loads(l)["node"] for l in trace_path.read_text().splitlines() if l.strip()]
    assert "snapshot.load.cars24" in nodes
    assert "extract.cars24" in nodes
    assert "normalize.cars24" in nodes
    assert "score" in nodes
    assert "rank" in nodes
