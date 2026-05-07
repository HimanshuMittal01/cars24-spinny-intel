# src/ci/vision/agent.py
"""Outer vision agent: orchestrates tool-use turns until final_assessment.

Caps:
  - max_outer_turns (default 12): force-finalize after this many model turns
  - max_inspects (default 10): force-finalize after this many inspect_photo calls

On force-finalize, missing aspects default to severity="not_visible" and
budget_exceeded=True is set on the assessment.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from ci.schemas import VisionAssessment, VisionFinding
from ci.vision.tools import ALL_TOOLS

OUTER_MODEL = "claude-sonnet-4-6"
OUTER_PROMPT_VERSION = "v1"

OUTER_SYSTEM_PROMPT = """\
You are inspecting used-car listing photos to score visual condition across five aspects:
  exterior_panels, interior_cabin, dashboard_console, tyres, engine_bay.

You have these tools:
  - list_photos(): see what photos are available for this listing
  - inspect_photo(idx): get per-aspect findings for one photo
  - note_evidence_gap(aspect, reason): record an aspect you cannot evidence
  - final_assessment(per_aspect): submit your final per-aspect assessment (5 entries required)

Strategy:
  - Call list_photos() first to see what's available (use the hints to prioritize).
  - Inspect strategically — do not inspect every photo. Aim for ≤10 inspections.
  - When you have enough evidence (or have explicitly noted gaps for all uncovered aspects),
    call final_assessment with all 5 aspects.

Severity scale: pristine, light_wear, moderate, heavy, defect, not_visible.
Be conservative — if uncertain, mark not_visible rather than guess.
"""

_ASPECTS = ("exterior_panels", "interior_cabin",
            "dashboard_console", "tyres", "engine_bay")


def _default_assessment(
    listing_id: str, platform: str,
    manifest: dict, photos_inspected: list[int], turns: int,
    *, budget_exceeded: bool = False, partial_per_aspect: dict | None = None,
) -> VisionAssessment:
    """Build a VisionAssessment with not_visible defaults for any missing aspect."""
    per_aspect = partial_per_aspect or {}
    findings = []
    for a in _ASPECTS:
        if a in per_aspect:
            d = per_aspect[a]
            findings.append(VisionFinding(
                aspect=a,  # type: ignore[arg-type]
                severity=d.get("severity", "not_visible"),
                confidence=d.get("confidence", "low"),
                photo_refs=d.get("photo_refs", []),
                evidence_note=d.get("evidence_note", "")[:200],
            ))
        else:
            findings.append(VisionFinding(
                aspect=a,  # type: ignore[arg-type]
                severity="not_visible", confidence="low",
                photo_refs=[], evidence_note="",
            ))
    return VisionAssessment(
        listing_id=listing_id, platform=platform,  # type: ignore[arg-type]
        findings=findings,
        photos_inspected=photos_inspected,
        photo_count_total=len(manifest.get("photos", [])),
        agent_turns=turns,
        budget_exceeded=budget_exceeded,
    )


async def run_vision_agent(
    *,
    listing_id: str,
    platform: str,
    manifest: dict,
    client: Any,
    inspector_fn: Callable[[int], Awaitable[dict]],
    max_outer_turns: int = 12,
    max_inspects: int = 10,
) -> VisionAssessment:
    """Run the outer agent loop until final_assessment or budget exceeded."""
    photos_inspected: list[int] = []
    inspect_count = 0
    messages: list[dict] = [{
        "role": "user",
        "content": (
            f"Inspect the photos for listing {listing_id} on {platform}. "
            f"Use list_photos to begin, inspect_photo to gather evidence, "
            f"and final_assessment to submit your per-aspect ratings."
        ),
    }]
    turn = 0
    final_payload: dict | None = None

    while turn < max_outer_turns and final_payload is None:
        turn += 1
        resp = await client.messages.create(
            model=OUTER_MODEL,
            max_tokens=2048,
            system=OUTER_SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": resp.content})

        tool_results: list[dict] = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            tool_use_id = block.id
            inp = block.input

            if name == "list_photos":
                result = [{"idx": p["idx"], "sha256": p["sha256"], "hint": p.get("hint")}
                          for p in manifest.get("photos", [])]
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": str(result)}],
                })
            elif name == "inspect_photo":
                if inspect_count >= max_inspects:
                    # Budget hit — surface as error tool_result so the agent can still
                    # consolidate findings it already gathered into final_assessment.
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tool_use_id,
                        "content": [{"type": "text",
                                     "text": "ERROR: inspect_photo budget exceeded. "
                                             "Call final_assessment now with the findings "
                                             "you have already gathered. Use 'not_visible' "
                                             "only for aspects you genuinely could not evidence."}],
                        "is_error": True,
                    })
                else:
                    idx = int(inp["idx"])
                    inspect_count += 1
                    if idx not in photos_inspected:
                        photos_inspected.append(idx)
                    findings = await inspector_fn(idx)
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tool_use_id,
                        "content": [{"type": "text", "text": str(findings)}],
                    })
            elif name == "note_evidence_gap":
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": "ack"}],
                })
            elif name == "final_assessment":
                final_payload = inp
                break  # terminate outer loop after this turn
            else:
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": f"ERROR: unknown tool {name}"}],
                    "is_error": True,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    if final_payload is not None:
        return _default_assessment(
            listing_id=listing_id, platform=platform,
            manifest=manifest, photos_inspected=photos_inspected, turns=turn,
            partial_per_aspect=final_payload.get("per_aspect", {}),
        )

    # Force-finalize on budget exceeded
    return _default_assessment(
        listing_id=listing_id, platform=platform,
        manifest=manifest, photos_inspected=photos_inspected, turns=turn,
        budget_exceeded=True,
    )
