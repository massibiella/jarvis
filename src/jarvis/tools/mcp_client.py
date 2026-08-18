"""MCP client: connects Jarvis to tool servers like weather-mcp.

TODO (Step 5b, after ToolRegistry): implement `connect`, `list_tools`,
`call_tool`, `close`. One MCPToolClient per entry in config.mcp_servers;
discovered tools get registered into ToolRegistry as if they were native
Python tools. See docs/PLAN.md § "MCP client (tools/mcp_client.py)" for
the full design. Everything here is already async on purpose — connect()
opens the connection once and it stays alive inside the app's single
event loop (see cli.py's asyncio.run(main())); don't reconnect per call.
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