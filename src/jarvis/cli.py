"""Entry point: `jarvis` on the command line.

Loads config, builds the LLM adapter, connects to every configured MCP
server and registers its tools into a ToolRegistry, builds a MemoryStore
and an Agent, then runs the chat loop through `agent.step()`. Every
MCPToolClient gets closed on any exit path (see the try/finally in
_main()) — clean /exit, EOF, or a crash. See docs/ARCHITECTURE.md for
the full request-flow diagram.

Not yet added: `--config` CLI flag, `/remember <text>` (needs
MemoryStore, Step 7 — see docs/PLAN.md).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from jarvis.agent import Agent
from jarvis.config import JarvisConfig, load_config
from jarvis.llm.base import ToolSpec
from jarvis.llm.registry import get_adapter_class
from jarvis.memory.store import MemoryStore
from jarvis.tools.maps_tools import register_maps_tools
from jarvis.tools.mcp_client import MCPToolClient
from jarvis.tools.mcp_overrides import get_override
from jarvis.tools.memory_tools import register_memory_tools
from jarvis.tools.registry import Tool, ToolRegistry
from jarvis.tools.weather_tools import register_weather_tools
from jarvis.tools.web_browsing_tools import register_web_browsing_tools

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"


def _load_system_prompt(config: JarvisConfig) -> str:
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


async def _run_turn(agent: Agent, user_text: str) -> str:
    """User text in, response text out — the seam a future non-terminal
    interface (an API, a mobile backend) would call instead of the CLI's
    input()/print() loop.
    """
    try:
        return await agent.step(user_text)
    except Exception as e:
        logger.error("Something went wrong: %s", e)
        return "Sorry, something went wrong."


async def _main() -> None:
    load_dotenv()
    config = load_config()
    logging.basicConfig(level=config.logging.level)
    # google-genai warns on every call that we're not using its Chat helper —
    # a style recommendation, not an actual problem for us. Silence it specifically
    # rather than raising our own app's logging level to hide it.
    logging.getLogger("google_genai").setLevel(logging.ERROR)

    adapter_cls = get_adapter_class(config.llm.provider)
    adapter = adapter_cls.from_config(config.llm)

    tools = ToolRegistry()
    register_weather_tools(tools)
    register_web_browsing_tools(tools)
    register_maps_tools(tools)
    clients = []

    try:
        # Get all the tools from each MCP server, and register them
        for server_name, mcp_server_config in config.mcp_servers.items():
            client = MCPToolClient(server_name, mcp_server_config.command, mcp_server_config.env)
            await client.connect()
            clients.append(client)

            tools_available = await client.list_tools()
            if tools_available:
                for tool in tools_available:
                    tools.add_tool(_mcp_tool_to_tool(server_name, client, tool))

        memory = MemoryStore(config.memory.root_dir, config.memory.user_id)
        register_memory_tools(tools, memory)

        system_prompt = _load_system_prompt(config)
        agent = Agent(adapter, tools, memory, system_prompt)

        while True:
            try:
                user_input = await asyncio.to_thread(input, "you> ")
            except EOFError:
                break
            if user_input == "/exit":
                break
            print(await _run_turn(agent, user_input))
    finally:
        # Runs on any exit path — a connect() failure partway through the loop
        # above, a clean `/exit`, EOF, or an unexpected crash — not just the
        # happy path, so a client never gets left dangling.
        for client in clients:
            await client.close()


def main() -> None:
    """Sync entry point for pyproject.toml's [project.scripts] — that entry
    point calls this function directly, with no awareness of asyncio, so it
    has to be the thing that actually starts the event loop."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
