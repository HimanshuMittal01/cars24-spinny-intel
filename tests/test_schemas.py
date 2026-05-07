import pytest
from pydantic import ValidationError

from ci.schemas import (
    RawListing, NormalizedListing, ScoreRecord, RankRow, GoldRecord, TraceEvent,
)
from ci.schemas import (
    Aspect,
    Severity,
    VisionFinding,
    VisionAssessment,
    VisionScore,
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
        rule_score=75.0,
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
    )
    assert t.node == "extract.cars24"


def test_vision_finding_validates_aspect_and_severity():
    f = VisionFinding(
        aspect="exterior_panels",
        severity="light_wear",
        confidence="med",
        photo_refs=[0, 3],
        evidence_note="minor scuff on rear bumper",
    )
    assert f.aspect == "exterior_panels"
    assert f.severity == "light_wear"


def test_vision_finding_rejects_unknown_aspect():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VisionFinding(
            aspect="undercarriage",  # not in taxonomy
            severity="light_wear",
            confidence="med",
            photo_refs=[],
            evidence_note="x",
        )


def test_vision_finding_caps_evidence_note_at_200_chars():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VisionFinding(
            aspect="tyres",
            severity="moderate",
            confidence="low",
            photo_refs=[],
            evidence_note="x" * 201,
        )


def test_vision_assessment_holds_findings_and_metadata():
    findings = [
        VisionFinding(aspect=a, severity="not_visible", confidence="low",
                      photo_refs=[], evidence_note="")
        for a in ("exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay")
    ]
    a = VisionAssessment(
        listing_id="X1", platform="cars24",
        findings=findings, photos_inspected=[0, 1],
        photo_count_total=10, agent_turns=4,
        budget_exceeded=False, notes=None,
    )
    assert len(a.findings) == 5
    assert a.photo_count_total == 10


def test_vision_score_holds_aggregated_per_aspect_scores():
    s = VisionScore(
        listing_id="X1", platform="spinny",
        visual_score=72.5,
        per_aspect_score={"exterior_panels": 80.0, "interior_cabin": 70.0,
                          "dashboard_console": 75.0, "tyres": 70.0, "engine_bay": 67.5},
        imputed_aspects=[],
        assessment=VisionAssessment(
            listing_id="X1", platform="spinny",
            findings=[
                VisionFinding(aspect=a, severity="moderate", confidence="med",
                              photo_refs=[0], evidence_note="x")
                for a in ("exterior_panels", "interior_cabin", "dashboard_console", "tyres", "engine_bay")
            ],
            photos_inspected=[0], photo_count_total=5, agent_turns=3,
        ),
    )
    assert s.visual_score == 72.5
    assert "tyres" in s.per_aspect_score


def test_score_record_accepts_optional_visual_and_composite():
    from ci.schemas import ScoreRecord
    sr = ScoreRecord(
        listing_id="X1", platform="cars24",
        score_common=42.0,
        per_dim={"km_driven": 50.0, "age_years": 50.0,
                 "owners": 50.0, "accident_disclosed": 50.0},
        imputed_dims=[], disclosure_count=4, disclosed_fields={"a": True},
        visual_score=80.0, composite_score=53.4,
    )
    assert sr.visual_score == 80.0
    assert sr.composite_score == 53.4


def test_rank_row_carries_rule_visual_composite():
    from ci.schemas import RankRow
    r = RankRow(
        listing_id="X1", platform="cars24",
        price=500000, rule_score=42.0, visual_score=80.0,
        composite_score=53.4, ratio=9363.3,
        disclosure_count=4, imputed_dims=[], imputed_aspects=["engine_bay"],
    )
    assert r.composite_score == 53.4
    assert r.imputed_aspects == ["engine_bay"]


def test_trace_event_accepts_optional_agent_fields():
    from ci.schemas import TraceEvent
    e = TraceEvent(
        run_id="r1", node="vision.inspect_photo.cars24", timestamp="2026-05-07T12:00:00Z",
        input_hash="abc", output_hash="def", latency_ms=120,
        event_id="ev1", parent_event_id="ev0",
        tool="inspect_photo", tool_params_preview={"idx": 3},
        tool_result_preview={"aspects_visible": ["tyres"]},
    )
    assert e.tool == "inspect_photo"
    assert e.parent_event_id == "ev0"
