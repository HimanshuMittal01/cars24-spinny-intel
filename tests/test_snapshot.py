import pytest
from ci.snapshot import load_snapshot, list_snapshots, SnapshotMissing


def test_load_snapshot_returns_html_and_metadata(tmp_path, monkeypatch):
    fix = tmp_path / "fixtures" / "cars24" / "abc"
    fix.mkdir(parents=True)
    (fix / "page.html").write_text("<html>hi</html>")
    (fix / "captured_at.txt").write_text("2026-05-06T10:00:00Z")

    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    snap = load_snapshot("cars24", "abc")
    assert snap.html == "<html>hi</html>"
    assert snap.captured_at == "2026-05-06T10:00:00Z"
    assert snap.platform == "cars24"
    assert snap.listing_id == "abc"


def test_load_snapshot_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")
    with pytest.raises(SnapshotMissing):
        load_snapshot("cars24", "ghost")


def test_list_snapshots_per_platform(tmp_path, monkeypatch):
    for plat, lid in [("cars24", "a"), ("cars24", "b"), ("spinny", "c")]:
        fix = tmp_path / "fixtures" / plat / lid
        fix.mkdir(parents=True)
        (fix / "page.html").write_text("x")
        (fix / "captured_at.txt").write_text("t")
    monkeypatch.setattr("ci.snapshot.FIXTURES_DIR", tmp_path / "fixtures")

    assert sorted(list_snapshots("cars24")) == ["a", "b"]
    assert list_snapshots("spinny") == ["c"]
