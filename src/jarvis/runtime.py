"""Shared agent construction: build an adapter, native + MCP tools, memory,
and a wired-up `Agent`, with guaranteed MCP client cleanup on the way out.

Both the terminal CLI (`cli.py`) and the HTTP server (`server.py`) need the
exact same setup/teardown — this is the one place it's implemented, so
neither reimplements or drifts from the other. See docs/ARCHITECTURE.md's
"Request flow" for the full sequence this encodes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from jarvis.agent import Agent
from jarvis.config import JarvisConfig
from jarvis.llm.base import ToolSpec
from jarvis.llm.registry import get_adapter_class
from jarvis.memory.store import MemoryStore
from jarvis.tools.mcp_client import MCPToolClient
from jarvis.tools.mcp_overrides import get_override, is_allowed
from jarvis.tools.memory_tools import register_memory_tools
from jarvis.tools.registry import Tool, ToolRegistry
from jarvis.tools.weather_tools import register_weather_tools
from jarvis.tools.web_browsing_tools import register_web_browsing_tools

_DEFAULT_SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"


def load_system_prompt(config: JarvisConfig) -> str:
    """config.agent.system_prompt_file, if set, overrides the built-in default."""
    path = config.agent.system_prompt_file or _DEFAULT_SYSTEM_PROMPT_PATH
    return path.read_text()


def _mcp_tool_to_tool(server_name: str, client: MCPToolClient, tool_spec: ToolSpec) -> Tool:
    async def call(**kwargs):
        return await client.call_tool(tool_spec.name, kwargs)

    parameters = get_override(server_name, tool_spec.name) or tool_spec.parameters

    return Tool(
        name=tool_spec.name,
        description=tool_spec.description,
        parameters=parameters,
        func=call,
    )


@asynccontextmanager
async def build_agent(config: JarvisConfig) -> AsyncIterator[Agent]:
    """Build a fully-wired Agent and close every MCPToolClient on exit —
    whether the caller's `async with` block ends cleanly or raises.
    """
    adapter_cls = get_adapter_class(config.llm.provider)
    adapter = adapter_cls.from_config(config.llm)

    tools = ToolRegistry()
    register_weather_tools(tools)
    register_web_browsing_tools(tools)
    clients: list[MCPToolClient] = []

    try:
        for server_name, mcp_server_config in config.mcp_servers.items():
            client = MCPToolClient(
                server_name,
                command=mcp_server_config.command,
                env=mcp_server_config.env,
                url=mcp_server_config.url,
            )
            await client.connect()
            clients.append(client)

            tools_available = await client.list_tools()
            if tools_available:
                for tool in tools_available:
                    if is_allowed(server_name, tool.name):
                        tools.add_tool(_mcp_tool_to_tool(server_name, client, tool))

        memory = MemoryStore(config.memory.root_dir, config.memory.user_id)
        register_memory_tools(tools, memory)

        system_prompt = load_system_prompt(config)
        yield Agent(adapter, tools, memory, system_prompt)
    finally:
        # Runs whether setup completed, a connect() failed partway through,
        # or the caller's block raised — no client is ever left dangling.
        for client in clients:
            await client.close()
