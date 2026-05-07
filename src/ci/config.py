from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
EVAL_DIR = ROOT / "eval"
RUNS_DIR = ROOT / "runs"
DOCS_DIR = ROOT / "docs"

MODEL_EXTRACTOR = "claude-sonnet-4-6"
EXTRACTOR_TEMPERATURE = 0.0
EXTRACTOR_MAX_TOKENS = 4096

# --- score_common weight table (§4, revised per §13) ---
WEIGHTS = {
    "km_driven": 35,
    "age_years": 25,
    "owners": 25,
    "accident_disclosed": 15,
}

# --- anchored bands per dimension (§4) ---
KM_BANDS = [
    (20_000, 100),
    (40_000, 85),
    (70_000, 70),
    (100_000, 55),
    (150_000, 40),
    (float("inf"), 25),
]

AGE_BANDS = [
    (2, 100),
    (4, 85),
    (7, 65),
    (10, 45),
    (float("inf"), 25),
]

OWNERS_MAP = {1: 100, 2: 75, 3: 50}  # 4+ → 25 by lookup default

ACCIDENT_MAP = {
    "none": 100,
    "minor": 70,      # cosmetic
    "major": 30,      # structural
}

# --- imputation anchors (§4 null handling) ---
IMPUTATION = {
    "km_driven": 60,
    "age_years": 60,
    "owners": 60,
    "accident_disclosed": 60,
}

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
