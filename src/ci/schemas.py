from typing import Any, Literal
from pydantic import BaseModel, Field

Platform = Literal["cars24", "spinny"]


class RawListing(BaseModel):
    platform: Platform
    listing_id: str
    url: str
    captured_at: str
    fields: dict[str, Any]


class NormalizedListing(BaseModel):
    platform: Platform
    listing_id: str

    # common fields used in score_common
    price: int
    km_driven: int | None
    age_years: int | None
    owners: int | None
    certification_flag: Literal["top", "mid", "base", "none"] | None
    accident_disclosed: Literal["none", "minor", "major"] | None

    # disclosure measurement (§4)
    disclosed_fields: dict[str, bool]
    full_fields: dict[str, Any]


class ScoreRecord(BaseModel):
    listing_id: str
    platform: Platform
    score_common: float
    per_dim: dict[str, float]
    imputed_dims: list[str]
    disclosure_count: int
    disclosed_fields: dict[str, bool]
    # vision additions (optional, default None)
    visual_score: float | None = None
    composite_score: float | None = None


class RankRow(BaseModel):
    listing_id: str
    platform: Platform
    price: int
    rule_score: float                          # was score_common; renamed for clarity
    visual_score: float | None = None
    composite_score: float | None = None
    ratio: float
    disclosure_count: int
    imputed_dims: list[str]
    imputed_aspects: list[str] = Field(default_factory=list)


class GoldRecord(BaseModel):
    listing_id: str
    platform: Platform
    full_fields: dict[str, Any]
    score_common: float
    notes: dict[str, str] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    run_id: str
    node: str
    timestamp: str
    input_hash: str
    output_hash: str
    latency_ms: int
    # vision additions (optional, default None)
    event_id: str | None = None
    parent_event_id: str | None = None
    tool: str | None = None
    tool_params_preview: dict | None = None
    tool_result_preview: dict | None = None


# --- Vision agent additions (spec §6, §9) ---

Aspect = Literal[
    "exterior_panels",
    "interior_cabin",
    "dashboard_console",
    "tyres",
    "engine_bay",
]
Severity = Literal[
    "pristine", "light_wear", "moderate", "heavy", "defect", "not_visible",
]


class VisionFinding(BaseModel):
    aspect: Aspect
    severity: Severity
    confidence: Literal["low", "med", "high"]
    photo_refs: list[int]
    evidence_note: str = Field(max_length=200)


class VisionAssessment(BaseModel):
    listing_id: str
    platform: Platform
    findings: list[VisionFinding]
    photos_inspected: list[int]
    photo_count_total: int
    agent_turns: int
    budget_exceeded: bool = False
    notes: str | None = None


class VisionScore(BaseModel):
    listing_id: str
    platform: Platform
    visual_score: float
    per_aspect_score: dict[Aspect, float]
    imputed_aspects: list[Aspect]
    assessment: VisionAssessment
