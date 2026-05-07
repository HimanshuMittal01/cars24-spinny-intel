"""
One-time snapshot collection.

Usage:
    uv run python scripts/collect_snapshots.py <platform> <listing_id> <url>

Saves to fixtures/<platform>/<listing_id>/{page.html, captured_at.txt, url.txt}.
The operator is expected to provide URLs from the public listing pages
of Cars24 / Spinny for Hyundai Creta in Delhi-NCR within ₹8-14L.

This script does NOT bypass any access control. It does a single GET
with a normal browser User-Agent. If the page requires JS rendering,
the operator should save the rendered HTML manually via browser
"Save Page As" and place it at fixtures/<platform>/<listing_id>/page.html
plus write captured_at.txt by hand.
"""
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ci.config import FIXTURES_DIR

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def collect(platform: str, listing_id: str, url: str) -> Path:
    if platform not in ("cars24", "spinny"):
        raise SystemExit(f"unsupported platform: {platform}")
    out_dir = FIXTURES_DIR / platform / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    (out_dir / "page.html").write_text(html)
    (out_dir / "captured_at.txt").write_text(
        datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    (out_dir / "url.txt").write_text(url)
    print(f"saved {out_dir}")
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    collect(sys.argv[1], sys.argv[2], sys.argv[3])
