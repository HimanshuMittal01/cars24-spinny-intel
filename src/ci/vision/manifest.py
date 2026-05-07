"""Read/write fixtures/<platform>/<lid>/photos.json manifest."""
from __future__ import annotations

import json
from pathlib import Path


def read_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
