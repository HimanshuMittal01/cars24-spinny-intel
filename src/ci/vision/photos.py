"""Per-platform photo URL extraction from raw listing fields.

Each function takes the platform's `RawListing.fields` dict and returns a list
of `{"url": str, "hint": str | None}` dicts representing distinct listing
photos. Hints are platform-specific category labels useful for the agent.
"""
from __future__ import annotations

from typing import Any


def extract_photo_urls_cars24(fields: dict[str, Any]) -> list[dict]:
    """Walk media.gallery.{Highlights, Exterior, Interior, Tyres, Features, ...}.

    Each gallery entry is a dict with at least an `image` URL. We use the
    category name as the `hint`. Within each category, dedupe by URL string.
    """
    out: list[dict] = []
    seen: set[str] = set()
    gallery = (fields.get("media") or {}).get("gallery") or {}
    for category, entries in gallery.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("image")
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "hint": category})
    return out


def extract_photo_urls_spinny(fields: dict[str, Any]) -> list[dict]:
    """Prefer `galleryV3` (richer + sectioned); fall back to `product_photos`.

    galleryV3 entries have a `url` and an optional `section` label; product_photos
    have only a `url`.
    """
    g3 = fields.get("galleryV3")
    if isinstance(g3, list) and g3:
        out: list[dict] = []
        seen: set[str] = set()
        for entry in g3:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "hint": entry.get("section")})
        return out

    pp = fields.get("product_photos")
    if isinstance(pp, list):
        out2: list[dict] = []
        seen2: set[str] = set()
        for entry in pp:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not isinstance(url, str) or not url or url in seen2:
                continue
            seen2.add(url)
            out2.append({"url": url, "hint": None})
        return out2

    return []
