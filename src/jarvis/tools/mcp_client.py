"""MCP client: connects Jarvis to tool servers like weather-mcp.

One MCPToolClient per entry in config.mcp_servers; discovered tools get
registered into ToolRegistry as if they were native Python tools (see
docs/ARCHITECTURE.md § "Components"). Everything here is async on
purpose — connect() opens the connection once and it's meant to stay
alive inside the app's single event loop for the process's life; don't
reconnect per call (asyncio resources are loop-affine — see docs/PLAN.md
§ "Key decisions" for why `asyncio.run()` per call doesn't work here).
Verified end-to-end against the real weather-mcp server. Not yet wired
into cli.py/Agent — that's still open, see docs/PLAN.md.
"""
import logging
from contextlib import AsyncExitStack

import mcp

from jarvis.llm.base import ToolSpec

logger = logging.getLogger(__name__)

class MCPToolClient:
    def __init__(self, name: str, command: list[str]) -> None:
        self.name = name
        self.command = command
        self._session: mcp.ClientSession | None = None
        self._exit_stack = AsyncExitStack()
        
    async def connect(self) -> None:
        """Launch the subprocess and open an MCP ClientSession over it."""

        params = mcp.StdioServerParameters(
            command=self.command[0],
            args=self.command[1:],
        )

        read, write = await self._exit_stack.enter_async_context(mcp.stdio_client(params))
        self._session = await self._exit_stack.enter_async_context(mcp.ClientSession(read, write))
        await self._session.initialize()
        
    async def list_tools(self) -> list[ToolSpec]:
        """Ask the server what tools it has; translate to our ToolSpec shape."""
        result = await self._session.list_tools()
        return [
            ToolSpec(name=tool.name, 
                     description=tool.description,
                     parameters=tool.input_schema)
           for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Invoke a tool on this server, return its result as a string."""
        result = await self._session.call_tool(name=name, arguments=arguments)
        if result.is_error:
            err_msg = f"Tool call {name} returned an error. Try again"
            logger.error(err_msg)
            return err_msg

        text_parts = []
        for block in result.content:
            if isinstance(block, mcp.types.TextContent):
                text_parts.append(block.text)

        return '\n'.join(text_parts)

    async def close(self) -> None:
        await self._exit_stack.aclose()