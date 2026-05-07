import pytest
from ci.score import score_listing, _km_band, _age_band, _owners_band, _accident_band
from ci.schemas import NormalizedListing


def _norm(**kw):
    base = dict(
        platform="cars24", listing_id="x", price=900_000,
        km_driven=45_000, age_years=4, owners=1,
        certification_flag=None, accident_disclosed="none",
        disclosed_fields={f: False for f in []},
        full_fields={},
    )
    base.update(kw)
    return NormalizedListing(**base)


def test_km_band_lookup():
    assert _km_band(15_000) == 100
    assert _km_band(45_000) == 70
    assert _km_band(160_000) == 25


def test_age_band_lookup():
    assert _age_band(1) == 100
    assert _age_band(5) == 65
    assert _age_band(11) == 25


def test_owners_band_lookup():
    assert _owners_band(1) == 100
    assert _owners_band(2) == 75
    assert _owners_band(4) == 25
    assert _owners_band(7) == 25


def test_accident_band_lookup():
    assert _accident_band("none") == 100
    assert _accident_band("minor") == 70
    assert _accident_band("major") == 30


def test_score_listing_excellent_all_top():
    n = _norm(km_driven=18_000, age_years=1, owners=1, accident_disclosed="none")
    s = score_listing(n)
    assert s.score_common == pytest.approx(100.0, abs=0.01)
    assert s.imputed_dims == []


def test_score_listing_average():
    n = _norm(km_driven=60_000, age_years=5, owners=2, accident_disclosed="minor")
    s = score_listing(n)
    expected = 0.35 * 70 + 0.25 * 65 + 0.25 * 75 + 0.15 * 70
    assert s.score_common == pytest.approx(expected, abs=0.01)


def test_score_listing_imputes_missing_km():
    n = _norm(km_driven=None, age_years=4, owners=1, accident_disclosed="none")
    s = score_listing(n)
    assert "km_driven" in s.imputed_dims
    expected = 0.35 * 60 + 0.25 * 85 + 0.25 * 100 + 0.15 * 100
    assert s.score_common == pytest.approx(expected, abs=0.01)


def test_score_listing_imputes_missing_accident():
    n = _norm(km_driven=45_000, age_years=4, owners=1, accident_disclosed=None)
    s = score_listing(n)
    assert "accident_disclosed" in s.imputed_dims
    expected = 0.35 * 70 + 0.25 * 85 + 0.25 * 100 + 0.15 * 60
    assert s.score_common == pytest.approx(expected, abs=0.01)


def test_score_listing_per_dim_keys():
    n = _norm()
    s = score_listing(n)
    assert set(s.per_dim.keys()) == {"km_driven", "age_years", "owners", "accident_disclosed"}
    # certification_flag is intentionally NOT in per_dim
    assert "certification_flag" not in s.per_dim


def test_score_listing_disclosure_count():
    disclosed = {f: False for f in []}
    disclosed.update({"accident_history_detail": True, "service_history_records": True, "insurance_type": True})
    n = _norm(disclosed_fields=disclosed)
    s = score_listing(n)
    assert s.disclosure_count == 3


def test_score_listing_does_not_modify_certification_flag():
    n = _norm(certification_flag="top")  # Spinny-style with diagnostic cert
    s = score_listing(n)
    # cert is not part of score_common; score should equal 4-dim formula
    expected = 0.35 * 70 + 0.25 * 85 + 0.25 * 100 + 0.15 * 100
    assert s.score_common == pytest.approx(expected, abs=0.01)
    assert "certification_flag" not in s.per_dim
