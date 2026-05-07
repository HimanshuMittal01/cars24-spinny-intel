from ci.config import (
    ACCIDENT_MAP,
    AGE_BANDS,
    IMPUTATION,
    KM_BANDS,
    OWNERS_MAP,
    WEIGHTS,
)
from ci.schemas import NormalizedListing, ScoreRecord


def _km_band(km: int) -> int:
    for ceil, val in KM_BANDS:
        if km <= ceil:
            return val
    return KM_BANDS[-1][1]


def _age_band(age: int) -> int:
    for ceil, val in AGE_BANDS:
        if age <= ceil:
            return val
    return AGE_BANDS[-1][1]


def _owners_band(owners: int) -> int:
    if owners >= 4:
        return 25
    return OWNERS_MAP.get(owners, 25)


def _accident_band(label: str) -> int:
    return ACCIDENT_MAP[label]


def _value_for_dim(name: str, n: NormalizedListing) -> tuple[float, bool]:
    """Return (value, was_imputed)."""
    v = getattr(n, name)
    if v is None:
        return float(IMPUTATION[name]), True
    if name == "km_driven":
        return float(_km_band(v)), False
    if name == "age_years":
        return float(_age_band(v)), False
    if name == "owners":
        return float(_owners_band(v)), False
    if name == "accident_disclosed":
        return float(_accident_band(v)), False
    raise KeyError(name)


def score_listing(n: NormalizedListing) -> ScoreRecord:
    per_dim: dict[str, float] = {}
    imputed: list[str] = []
    total = 0.0
    for dim, w in WEIGHTS.items():
        v, was_imp = _value_for_dim(dim, n)
        per_dim[dim] = v
        if was_imp:
            imputed.append(dim)
        total += (w / 100.0) * v
    return ScoreRecord(
        listing_id=n.listing_id,
        platform=n.platform,
        score_common=round(total, 2),
        per_dim=per_dim,
        imputed_dims=imputed,
        disclosure_count=sum(1 for v in n.disclosed_fields.values() if v),
        disclosed_fields=dict(n.disclosed_fields),
    )
