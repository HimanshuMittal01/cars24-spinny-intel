"""Spinny listing extractor.

Strategy: parse `window.__INITIAL_STATE__` (a JS object literal embedded in
the HTML) and navigate to `product.pageData.productDetail` for the per-listing
fields. The literal uses JS-only syntax (`!0`/`!1` for booleans, `void 0` for
null, unquoted numeric object keys); a small preprocessor converts to JSON5,
which is then parsed with the `json5` package.
"""

import re
from typing import Any

import json5

from ci.schemas import RawListing
from ci.snapshot import Snapshot

_INITIAL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__=(.+?)(?:,window\.__STATIC_CONFIG__|;window\.|</script>)",
    re.DOTALL,
)


def _transform_js_to_json5(s: str) -> str:
    """Convert JS-literal-only constructs into json5-parseable form.

    Handles:
      !0  -> true
      !1  -> false
      void 0  -> null
      {12: -> {"12":   (and ,12: -> ,"12":)
    String contents are preserved verbatim (uses a single-quote / double-quote
    aware state machine).
    """
    out: list[str] = []
    i, n = 0, len(s)
    in_str = False
    quote = ""
    escape = False
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "!" and i + 1 < n and s[i + 1] in "01":
            out.append("true" if s[i + 1] == "0" else "false")
            i += 2
            continue
        if ch == "v" and s[i : i + 5] == "void ":
            j = i + 5
            while j < n and s[j].isdigit():
                j += 1
            out.append("null")
            i = j
            continue
        if ch in ("{", ","):
            out.append(ch)
            j = i + 1
            while j < n and s[j] in " \t\n\r":
                j += 1
            k_start = j
            while j < n and s[j].isdigit():
                j += 1
            if j > k_start and j < n and s[j] == ":":
                out.append('"' + s[k_start:j] + '"')
                i = j
                continue
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_initial_state(html: str) -> dict[str, Any]:
    m = _INITIAL_STATE_RE.search(html)
    if not m:
        raise ValueError("spinny extractor: window.__INITIAL_STATE__ not found")
    transformed = _transform_js_to_json5(m.group(1))
    return json5.loads(transformed)


def _navigate_to_product_detail(state: dict[str, Any]) -> dict[str, Any]:
    try:
        return state["product"]["pageData"]["productDetail"]
    except (KeyError, TypeError) as e:
        raise ValueError(
            f"spinny extractor: product.pageData.productDetail not found: {e}"
        )


def extract_spinny(snapshot: Snapshot) -> RawListing:
    """Extract structured fields from a Spinny listing snapshot."""
    state = _parse_initial_state(snapshot.html)
    fields = _navigate_to_product_detail(state)
    return RawListing(
        platform="spinny",
        listing_id=snapshot.listing_id,
        url=f"snapshot://{snapshot.listing_id}",
        captured_at=snapshot.captured_at,
        fields=fields,
    )
