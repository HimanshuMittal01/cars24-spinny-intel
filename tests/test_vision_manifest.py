"""Read/write helpers for fixtures/<platform>/<lid>/photos.json."""
import json
from pathlib import Path

from ci.vision.manifest import read_manifest, write_manifest


def test_round_trip(tmp_path: Path):
    p = tmp_path / "photos.json"
    data = {
        "captured_at": "2026-05-07T00:00:00Z",
        "photos": [
            {"idx": 0, "sha256": "ab12", "source_url": "https://x/a.jpg", "hint": "Exterior"},
            {"idx": 1, "sha256": "cd34", "source_url": "https://x/b.jpg", "hint": None},
        ],
    }
    write_manifest(p, data)
    assert read_manifest(p) == data


def test_read_missing_returns_none(tmp_path: Path):
    assert read_manifest(tmp_path / "nope.json") is None
