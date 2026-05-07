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


def test_extract_spinny_prefers_galleryV3():
    fields = {
        "galleryV3": [
            {"url": "https://spn-mda.spinny.com/img/a/raw/file.jpg",
             "section": "exterior"},
            {"url": "https://spn-mda.spinny.com/img/b/raw/file.jpg",
             "section": "interior"},
        ],
        "product_photos": [
            {"url": "https://spn-mda.spinny.com/img/Z/raw/file.jpg"},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 2  # galleryV3 wins
    assert urls[0]["hint"] == "exterior"


def test_extract_spinny_falls_back_to_product_photos():
    fields = {
        "product_photos": [
            {"url": "https://spn-mda.spinny.com/img/x/raw/file.jpg"},
            {"url": "https://spn-mda.spinny.com/img/y/raw/file.jpg"},
        ],
    }
    urls = extract_photo_urls_spinny(fields)
    assert len(urls) == 2
    assert urls[0]["hint"] is None


def test_extract_spinny_handles_missing_both():
    assert extract_photo_urls_spinny({}) == []
