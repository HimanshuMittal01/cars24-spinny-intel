from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
EVAL_DIR = ROOT / "eval"
RUNS_DIR = ROOT / "runs"
DOCS_DIR = ROOT / "docs"

# --- score_common weight table ---
WEIGHTS = {
    "km_driven": 35,
    "age_years": 25,
    "owners": 25,
    "accident_disclosed": 15,
}

# Accident severity ordering for rank-based scoring (higher = better).
# Used by ci.score._comparable_value to compare accident_disclosed across listings.
ACCIDENT_ORDER = {"none": 3, "minor": 2, "major": 1}

# Per-feature scoring uses rank-based ordering (best in the set = 100, worst
# = 0, others linearly interpolated by rank); see src/ci/score.py.

# --- disclosure-eligible field set ---
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
