"""Entry point: `jarvis` on the command line.

TODO (Step 4, extended in Step 7): implement `main()`. See docs/PLAN.md
§ "CLI chat loop":

1. Parse `--config` (argparse), call `load_config(args.config)`.
2. Resolve the adapter class from `ADAPTER_REGISTRY[config.llm.provider]`
   (jarvis.llm.registry) and build it via `.from_config(config.llm)`.
3. Build a ToolRegistry (register the recall tools once Step 7 exists)
   and a MemoryStore(config.memory.root_dir, config.memory.user_id).
4. Build an Agent(adapter, tools, memory, system_prompt=...).
5. Loop on input("you> "): support `/exit` (or Ctrl+D), `/remember <text>`
   (calls memory.append("facts.md", text)), and otherwise call
   `agent.step(user_input)` and print the result. Catch exceptions per
   turn so one bad turn doesn't kill the whole session.
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
from jarvis.tools.mcp_client import MCPToolClient
from jarvis.tools.registry import Tool, ToolRegistry

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"


def _load_system_prompt(config: JarvisConfig) -> str:
    """config.agent.system_prompt_file, if set, overrides the built-in default."""
    path = config.agent.system_prompt_file or _DEFAULT_SYSTEM_PROMPT_PATH
    return path.read_text()


def _mcp_tool_to_tool(client: MCPToolClient, tool_spec: ToolSpec) -> Tool:
    async def call(**kwargs):
        return await client.call_tool(tool_spec.name, kwargs)

    return Tool(
        name=tool_spec.name,
        description=tool_spec.description,
        parameters=tool_spec.parameters,
        func=call,
    )

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
    clients = []

    try:
        # Get all the tools from each MCP server, and register them
        for server_name, mcp_server_config in config.mcp_servers.items():
            client = MCPToolClient(server_name, mcp_server_config.command)
            await client.connect()
            clients.append(client)

            tools_available = await client.list_tools()
            if tools_available:
                for tool in tools_available:
                    tools.add_tool(_mcp_tool_to_tool(client, tool))

        memory = MemoryStore(config.memory.root_dir, config.memory.user_id)
        system_prompt = _load_system_prompt(config)
        agent = Agent(adapter, tools, memory, system_prompt)

        while True:
            try:
                user_input = await asyncio.to_thread(input, "you> ")
            except EOFError:
                break
            if user_input == "/exit":
                break
            try:
                print(await agent.step(user_input))
            except Exception as e:
                logger.error("Something went wrong: %s", e)
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