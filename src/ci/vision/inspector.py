# src/ci/vision/inspector.py
"""Inner inspector: one-shot VLM call examining a single photo for all aspects.

Returns a structured findings JSON. Cached on (prompt_version, photo_sha256).
The outer agent uses this as a tool implementation.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ci.vision.cache import InnerCache

INSPECTOR_PROMPT_VERSION = "v1"
INSPECTOR_MODEL = "claude-sonnet-4-6"

INSPECTOR_SYSTEM_PROMPT = """\
You inspect a single photo of a used car and classify visible-aspect severity.

For each visible aspect from this list:
  - exterior_panels (paint, dents, scratches)
  - interior_cabin (seats, plastics, headliner wear)
  - dashboard_console (steering, screen, controls)
  - tyres (tread, sidewall)
  - engine_bay

classify severity as one of:
  - pristine
  - light_wear
  - moderate
  - heavy
  - defect

Aspects that are NOT visible in this photo MUST NOT appear in `findings`.
Be conservative: if uncertain, omit the aspect rather than guess.

Return strict JSON matching:
  {
    "aspects_visible": [<aspect-name>, ...],
    "findings": {
      <aspect-name>: {"severity": <severity>, "evidence_note": <≤200 char string>}
    }
  }
"""


async def inspect_photo(
    *,
    photo_path: Path,
    photo_sha: str,
    client: Any,
    cache: InnerCache,
) -> dict:
    """Single-photo VLM call. Returns the model's structured findings dict."""
    cached = cache.get(photo_sha=photo_sha)
    if cached is not None:
        return cached

    img_bytes = photo_path.read_bytes()
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    response = await client.messages.create(
        model=INSPECTOR_MODEL,
        max_tokens=1024,
        system=INSPECTOR_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64,
                    },
                },
                {
                    "type": "text",
                    "text": "Inspect this photo. Return strict JSON per the schema.",
                },
            ],
        }],
    )

    # Extract text from first text block
    text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
    if not text_blocks:
        raise ValueError("inspector: no text block in response")
    raw = text_blocks[0].text
    # Tolerate code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    parsed = json.loads(raw)
    cache.set(photo_sha=photo_sha, value=parsed)
    return parsed
