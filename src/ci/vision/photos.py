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
    """Prefer `galleryV3` (richer + sectioned); fall back to `product_photos.images`.

    galleryV3 is a list of category objects, each with an `images` list whose
    entries have a `path` field. Paths are protocol-relative (//host/...) so we
    prepend `https:`. product_photos has a different shape (dict-of-dicts);
    we walk product_photos.images.<section> -> [{file: {url}}, ...] as fallback.
    """
    out: list[dict] = []
    seen: set[str] = set()

    g3 = fields.get("galleryV3")
    if isinstance(g3, list) and g3:
        for entry in g3:
            if not isinstance(entry, dict):
                continue
            category = entry.get("category")
            images = entry.get("images", [])
            if not isinstance(images, list):
                continue
            for img in images:
                if not isinstance(img, dict):
                    continue
                path = img.get("path")
                if not isinstance(path, str) or not path:
                    continue
                url = "https:" + path if path.startswith("//") else path
                if url in seen:
                    continue
                seen.add(url)
                out.append({"url": url, "hint": category})
        if out:
            return out

    pp = fields.get("product_photos")
    if isinstance(pp, dict):
        images_by_section = pp.get("images")
        if isinstance(images_by_section, dict):
            for section, entries in images_by_section.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    file_obj = entry.get("file")
                    if not isinstance(file_obj, dict):
                        continue
                    url = file_obj.get("url")
                    if not isinstance(url, str) or not url:
                        continue
                    if url.startswith("//"):
                        url = "https:" + url
                    if url in seen:
                        continue
                    seen.add(url)
                    out.append({"url": url, "hint": section})
        return out

    return []
