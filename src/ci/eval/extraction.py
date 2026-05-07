"""Extraction quality evaluation: per-field recall vs. gold records.

This module measures how well the extraction system recovers key fields
(price, km_driven, age_years, owners) by comparing normalized values
against gold records, which are similarly normalized.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ci.normalize import normalize
from ci.schemas import GoldRecord, NormalizedListing, RawListing

# Per-field absolute tolerance for considering two numeric values equal.
TOLERANCE: dict[str, int | float] = {
    "price": 1,           # exact INR price
    "km_driven": 500,     # small tolerance for rounding
    "age_years": 0,       # exact
    "owners": 0,          # exact
}

CHECKED_FIELDS = ("price", "km_driven", "age_years", "owners")


@dataclass
class ExtractionMetrics:
    field_recall: dict[str, float] = field(default_factory=dict)
    field_recall_per_platform: dict[str, dict[str, float]] = field(default_factory=dict)
    n: int = 0


def _approx_equal(a, b, tol) -> bool:
    """Compare two values within tolerance.

    - None == None
    - int/float compared with tolerance
    - other types compared with ==
    """
    if a is None or b is None:
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def _gold_to_normalized(gold: GoldRecord, today_year: int) -> NormalizedListing:
    """Convert a GoldRecord to NormalizedListing by running normalize() on its full_fields."""
    raw = RawListing(
        platform=gold.platform,
        listing_id=gold.listing_id,
        url=f"snapshot://{gold.listing_id}",
        captured_at="gold",
        fields=dict(gold.full_fields),
    )
    return normalize(raw, today_year=today_year)


def _compute_recalls(
    pairs: list[tuple[NormalizedListing, NormalizedListing]],
) -> dict[str, float]:
    """For each CHECKED_FIELDS, compute fraction of pairs where system matches gold (within tolerance).

    Only considers pairs where gold has a non-None value for the field.
    Returns 1.0 for any field with no gold values (vacuous truth).
    """
    out: dict[str, float] = {}
    n = len(pairs)
    if n == 0:
        return {k: 1.0 for k in CHECKED_FIELDS}
    for fkey in CHECKED_FIELDS:
        match = 0
        present = 0
        for sys_n, gold_n in pairs:
            g = getattr(gold_n, fkey)
            if g is None:
                continue
            present += 1
            s = getattr(sys_n, fkey)
            if _approx_equal(s, g, TOLERANCE.get(fkey, 0)):
                match += 1
        out[fkey] = (match / present) if present else 1.0
    return out


def extraction_metrics(
    pairs: list[tuple[NormalizedListing, GoldRecord]],
    today_year: int | None = None,
) -> ExtractionMetrics:
    """Compute extraction quality metrics vs. gold records.

    Args:
        pairs: List of (system_normalized, gold_record) tuples.
        today_year: Year to use for age calculation (defaults to current UTC year).

    Returns:
        ExtractionMetrics with field_recall (overall and per-platform).
    """
    today_year = today_year or datetime.now(timezone.utc).year

    # Convert each gold to normalized.
    normalized_pairs: list[tuple[NormalizedListing, NormalizedListing]] = [
        (sys_n, _gold_to_normalized(g, today_year)) for sys_n, g in pairs
    ]

    overall = _compute_recalls(normalized_pairs)

    per_platform: dict[str, dict[str, float]] = {}
    platforms = set(s.platform for s, _ in pairs)
    for p in platforms:
        sub = [pp for pp in normalized_pairs if pp[0].platform == p]
        per_platform[p] = _compute_recalls(sub)

    return ExtractionMetrics(
        field_recall=overall,
        field_recall_per_platform=per_platform,
        n=len(pairs),
    )
