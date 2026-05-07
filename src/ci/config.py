from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
EVAL_DIR = ROOT / "eval"
RUNS_DIR = ROOT / "runs"
DOCS_DIR = ROOT / "docs"

MODEL_EXTRACTOR = "claude-sonnet-4-6"
EXTRACTOR_TEMPERATURE = 0.0
EXTRACTOR_MAX_TOKENS = 4096

# --- score_common weight table (§4, revised per §13 / §14) ---
WEIGHTS = {
    "km_driven": 35,
    "age_years": 25,
    "owners": 25,
    "accident_disclosed": 15,
}

# Accident severity ordering for rank-based scoring (higher = better).
# Used by ci.score._comparable_value to compare accident_disclosed across listings.
ACCIDENT_ORDER = {"none": 3, "minor": 2, "major": 1}

# Anchored bands and per-dim imputation anchors were dropped in §14 in favour
# of rank-based per-feature scoring. Magnitude lives in NormalizedListing's raw
# fields and is available for any post-hoc analysis; the scorer no longer
# encodes a "what is excellent" prior, only "best in this set is excellent".

# --- disclosure-eligible field set (§4 Disclosure metric, revised per §13) ---
DISCLOSURE_FIELDS = [
    "accident_history_detail",
    "inspection_per_section_ratings",
    "inspection_repair_statements",
    "tyre_condition_per_wheel",
    "service_history_records",
    "warranty_remaining_months",
    "noc_status",
    "rc_type",
    "insurance_type",
    "insurance_validity",
    "previous_use_type",
    "challan_status",
    "hypothecation_status",
    "inspection_photo_count",
    "per_listing_certification_tier",
    "buy_back_pricing",
    "market_price_delta",
]

PROMPT_VERSION = "v1.0"
