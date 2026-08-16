"""Anthropic implementation of LLMAdapter.

TODO (Step 3): implement `chat()`. See docs/PLAN.md
§ "LLM adapter (provider-agnostic)" for the exact translation needed:

- ToolSpec -> Anthropic's {"name", "description", "input_schema"}
- response.content blocks -> LLMResponse.content (text) + .tool_calls (tool_use)
  (block.input on a tool_use block is already parsed JSON — no manual parsing)
- response.stop_reason passes through as-is ("tool_use" / "end_turn" / "max_tokens" / ...)

Once this works, register it in llm/registry.py's ADAPTER_REGISTRY.
"""

from __future__ import annotations

import anthropic

from jarvis.config import LLMConfig
from jarvis.llm.base import ChatMessage, LLMAdapter, LLMResponse, ToolSpec


class AnthropicAdapter(LLMAdapter):
    def __init__(self, model: str, api_key: str, default_max_tokens: int = 4096) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.default_max_tokens = default_max_tokens

    @classmethod
    def from_config(cls, llm_config: LLMConfig) -> AnthropicAdapter:
        return cls(
            model=llm_config.model,
            api_key=llm_config.api_key,
            default_max_tokens=llm_config.max_tokens,
        )

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("TODO: Step 3 — see docs/PLAN.md")
