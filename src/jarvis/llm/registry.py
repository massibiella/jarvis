"""Maps a config `provider` string to the adapter class that implements it.

TODO (Step 3): register AnthropicAdapter here once it exists. Adding a new
provider later means writing one adapter module and adding one line to
ADAPTER_REGISTRY — nothing else in the app needs to change. See
docs/PLAN.md § "LLM adapter (provider-agnostic)".
"""

from __future__ import annotations

from jarvis.llm.base import LLMAdapter

ADAPTER_REGISTRY: dict[str, type[LLMAdapter]] = {
    # "anthropic": AnthropicAdapter,  # from jarvis.llm.adapters.anthropic_adapter
}


def get_adapter_class(provider: str) -> type[LLMAdapter]:
    try:
        return ADAPTER_REGISTRY[provider]
    except KeyError as e:
        known = ", ".join(sorted(ADAPTER_REGISTRY)) or "(none registered yet)"
        raise ValueError(f"Unknown LLM provider {provider!r}. Known: {known}") from e
