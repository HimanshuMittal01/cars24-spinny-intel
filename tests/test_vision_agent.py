# tests/test_vision_agent.py
"""Outer agent loop with mocked client + inspector."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ci.vision.agent import run_vision_agent


def _tool_use_block(tool_name: str, tool_input: dict, tool_use_id: str = "tu1"):
    b = MagicMock()
    b.type = "tool_use"
    b.name = tool_name
    b.input = tool_input
    b.id = tool_use_id
    return b


def _text_block(text: str):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _make_client(scripted_responses: list[list]):
    """Build a mock client that returns scripted content blocks per call."""
    client = MagicMock()
    responses = []
    for blocks in scripted_responses:
        r = MagicMock()
        r.content = blocks
        # stop_reason is "tool_use" if last block is tool_use, else "end_turn"
        r.stop_reason = "tool_use" if blocks and blocks[-1].type == "tool_use" else "end_turn"
        responses.append(r)
    client.messages = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


_FINAL_PAYLOAD = {
    "per_aspect": {
        a: {"severity": "not_visible", "confidence": "low",
            "photo_refs": [], "evidence_note": ""}
        for a in ("exterior_panels", "interior_cabin",
                  "dashboard_console", "tyres", "engine_bay")
    }
}


@pytest.fixture
def fake_manifest():
    return {
        "captured_at": "2026-05-07T00:00:00Z",
        "photos": [
            {"idx": 0, "sha256": "aaa", "source_url": "https://x/a.jpg", "hint": "Exterior"},
            {"idx": 1, "sha256": "bbb", "source_url": "https://x/b.jpg", "hint": "Interior"},
        ],
    }


async def test_agent_calls_list_then_final(fake_manifest):
    client = _make_client([
        [_tool_use_block("list_photos", {})],
        [_tool_use_block("final_assessment", _FINAL_PAYLOAD)],
    ])

    async def noop_inspect(idx):
        return {"aspects_visible": [], "findings": {}}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=noop_inspect,
    )
    assert len(assessment.findings) == 5
    assert assessment.agent_turns == 2
    assert assessment.budget_exceeded is False


async def test_agent_invokes_inspector_when_inspect_photo_called(fake_manifest):
    findings_for_idx_0 = {
        "aspects_visible": ["exterior_panels"],
        "findings": {"exterior_panels": {"severity": "light_wear", "evidence_note": "scuff"}},
    }
    client = _make_client([
        [_tool_use_block("inspect_photo", {"idx": 0})],
        [_tool_use_block("final_assessment", _FINAL_PAYLOAD)],
    ])

    inspector = AsyncMock(return_value=findings_for_idx_0)

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
    )
    inspector.assert_awaited_once_with(0)
    assert 0 in assessment.photos_inspected


async def test_agent_recovers_when_inspect_budget_hit(fake_manifest):
    """When max_inspects is hit on a tool call, agent receives an error tool_result
    and is expected to consolidate findings via final_assessment.
    """
    client = _make_client([
        [_tool_use_block("inspect_photo", {"idx": 0})],
        [_tool_use_block("inspect_photo", {"idx": 1})],
        [_tool_use_block("inspect_photo", {"idx": 0})],   # 3rd attempt: budget hit
        [_tool_use_block("final_assessment", _FINAL_PAYLOAD)],  # agent recovers
    ])

    async def inspector(idx):
        return {"aspects_visible": [], "findings": {}}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
        max_outer_turns=12, max_inspects=2,
    )
    assert assessment.budget_exceeded is False
    assert len(assessment.findings) == 5


async def test_agent_force_finalizes_on_outer_turn_budget(fake_manifest):
    # Agent never calls final_assessment; force-finalize after max_outer_turns
    blocks = [[_tool_use_block("list_photos", {})] for _ in range(20)]
    client = _make_client(blocks)

    async def inspector(idx):
        return {}

    assessment = await run_vision_agent(
        listing_id="L1", platform="cars24",
        manifest=fake_manifest, client=client, inspector_fn=inspector,
        max_outer_turns=3, max_inspects=10,
    )
    assert assessment.budget_exceeded is True
    assert assessment.agent_turns == 3
