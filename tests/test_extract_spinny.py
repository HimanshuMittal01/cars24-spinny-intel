from ci.extract.spinny import extract_spinny
from ci.llm import FakeLLMClient
from ci.snapshot import load_snapshot


def test_spinny_extractor_parses_real_fixture():
    snap = load_snapshot("spinny", "28476005")
    fake = FakeLLMClient(canned_tool_input={})  # unused; signature compatibility
    raw = extract_spinny(snap, fake)
    assert raw.platform == "spinny"
    assert raw.listing_id == "28476005"
    # Anchored values verified by direct inspection of fixture:
    assert raw.fields["productPrice"] == 1347000.0
    assert raw.fields["productMileage"] == 33191
    assert raw.fields["no_of_owners"] == "1st"
    assert raw.fields["registration_year"] == 2022
    assert raw.fields["make_year"] == 2022
    assert raw.fields["fuel_type"] == "petrol"
    assert raw.fields["transmission"] == "automatic"
    assert raw.fields["procurement_category"] == "assured"
    assert raw.fields["is_assured"] is True
    assert raw.fields["inspection_report"]["report"]["summary"]["is_accidental"] is False
    # the LLM client should NOT have been called
    assert len(fake.calls) == 0


def test_spinny_extractor_raises_on_missing_initial_state(tmp_path, monkeypatch):
    fix = tmp_path / "fixtures" / "spinny" / "broken"
    fix.mkdir(parents=True)
    (fix / "page.html").write_text("<html>no initial state</html>")
    (fix / "captured_at.txt").write_text("2026-05-07T10:00:00Z")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    snap = load_snapshot("spinny", "broken")
    fake = FakeLLMClient(canned_tool_input={})
    import pytest
    with pytest.raises(ValueError, match="spinny"):
        extract_spinny(snap, fake)
