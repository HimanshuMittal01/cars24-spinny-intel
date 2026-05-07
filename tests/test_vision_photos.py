"""URL extraction from per-platform raw fields."""
from ci.vision.photos import (
    extract_photo_urls_cars24,
    extract_photo_urls_spinny,
)


def test_extract_cars24_walks_media_gallery_categories():
    fields = {
        "media": {
            "gallery": {
                "Exterior": [
                    {"image": "https://media.cars24.com/hello-ar/a.jpg",
                     "label": "Front"},
                    {"image": "https://media.cars24.com/hello-ar/b.jpg",
                     "label": "Side"},
                ],
                "Interior": [
                    {"image": "https://media.cars24.com/hello-ar/c.jpg",
                     "label": "Dashboard"},
                ],
                "Tyres": [],  # empty list OK
            }
        }
    }
    urls = extract_photo_urls_cars24(fields)
    assert len(urls) == 3
    assert all("url" in u and "hint" in u for u in urls)
    assert urls[0]["hint"] == "Exterior"
    assert urls[2]["hint"] == "Interior"


def test_extract_cars24_dedupes_within_categories():
    fields = {
        "media": {
            "gallery": {
                "Exterior": [
                    {"image": "https://media.cars24.com/hello-ar/a.jpg"},
                    {"image": "https://media.cars24.com/hello-ar/a.jpg"},  # dup
                ],
            }
        }
    }
    urls = extract_photo_urls_cars24(fields)
    assert len(urls) == 1


def test_extract_cars24_handles_missing_gallery():
    assert extract_photo_urls_cars24({}) == []
    assert extract_photo_urls_cars24({"media": {}}) == []


def test_extract_spinny_walks_galleryV3_categories():
    fields = {
        "galleryV3": [
            {"category": "exterior", "images": [
                {"path": "//mda.spinny.com/abc/raw/file.JPG", "label": "Front"},
                {"path": "//mda.spinny.com/def/raw/file.JPG", "label": "Side"},
            ]},
            {"category": "interior", "images": [
                {"path": "//mda.spinny.com/ghi/raw/file.JPG", "label": "Dashboard"},
            ]},
            {"category": "engine", "images": []},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 3
    assert all(u["url"].startswith("https://mda.spinny.com/") for u in urls)
    assert urls[0]["hint"] == "exterior"
    assert urls[2]["hint"] == "interior"


def test_extract_spinny_falls_back_to_product_photos_when_galleryV3_empty():
    fields = {
        "galleryV3": [],
        "product_photos": {
            "images": {
                "exterior": [
                    {"file": {"url": "//mda.spinny.com/x/raw/file.JPG"}},
                    {"file": {"url": "//mda.spinny.com/y/raw/file.JPG"}},
                ],
                "interior": [
                    {"file": {"url": "//mda.spinny.com/z/raw/file.JPG"}},
                ],
            },
        },
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 3
    assert urls[0]["hint"] == "exterior"
    assert urls[2]["hint"] == "interior"
    assert all(u["url"].startswith("https://") for u in urls)


def test_extract_spinny_dedupes_paths():
    fields = {
        "galleryV3": [
            {"category": "exterior", "images": [
                {"path": "//x/a.jpg"},
                {"path": "//x/a.jpg"},  # dup
            ]},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 1


def test_extract_spinny_handles_missing_both():
    assert extract_photo_urls_spinny({}) == []
