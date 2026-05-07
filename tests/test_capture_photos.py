"""Tests for the photo capture script (mocked httpx)."""
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.capture_photos import capture_for_listing


@pytest.fixture
def fake_fixture_dir(tmp_path: Path):
    d = tmp_path / "cars24" / "TESTLID"
    d.mkdir(parents=True)
    (d / "page.html").write_text("<html>x</html>")
    (d / "captured_at.txt").write_text("2026-05-07T00:00:00Z")
    return d


@pytest.mark.asyncio
async def test_capture_dedupes_by_content_hash(fake_fixture_dir: Path):
    """Two URLs returning identical bytes should produce one photo file."""
    same_bytes = b"jpegbytes-A"
    extracted = [
        {"url": "https://x/a.jpg", "hint": "Exterior"},
        {"url": "https://x/b.jpg", "hint": "Interior"},  # diff URL, same bytes
    ]

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = same_bytes
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.aclose = AsyncMock()

    with patch("scripts.capture_photos.httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        await capture_for_listing(
            platform="cars24",
            listing_id="TESTLID",
            extracted_urls=extracted,
            fixture_root=fake_fixture_dir.parent.parent,
        )

    photos_dir = fake_fixture_dir / "photos"
    files = list(photos_dir.glob("*.jpg"))
    assert len(files) == 1  # dedup by content hash

    manifest = json.loads((fake_fixture_dir / "photos.json").read_text())
    assert len(manifest["photos"]) == 2  # both URLs recorded
    assert manifest["photos"][0]["sha256"] == manifest["photos"][1]["sha256"]
    expected_sha = hashlib.sha256(same_bytes).hexdigest()
    assert manifest["photos"][0]["sha256"] == expected_sha


@pytest.mark.asyncio
async def test_capture_writes_distinct_files_for_distinct_bytes(fake_fixture_dir: Path):
    """Different bytes per URL -> distinct files."""
    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"unique-" + url.encode()
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    extracted = [
        {"url": "https://x/a.jpg", "hint": "Exterior"},
        {"url": "https://x/b.jpg", "hint": "Interior"},
    ]
    with patch("scripts.capture_photos.httpx.AsyncClient", return_value=mock_client):
        await capture_for_listing(
            platform="cars24",
            listing_id="TESTLID",
            extracted_urls=extracted,
            fixture_root=fake_fixture_dir.parent.parent,
        )

    files = list((fake_fixture_dir / "photos").glob("*.jpg"))
    assert len(files) == 2
