"""Provider-agnostic types for talking to an LLM.

TODO (Step 3): everything above this file (Agent, CLI) only ever imports
these types, never anything Anthropic-specific — that's what makes
swapping or adding a provider later a one-file change instead of a
rewrite. See docs/PLAN.md § "LLM adapter (provider-agnostic)".

The dataclasses below are already the agreed shape — you shouldn't need
to change them to implement AnthropicAdapter in llm/anthropic_adapter.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from jarvis.config import LLMConfig

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCallRequest:
    """A single tool call the model is asking us to run."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """One turn in the conversation, in our own provider-neutral shape."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCallRequest] | None = None
    tool_call_id: str | None = None  # set when role == "tool"


@dataclass
class ToolSpec:
    """A tool definition, in the shape the LLM adapter needs to see it."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class LLMResponse:
    """What comes back from one call to the model."""

    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    stop_reason: str = "end_turn"
    raw: Any = None


class LLMAdapter(ABC):
    """Base class every provider adapter implements."""

    @classmethod
    @abstractmethod
    def from_config(cls, llm_config: LLMConfig) -> LLMAdapter:
        """Build an adapter instance from the parsed `llm` config section."""
        raise NotImplementedError

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send the conversation so far to the model and get one response.

        Implementations translate `messages`/`tools` into the provider's
        wire format, make the call, and translate the response back into
        an LLMResponse. Must not mutate `messages`.
        """
        raise NotImplementedError
