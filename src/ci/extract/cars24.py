"""Cars24 listing extractor.

Strategy: parse Next.js streaming-SSR payloads (`self.__next_f.push([1,"..."])`)
to find the per-listing `content` object that contains all structured fields.
"""

import json
import re
from typing import Any

from ci.schemas import RawListing
from ci.snapshot import Snapshot

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.DOTALL)
_ANCHOR = '"odometerReading"'


def _decode_pushes(html: str) -> str:
    """Concatenate decoded payloads from all __next_f.push calls."""
    pushes = _PUSH_RE.findall(html)
    return "".join(p.encode().decode("unicode_escape") for p in pushes)


def _find_listing_object(decoded: str) -> dict[str, Any]:
    """Locate the listing-detail JSON object anchored on `_ANCHOR`."""
    idx = decoded.find(_ANCHOR)
    if idx < 0:
        raise ValueError(
            f"cars24 extractor: anchor {_ANCHOR!r} not found in __next_f payloads"
        )

    # Walk backward from anchor to find the enclosing object's open brace.
    depth = 0
    start = -1
    for i in range(idx, -1, -1):
        ch = decoded[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start < 0:
        raise ValueError("cars24 extractor: no enclosing { for content object")

    # Walk forward to find the matching close brace, respecting strings.
    depth = 0
    in_string = False
    escape = False
    end = -1
    for j in range(start, len(decoded)):
        ch = decoded[j]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end < 0:
        raise ValueError("cars24 extractor: no matching } for content object")

    blob = decoded[start:end]
    return json.loads(blob)


def extract_cars24(snapshot: Snapshot) -> RawListing:
    """Extract structured fields from a Cars24 listing snapshot."""
    fields = _find_listing_object(_decode_pushes(snapshot.html))
    return RawListing(
        platform="cars24",
        listing_id=snapshot.listing_id,
        url=f"snapshot://{snapshot.listing_id}",
        captured_at=snapshot.captured_at,
        fields=fields,
    )
