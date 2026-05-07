from ci.eval.determinism import determinism_check
from ci.llm import FakeLLMClient


def test_determinism_passes_when_outputs_identical(tmp_path):
    """Use the real cars24 fixture — 3 reps should produce identical output."""
    fake = FakeLLMClient(canned_tool_input={})
    res = determinism_check(
        platform="cars24",
        listing_id="10041693110",
        client=fake,
        run_root=tmp_path / "runs",
        reps=3,
    )
    assert res.identical is True
    assert res.distinct_outputs == 1
