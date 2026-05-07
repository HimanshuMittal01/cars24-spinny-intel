from ci.extract.cars24 import extract_cars24
from ci.snapshot import load_snapshot


def test_cars24_extractor_parses_real_fixture():
    snap = load_snapshot("cars24", "10041693110")
    raw = extract_cars24(snap)
    assert raw.platform == "cars24"
    assert raw.listing_id == "10041693110"
    # Anchored values verified by direct inspection of fixture:
    assert raw.fields["listingPrice"] == 950000
    assert raw.fields["odometerReading"] == 50673
    assert raw.fields["year"] == 2020
    assert raw.fields["ownerNumber"] == 2
    assert raw.fields["fuelType"] == "Petrol"
    assert raw.fields["transmission"] == "Automatic"


def test_cars24_extractor_raises_on_missing_anchor(tmp_path, monkeypatch):
    fix = tmp_path / "fixtures" / "cars24" / "broken"
    fix.mkdir(parents=True)
    (fix / "page.html").write_text("<html>no listing data</html>")
    (fix / "captured_at.txt").write_text("2026-05-07T10:00:00Z")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    snap = load_snapshot("cars24", "broken")
    import pytest
    with pytest.raises(ValueError, match="cars24"):
        extract_cars24(snap)
