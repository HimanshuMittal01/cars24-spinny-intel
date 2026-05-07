import json
from ci.trace import TraceStore
from ci.schemas import TraceEvent


def test_trace_store_writes_jsonl(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    ev = TraceEvent(
        run_id="r1", node="extract.cars24",
        timestamp="2026-05-06T10:00:00Z",
        input_hash="a", output_hash="b",
        latency_ms=100,
    )
    store.write(ev)
    contents = (tmp_path / "runs" / "r1" / "trace.jsonl").read_text().strip()
    assert json.loads(contents)["node"] == "extract.cars24"


def test_trace_store_appends_multiple(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    for n in ["a", "b", "c"]:
        store.write(TraceEvent(
            run_id="r1", node=n,
            timestamp="t", input_hash="i", output_hash="o", latency_ms=1,
        ))
    lines = (tmp_path / "runs" / "r1" / "trace.jsonl").read_text().strip().splitlines()
    assert [json.loads(l)["node"] for l in lines] == ["a", "b", "c"]


def test_trace_store_read_returns_events(tmp_path):
    store = TraceStore(run_dir=tmp_path / "runs" / "r1")
    ev = TraceEvent(
        run_id="r1", node="x",
        timestamp="t", input_hash="i", output_hash="o", latency_ms=42,
    )
    store.write(ev)
    events = list(store.read())
    assert len(events) == 1
    assert events[0].latency_ms == 42
