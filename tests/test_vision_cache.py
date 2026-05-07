# tests/test_vision_cache.py
"""On-disk cache for inner inspector results."""
import json
from pathlib import Path

from ci.vision.cache import InnerCache


def test_get_returns_none_on_miss(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1")
    assert c.get(photo_sha="abc") is None


def test_set_then_get_round_trips(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1")
    payload = {"aspects_visible": ["tyres"], "findings": {"tyres": {"severity": "moderate"}}}
    c.set(photo_sha="abc", value=payload)
    assert c.get(photo_sha="abc") == payload


def test_different_prompt_versions_dont_collide(tmp_path: Path):
    c1 = InnerCache(root=tmp_path, prompt_version="v1")
    c2 = InnerCache(root=tmp_path, prompt_version="v2")
    c1.set(photo_sha="abc", value={"x": 1})
    c2.set(photo_sha="abc", value={"x": 2})
    assert c1.get(photo_sha="abc") == {"x": 1}
    assert c2.get(photo_sha="abc") == {"x": 2}


def test_bypass_mode_always_misses_and_does_not_write(tmp_path: Path):
    c = InnerCache(root=tmp_path, prompt_version="v1", bypass=True)
    c.set(photo_sha="abc", value={"x": 1})
    assert c.get(photo_sha="abc") is None
    # confirm no files written
    assert not list(tmp_path.glob("*.json"))
