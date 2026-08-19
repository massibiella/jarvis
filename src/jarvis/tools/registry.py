"""Tool registration: turns a Python function into something the LLM
adapter can offer to the model, and the agent can execute by name.

Designed so an MCP client can add MCP-server tools into the same registry
without changing this interface — MCPToolClient does exactly this via
add_tool(). See docs/ARCHITECTURE.md § "Components" for the full picture.

`execute` is async (native tool functions are still plain sync/async
callables you can `await` either way, see the isawaitable check below)
so MCP-backed tools can `await client.call_tool(...)` directly, inside
the app's single event loop, instead of needing a nested `asyncio.run()`
per call — see docs/PLAN.md § "Key decisions" for why that breaks.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jarvis.llm.base import ToolSpec
from jarvis.tools.schema import build_schema_from_signature


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

        For native Python tools only. MCP-discovered tools already come with
        a name/description/schema (from MCPToolClient.list_tools()) and no
        local function to introspect — use add_tool() for those instead.
        """
        def wrapper(func):
            resolved_name = name if name is not None else func.__name__
            resolved_description = description if description is not None else func.__doc__
            params = build_schema_from_signature(func)
            self.add_tool(
                Tool(
                    name=resolved_name,
                    description=resolved_description,
                    parameters=params,
                    func=func,
                )
            )
            return func

        return wrapper

    def add_tool(self, tool: Tool) -> None:
        """Register an already-fully-described Tool directly, bypassing
        schema derivation. This is what MCP wiring in cli.py uses: build a
        Tool per entry in MCPToolClient.list_tools(), with `func` set to a
        wrapper that awaits `client.call_tool(tool.name, kwargs)`.
        """
        self._tools[tool.name] = tool

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Look up the tool by name and call it with `arguments`.

        Let unknown-tool-name and call errors propagate — the agent loop
        (Step 6) is responsible for catching them and turning them into
        an error string fed back to the model, not this method.
        """
        tool = self._tools[name]

        result = tool.func(**arguments)
        if inspect.isawaitable(result):
            result = await result

        return f"{result}" 


    def as_llm_tool_specs(self) -> list[ToolSpec]:
        """Return every registered tool as a ToolSpec, for passing to
        LLMAdapter.chat(tools=...)."""
        return [
            ToolSpec(tool.name, tool.description, tool.parameters) for tool in self._tools.values()
        ]