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


class RankRow(BaseModel):
    listing_id: str
    platform: Platform
    price: int
    score_common: float
    ratio: float
    disclosure_count: int
    imputed_dims: list[str]


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
