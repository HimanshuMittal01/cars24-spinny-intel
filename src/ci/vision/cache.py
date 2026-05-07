# src/ci/vision/cache.py
"""On-disk cache for inner inspector results.

Key = sha256(prompt_version + photo_sha256). Value = inspector findings JSON.
Bypass mode disables both reads and writes (used by E5 cold-cache runs).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


class InnerCache:
    def __init__(self, *, root: Path, prompt_version: str, bypass: bool = False):
        self.root = Path(root)
        self.prompt_version = prompt_version
        self.bypass = bypass
        if not bypass:
            self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, *, photo_sha: str) -> str:
        h = hashlib.sha256()
        h.update(self.prompt_version.encode())
        h.update(b":")
        h.update(photo_sha.encode())
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, *, photo_sha: str) -> dict | None:
        if self.bypass:
            return None
        p = self._path(self._key(photo_sha=photo_sha))
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def set(self, *, photo_sha: str, value: dict) -> None:
        if self.bypass:
            return
        p = self._path(self._key(photo_sha=photo_sha))
        # atomic write: tempfile + rename
        fd, tmp = tempfile.mkstemp(dir=str(self.root), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(value, f)
            os.replace(tmp, p)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
