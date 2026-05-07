"""Download listing photos to fixtures/<platform>/<listing_id>/photos/<sha>.jpg.

Per spec §4. Idempotent — re-running skips already-on-disk hashes. Writes a
photos.json manifest alongside.

Usage:
  uv run python -m scripts.capture_photos cars24 10182490193
  uv run python -m scripts.capture_photos --all  # all 16 active fixtures
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ci.config import EVAL_DIR, FIXTURES_DIR
from ci.extract.cars24 import extract_cars24
from ci.extract.spinny import extract_spinny
from ci.snapshot import load_snapshot
from ci.vision.manifest import write_manifest
from ci.vision.photos import extract_photo_urls_cars24, extract_photo_urls_spinny


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    return resp.content


async def capture_for_listing(
    *,
    platform: str,
    listing_id: str,
    extracted_urls: list[dict],
    fixture_root: Path,
) -> dict:
    """Download all extracted_urls' bytes, dedupe by sha256, write photos/ + photos.json."""
    listing_dir = fixture_root / platform / listing_id
    photos_dir = listing_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient() as client:
        tasks = [_download(client, e["url"]) for e in extracted_urls]
        all_bytes = await asyncio.gather(*tasks, return_exceptions=True)

    photos_meta: list[dict] = []
    for idx, (entry, body) in enumerate(zip(extracted_urls, all_bytes)):
        if isinstance(body, Exception):
            print(f"  WARN: skipping {entry['url']}: {body}")
            continue
        sha = hashlib.sha256(body).hexdigest()
        out_path = photos_dir / f"{sha}.jpg"
        if not out_path.exists():
            out_path.write_bytes(body)
        photos_meta.append({
            "idx": idx,
            "sha256": sha,
            "source_url": entry["url"],
            "hint": entry.get("hint"),
        })

    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "photos": photos_meta,
    }
    write_manifest(listing_dir / "photos.json", manifest)
    return manifest


def _active_listings() -> list[tuple[str, str]]:
    """Union of gold (10) + ranking (6) = 16 active fixtures."""
    gold = [
        json.loads(line)
        for line in (EVAL_DIR / "gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ranking = json.loads((EVAL_DIR / "ranking_listings.json").read_text())
    return [(g["platform"], g["listing_id"]) for g in gold] + \
           [(r["platform"], r["listing_id"]) for r in ranking]


async def _main_async(args: argparse.Namespace) -> None:
    if args.all:
        targets = _active_listings()
    else:
        targets = [(args.platform, args.listing_id)]

    for platform, lid in targets:
        print(f"--- {platform}/{lid} ---")
        snap = load_snapshot(platform, lid)
        if platform == "cars24":
            raw = extract_cars24(snap)
            urls = extract_photo_urls_cars24(raw.fields)
        elif platform == "spinny":
            raw = extract_spinny(snap)
            urls = extract_photo_urls_spinny(raw.fields)
        else:
            raise ValueError(f"unknown platform: {platform}")

        if not urls:
            print(f"  no photo URLs extracted; skipping")
            continue

        manifest = await capture_for_listing(
            platform=platform, listing_id=lid,
            extracted_urls=urls, fixture_root=FIXTURES_DIR,
        )
        print(f"  {len(manifest['photos'])} photos, "
              f"{len(set(p['sha256'] for p in manifest['photos']))} unique")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("platform", nargs="?", choices=["cars24", "spinny"])
    p.add_argument("listing_id", nargs="?")
    p.add_argument("--all", action="store_true",
                   help="capture for all 16 active fixtures (10 gold + 6 ranking)")
    args = p.parse_args()
    if not args.all and (not args.platform or not args.listing_id):
        p.error("specify <platform> <listing_id> or --all")
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
