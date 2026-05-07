from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
EVAL_DIR = ROOT / "eval"
RUNS_DIR = ROOT / "runs"
DOCS_DIR = ROOT / "docs"

MODEL_EXTRACTOR = "claude-sonnet-4-6"
EXTRACTOR_TEMPERATURE = 0.0
EXTRACTOR_MAX_TOKENS = 4096

# --- score_common weight tables (§4) ---
# Used when accident_disclosed is included in the locked common set:
WEIGHTS_WITH_ACCIDENT = {
    "km_driven": 30,
    "age_years": 20,
    "owners": 20,
    "certification_flag": 15,
    "accident_disclosed": 15,
}
# Used when accident_disclosed is NOT in the locked common set:
WEIGHTS_WITHOUT_ACCIDENT = {
    "km_driven": 35,
    "age_years": 25,
    "owners": 25,
    "certification_flag": 15,
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

CERT_MAP = {
    "top": 100,       # Imperial / Royal Blue / Spinny Assured Plus
    "mid": 75,
    "base": 60,
    "none": 40,
}

# --- imputation anchors (§4 null handling) ---
IMPUTATION = {
    "km_driven": 60,
    "age_years": 60,
    "owners": 60,
    "accident_disclosed": 60,
    "certification_flag": 40,
}

# --- disclosure-eligible field set (§4 Disclosure metric, locked) ---
DISCLOSURE_FIELDS = [
    "accident_history_detail",
    "service_history_records",
    "inspection_issue_list",
    "inspection_points_passed",
    "cosmetic_exterior_notes",
    "cosmetic_interior_notes",
    "tire_condition",
    "engine_remarks",
    "transmission_remarks",
    "battery_status",
    "ac_remarks",
    "electrical_remarks",
    "previous_use_type",
    "noc_status",
    "hypothecation_status",
    "insurance_status",
    "rc_type",
    "challan_status",
    "warranty_remaining_months",
    "inspection_photo_count",
]

PROMPT_VERSION = "v1.0"
