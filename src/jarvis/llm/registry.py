"""Maps a config `provider` string to the adapter class that implements it.

Adding a new provider means writing one adapter module and adding one line
to ADAPTER_REGISTRY — nothing else in the app needs to change. See
docs/PLAN.md § "LLM adapter (provider-agnostic)".

Status: GeminiAdapter is implemented and registered (plain-message chat
verified against the real API; tool-calling not yet translated).
AnthropicAdapter still has an unfinished chat() (see TODOs in that file) —
left unregistered until it's complete, so `get_adapter_class("anthropic")`
fails loudly instead of silently returning something broken.
"""

from __future__ import annotations

from jarvis.llm.adapters.gemini_adapter import GeminiAdapter
from jarvis.llm.base import LLMAdapter

ADAPTER_REGISTRY: dict[str, type[LLMAdapter]] = {
    "gemini": GeminiAdapter,
    # "anthropic": AnthropicAdapter,  # finish chat() first — see adapters/anthropic_adapter.py
}


def get_adapter_class(provider: str) -> type[LLMAdapter]:
    try:
        return ADAPTER_REGISTRY[provider]
    except KeyError as e:
        known = ", ".join(sorted(ADAPTER_REGISTRY)) or "(none registered yet)"
        raise ValueError(f"Unknown LLM provider {provider!r}. Known: {known}") from e
