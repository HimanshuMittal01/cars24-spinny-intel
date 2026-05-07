from ci.llm import LLMClient
from ci.schemas import RawListing
from ci.snapshot import Snapshot

CARS24_SYSTEM = """You extract structured data from Cars24 used-car listing HTML.
Return ONLY values you can find in the page; for any field you cannot find, return null.
Do not infer, normalize, or invent. Numeric fields must be integers (no commas).
Year is the manufacturing year. Owners count is the integer number of prior owners.
Certification tier is the platform's named tier (e.g. "Imperial", "Royal Blue") or
null if no tier badge is visible. Accident disclosed is "none" / "minor" / "major" or null."""

CARS24_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "price": {"type": ["integer", "null"]},
        "km_driven": {"type": ["integer", "null"]},
        "year": {"type": ["integer", "null"]},
        "owners_count": {"type": ["integer", "null"]},
        "registration_state": {"type": ["string", "null"]},
        "fuel": {"type": ["string", "null"]},
        "transmission": {"type": ["string", "null"]},
        "body_color": {"type": ["string", "null"]},
        "certification_tier": {"type": ["string", "null"]},
        "accident_disclosed": {
            "type": ["string", "null"],
            "enum": ["none", "minor", "major", None],
        },
        "inspection_issue_list": {"type": ["array", "null"], "items": {"type": "string"}},
        "service_history_records": {"type": ["string", "null"]},
        "warranty_remaining_months": {"type": ["integer", "null"]},
        "noc_status": {"type": ["string", "null"]},
        "rc_type": {"type": ["string", "null"]},
        "insurance_status": {"type": ["string", "null"]},
        "previous_use_type": {"type": ["string", "null"]},
        "tire_condition": {"type": ["string", "null"]},
        "engine_remarks": {"type": ["string", "null"]},
        "transmission_remarks": {"type": ["string", "null"]},
        "battery_status": {"type": ["string", "null"]},
        "ac_remarks": {"type": ["string", "null"]},
        "electrical_remarks": {"type": ["string", "null"]},
        "cosmetic_exterior_notes": {"type": ["string", "null"]},
        "cosmetic_interior_notes": {"type": ["string", "null"]},
        "challan_status": {"type": ["string", "null"]},
        "hypothecation_status": {"type": ["string", "null"]},
        "inspection_photo_count": {"type": ["integer", "null"]},
        "inspection_points_passed": {"type": ["string", "null"]},
        "accident_history_detail": {"type": ["string", "null"]},
    },
    "required": ["price", "km_driven", "year"],
}


def extract_cars24(snapshot: Snapshot, client: LLMClient) -> RawListing:
    user = (
        "Extract the structured fields from this Cars24 listing HTML. "
        "If a field is not visible, return null. Do not invent values.\n\n"
        f"HTML:\n{snapshot.html}"
    )
    resp = client.extract_structured(
        system=CARS24_SYSTEM,
        user=user,
        tool_name="cars24_extract",
        tool_schema=CARS24_TOOL_SCHEMA,
    )
    return RawListing(
        platform="cars24",
        listing_id=snapshot.listing_id,
        url=f"snapshot://{snapshot.listing_id}",
        captured_at=snapshot.captured_at,
        fields=resp.parsed,
    )
