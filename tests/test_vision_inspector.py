# tests/test_vision_inspector.py
"""Inner inspector: one-shot VLM call for a single photo."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ci.vision.cache import InnerCache
from ci.vision.inspector import inspect_photo, INSPECTOR_PROMPT_VERSION


def _mock_client_returning(payload: dict) -> MagicMock:
    """Construct a mock anthropic AsyncAnthropic that returns a single text block."""
    client = MagicMock()
    response = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response.content = [block]
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def fake_photo(tmp_path: Path) -> Path:
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake jpeg bytes")
    return p


async def test_inspect_photo_returns_parsed_findings(fake_photo: Path, tmp_path: Path):
    payload = {
        "aspects_visible": ["exterior_panels"],
        "findings": {
            "exterior_panels": {"severity": "light_wear", "evidence_note": "scuff"}
        },
    }
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache", prompt_version=INSPECTOR_PROMPT_VERSION)
    result = await inspect_photo(
        photo_path=fake_photo, photo_sha="abc",
        client=client, cache=cache,
    )
    assert result == payload
    client.messages.create.assert_awaited_once()


async def test_inspect_photo_uses_cache_on_second_call(fake_photo: Path, tmp_path: Path):
    payload = {"aspects_visible": [], "findings": {}}
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache", prompt_version=INSPECTOR_PROMPT_VERSION)

    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    assert client.messages.create.await_count == 1  # second call hit cache


async def test_inspect_photo_skips_cache_in_bypass_mode(fake_photo: Path, tmp_path: Path):
    payload = {"aspects_visible": [], "findings": {}}
    client = _mock_client_returning(payload)
    cache = InnerCache(root=tmp_path / "cache",
                       prompt_version=INSPECTOR_PROMPT_VERSION, bypass=True)

    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    await inspect_photo(photo_path=fake_photo, photo_sha="abc", client=client, cache=cache)
    assert client.messages.create.await_count == 2  # both calls hit the API
