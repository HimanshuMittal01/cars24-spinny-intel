import pytest
from pydantic import ValidationError

from ci.schemas import (
    RawListing, NormalizedListing, ScoreRecord, RankRow, GoldRecord, TraceEvent,
)


def test_raw_listing_minimal_valid():
    raw = RawListing(
        platform="cars24",
        listing_id="abc123",
        url="https://cars24.com/listing/abc123",
        captured_at="2026-05-06T10:00:00Z",
        fields={"price": 950000, "km_driven": 45000, "year": 2020},
    )
    assert raw.platform == "cars24"
    assert raw.fields["price"] == 950000


def test_raw_listing_rejects_unknown_platform():
    with pytest.raises(ValidationError):
        RawListing(
            platform="olx",
            listing_id="x",
            url="https://x",
            captured_at="2026-05-06T10:00:00Z",
            fields={},
        )


def test_normalized_listing_requires_common_fields():
    n = NormalizedListing(
        platform="spinny",
        listing_id="x",
        price=1_100_000,
        km_driven=38_000,
        age_years=4,
        owners=1,
        certification_flag="top",
        accident_disclosed=None,
        disclosed_fields={"accident_history_detail": True, "service_history_records": False},
        full_fields={"accident_history_detail": "minor rear bumper scuff"},
    )
    assert n.disclosed_fields["accident_history_detail"] is True


def test_score_record_shape():
    s = ScoreRecord(
        listing_id="x",
        platform="cars24",
        score_common=78.5,
        per_dim={"km_driven": 85, "age_years": 65, "owners": 100, "certification_flag": 60},
        imputed_dims=[],
        disclosure_count=4,
        disclosed_fields={f: False for f in []},
    )
    assert s.score_common == 78.5


def test_rank_row_ratio():
    r = RankRow(
        listing_id="x",
        platform="cars24",
        price=900_000,
        score_common=75.0,
        ratio=12_000.0,
        disclosure_count=4,
        imputed_dims=[],
    )
    assert r.ratio == 12_000.0


def test_gold_record_shape():
    g = GoldRecord(
        listing_id="x",
        platform="spinny",
        full_fields={"price": 1_200_000, "km_driven": 30_000},
        score_common=82.0,
        notes={"km_driven": "30k, well below band threshold"},
    )
    assert g.score_common == 82.0


def test_trace_event_shape():
    t = TraceEvent(
        run_id="r1",
        node="extract.cars24",
        timestamp="2026-05-06T10:00:01Z",
        input_hash="abc",
        output_hash="def",
        latency_ms=1234,
        tokens_in=500,
        tokens_out=200,
        model="claude-sonnet-4-6",
        prompt_version="v1.0",
        cost_usd=0.0123,
    )
    assert t.node == "extract.cars24"
