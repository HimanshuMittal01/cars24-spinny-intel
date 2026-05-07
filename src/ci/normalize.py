"""Normalizer: maps platform-native RawListing fields to NormalizedListing.

Implements spec §13 mapping rules for Cars24 and Spinny.
"""

import re
from datetime import datetime, timezone
from typing import Any

from ci.config import DISCLOSURE_FIELDS
from ci.schemas import NormalizedListing, RawListing

# --- Spinny certification tier map (spec §13) ---
SPINNY_CERT_MAP: dict[str, str] = {
    "max": "top",
    "assured-plus": "top",
    "assured": "mid",
    "budget": "base",
}


def _parse_owners_spinny(value: Any) -> int | None:
    """Parse Spinny's ordinal owner string ("1st", "2nd", …) to int.

    - int/float → passthrough (coerced to int)
    - ordinal string like "1st", "2nd", "3rd", "4th+", "5th" → leading digit
    - None / unparseable → None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = re.match(r"^(\d+)", value.strip())
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Disclosure helpers
# ---------------------------------------------------------------------------

def _disclosure_cars24(fields: dict[str, Any]) -> dict[str, bool]:
    """Build disclosed_fields dict for a Cars24 listing."""
    d: dict[str, bool] = {f: False for f in DISCLOSURE_FIELDS}
    d["service_history_records"] = bool(fields.get("lastServicedAt"))
    d["insurance_type"] = bool(fields.get("insuranceType"))
    d["insurance_validity"] = bool(fields.get("insuranceExpiry"))
    # Cars24 advertises a 12-month platform-wide warranty for all listings
    d["warranty_remaining_months"] = True
    return d


def _disclosure_spinny(fields: dict[str, Any]) -> dict[str, bool]:
    """Build disclosed_fields dict for a Spinny listing."""
    d: dict[str, bool] = {f: False for f in DISCLOSURE_FIELDS}

    inspection = fields.get("inspection_report")
    inspection_v3 = fields.get("inspection_report_v3")
    pricing = fields.get("pricing") or {}

    d["accident_history_detail"] = bool(inspection)
    d["inspection_per_section_ratings"] = bool(inspection_v3)
    d["inspection_repair_statements"] = bool(inspection_v3)
    d["tyre_condition_per_wheel"] = bool(inspection_v3 or inspection)
    d["service_history_records"] = bool(fields.get("last_service_date"))
    d["warranty_remaining_months"] = bool(pricing.get("extended_warranty_pricing"))
    d["insurance_type"] = bool(fields.get("insurance_type"))
    d["insurance_validity"] = bool(
        fields.get("insurance_validity_month") or fields.get("insurance_validity_year")
    )
    d["per_listing_certification_tier"] = bool(fields.get("procurement_category"))
    d["buy_back_pricing"] = bool(fields.get("buy_back_pricing"))
    d["market_price_delta"] = bool(pricing.get("market_price"))
    d["inspection_photo_count"] = bool(
        fields.get("galleryV3") or fields.get("product_photos")
    )
    # noc_status, rc_type, previous_use_type, challan_status, hypothecation_status
    # remain False — not exposed pre-auth on Spinny

    return d


# ---------------------------------------------------------------------------
# Per-platform normalization
# ---------------------------------------------------------------------------

def _normalize_cars24(raw: RawListing, today_year: int) -> NormalizedListing:
    fields = raw.fields

    price = int(fields["listingPrice"])
    km_driven = fields.get("odometerReading")
    if km_driven is not None:
        km_driven = int(km_driven)

    year_raw = fields.get("year")
    age_years = (today_year - int(year_raw)) if year_raw is not None else None

    owners = fields.get("ownerNumber")
    if owners is not None:
        owners = int(owners)

    return NormalizedListing(
        platform=raw.platform,
        listing_id=raw.listing_id,
        price=price,
        km_driven=km_driven,
        age_years=age_years,
        owners=owners,
        # Cars24 has no per-listing certification tier (spec §13)
        certification_flag=None,
        # Cars24 platform-level no-accident promise mapped to per-listing (spec §13)
        accident_disclosed="none",
        disclosed_fields=_disclosure_cars24(fields),
        full_fields=fields,
    )


def _normalize_spinny(raw: RawListing, today_year: int) -> NormalizedListing:
    fields = raw.fields

    # Price: prefer productPrice, fall back to "price" string with commas
    if "productPrice" in fields and fields["productPrice"] is not None:
        price = int(fields["productPrice"])
    else:
        price = int(str(fields["price"]).replace(",", ""))

    # km_driven: prefer productMileage, fall back to "mileage" string with commas
    if "productMileage" in fields and fields["productMileage"] is not None:
        km_driven: int | None = int(fields["productMileage"])
    elif "mileage" in fields and fields["mileage"] is not None:
        km_driven = int(str(fields["mileage"]).replace(",", ""))
    else:
        km_driven = None

    # age_years: prefer make_year, fall back to registration_year
    make_year = fields.get("make_year")
    reg_year = fields.get("registration_year")
    if make_year is not None:
        age_years: int | None = today_year - int(make_year)
    elif reg_year is not None:
        age_years = today_year - int(reg_year)
    else:
        age_years = None

    owners = _parse_owners_spinny(fields.get("no_of_owners"))

    # certification_flag via SPINNY_CERT_MAP
    proc_cat = fields.get("procurement_category")
    cert_flag = SPINNY_CERT_MAP.get(proc_cat) if proc_cat else None  # type: ignore[arg-type]

    # accident_disclosed from inspection_report summary
    accident: str | None = None
    inspection = fields.get("inspection_report")
    if inspection:
        try:
            is_acc = inspection["report"]["summary"]["is_accidental"]
            accident = "none" if is_acc is False else "minor"
        except (KeyError, TypeError):
            accident = None

    return NormalizedListing(
        platform=raw.platform,
        listing_id=raw.listing_id,
        price=price,
        km_driven=km_driven,
        age_years=age_years,
        owners=owners,
        certification_flag=cert_flag,  # type: ignore[arg-type]
        accident_disclosed=accident,  # type: ignore[arg-type]
        disclosed_fields=_disclosure_spinny(fields),
        full_fields=fields,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(raw: RawListing, today_year: int | None = None) -> NormalizedListing:
    """Normalize a RawListing to a NormalizedListing.

    Dispatches on raw.platform. today_year defaults to the current UTC year.
    """
    if today_year is None:
        today_year = datetime.now(timezone.utc).year

    if raw.platform == "cars24":
        return _normalize_cars24(raw, today_year)
    if raw.platform == "spinny":
        return _normalize_spinny(raw, today_year)

    raise ValueError(f"normalize: unknown platform {raw.platform!r}")
