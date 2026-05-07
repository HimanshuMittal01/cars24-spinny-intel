from dataclasses import dataclass

from ci.config import FIXTURES_DIR


class SnapshotMissing(FileNotFoundError):
    pass


@dataclass
class Snapshot:
    platform: str
    listing_id: str
    html: str
    captured_at: str


def load_snapshot(platform: str, listing_id: str) -> Snapshot:
    fix = FIXTURES_DIR / platform / listing_id
    if not fix.exists():
        raise SnapshotMissing(f"{platform}/{listing_id}")
    html_path = fix / "page.html"
    cap_path = fix / "captured_at.txt"
    if not html_path.exists() or not cap_path.exists():
        raise SnapshotMissing(f"incomplete snapshot at {fix}")
    return Snapshot(
        platform=platform,
        listing_id=listing_id,
        html=html_path.read_text(),
        captured_at=cap_path.read_text().strip(),
    )


def list_snapshots(platform: str) -> list[str]:
    base = FIXTURES_DIR / platform
    if not base.exists():
        return []
    return [d.name for d in base.iterdir() if d.is_dir()]
