from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from anthropic import Anthropic

from ci.config import (
    EXTRACTOR_MAX_TOKENS,
    EXTRACTOR_TEMPERATURE,
    MODEL_EXTRACTOR,
)


@dataclass
class LLMResponse:
    parsed: dict[str, Any]
    tokens_in: int
    tokens_out: int
    model: str


class LLMClient(Protocol):
    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse: ...


class AnthropicLLMClient:
    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_EXTRACTOR):
        self.client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=EXTRACTOR_MAX_TOKENS,
            temperature=EXTRACTOR_TEMPERATURE,
            system=system,
            tools=[{
                "name": tool_name,
                "description": "Return the structured extraction.",
                "input_schema": tool_schema,
            }],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )
        # Find the tool_use block.
        tool_block = next(b for b in msg.content if b.type == "tool_use")
        return LLMResponse(
            parsed=tool_block.input,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            model=self.model,
        )


@dataclass
class FakeLLMClient:
    canned_tool_input: dict[str, Any]
    canned_tokens_in: int = 100
    canned_tokens_out: int = 50
    model: str = "fake"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def extract_structured(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> LLMResponse:
        self.calls.append({
            "system": system, "user": user,
            "tool_name": tool_name, "tool_schema": tool_schema,
        })
        return LLMResponse(
            parsed=self.canned_tool_input,
            tokens_in=self.canned_tokens_in,
            tokens_out=self.canned_tokens_out,
            model=self.model,
        )
