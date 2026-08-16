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
        raise NotImplementedError("API Paid plan required. We'll levae this for later.")
    
        # Build message list according to Anthropic's specs
        anthropic_messages = self._to_anthropic_message(messages)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.default_max_tokens,
            system=system,
            messages=anthropic_messages
        )

        # Extract response blocks
        print(response.to_json)

        # Format response in LLMResponse format, and return



    def _to_anthropic_message(self, messages: list[ChatMessage]) -> list[dict]:
        anthropic_messages = []
        for message in messages:
            # for now: just role + content, straight across
            # (msg.tool_calls / msg.tool_call_id come later, once tools are in play)
            anthropic_messages.append(
                {"role": message.role, "content": message.content}
            )
        return anthropic_messages
