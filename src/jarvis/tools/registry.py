"""Tool registration: turns a Python function into something the LLM
adapter can offer to the model, and the agent can execute by name.

TODO (Step 5): implement `register`, `execute`, `as_llm_tool_specs`.
Designed so an MCP client can add MCP-server tools into the same registry
later without changing this interface — see docs/PLAN.md
§ "Tool registry (MCP-ready)".

`execute` is async (native tool functions are still plain sync/async
callables you can `await` either way) so MCP-backed tools can `await
client.call_tool(...)` without a nested event loop — see docs/PLAN.md
§ "MCP client" for why a sync `execute` doesn't work for those.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jarvis.llm.base import ToolSpec


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema
    func: Callable[..., str]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self, name: str | None = None, description: str | None = None
    ) -> Callable[[Callable[..., str]], Callable[..., str]]:
        """Decorator: derive a schema from the function signature (via
        tools/schema.py) and register it under `name` (defaults to the
        function's __name__) and `description` (defaults to its docstring).
        """
        raise NotImplementedError("TODO: Step 5 — see docs/PLAN.md")

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Look up the tool by name and call it with `arguments`.

        Let unknown-tool-name and call errors propagate — the agent loop
        (Step 6) is responsible for catching them and turning them into
        an error string fed back to the model, not this method.
        """
        raise NotImplementedError("TODO: Step 5 — see docs/PLAN.md")

    def as_llm_tool_specs(self) -> list[ToolSpec]:
        """Return every registered tool as a ToolSpec, for passing to
        LLMAdapter.chat(tools=...)."""
        raise NotImplementedError("TODO: Step 5 — see docs/PLAN.md")
