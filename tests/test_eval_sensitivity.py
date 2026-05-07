from ci.eval.sensitivity import weight_sensitivity
from ci.schemas import NormalizedListing


def _n(lid, plat, price, km, age, owners, acc):
    return NormalizedListing(
        platform=plat, listing_id=lid, price=price,
        km_driven=km, age_years=age, owners=owners,
        certification_flag=None, accident_disclosed=acc,
        disclosed_fields={}, full_fields={},
    )


def test_sensitivity_returns_taus_for_each_dim():
    listings = [
        _n("a", "cars24", 1_200_000, 45_000, 4, 1, "none"),
        _n("b", "spinny", 900_000, 60_000, 5, 2, "minor"),
        _n("c", "cars24", 1_000_000, 30_000, 2, 1, "none"),
    ]
    res = weight_sensitivity(listings, perturbation=0.25)

    # 4 dims × 2 directions (+/−) = 8 perturbation entries
    assert set(res.tau_perturbed.keys()) == {
        "km_driven+", "km_driven-", "age_years+", "age_years-",
        "owners+", "owners-", "accident_disclosed+", "accident_disclosed-",
    }
    for tau in res.tau_perturbed.values():
        assert -1.0 <= tau <= 1.0

    # 4 leave-one-out entries
    assert set(res.tau_leave_one_out.keys()) == {
        "km_driven", "age_years", "owners", "accident_disclosed",
    }
    for tau in res.tau_leave_one_out.values():
        assert -1.0 <= tau <= 1.0


def test_sensitivity_unperturbed_is_identity():
    """When the perturbation is 0, the perturbed ranking should be identical to base, so tau == 1.0."""
    listings = [
        _n("a", "cars24", 1_200_000, 45_000, 4, 1, "none"),
        _n("b", "spinny", 900_000, 60_000, 5, 2, "minor"),
        _n("c", "cars24", 1_000_000, 30_000, 2, 1, "none"),
    ]
    res = weight_sensitivity(listings, perturbation=0.0)
    for tau in res.tau_perturbed.values():
        assert tau == 1.0
