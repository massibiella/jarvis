"""MCP client: connects Jarvis to tool servers, e.g. Google Calendar.

One MCPToolClient per entry in config.mcp_servers; discovered tools get
registered into ToolRegistry as if they were native Python tools (see
docs/ARCHITECTURE.md § "Components"). Everything here is async on
purpose — connect() opens the connection once and it's meant to stay
alive inside the app's single event loop for the process's life; don't
reconnect per call (asyncio resources are loop-affine — see docs/PLAN.md
§ "Key decisions" for why `asyncio.run()` per call doesn't work here).
Verified end-to-end (originally against weather-mcp, since moved to a
native tool — see PLAN.md "Key decisions"). Wired into cli.py/Agent.
"""

import logging
from contextlib import AsyncExitStack

import httpx2
import mcp
from mcp.client.streamable_http import streamable_http_client

from jarvis.llm.base import ToolSpec
from jarvis.tools.mcp_oauth import build_oauth_provider

logger = logging.getLogger(__name__)

_USER_AGENT = "jarvis-mcp-client/0.1"


async def _ensure_user_agent(request: httpx2.Request) -> None:
    """mcp==2.0.0's OAuth discovery/registration requests are built as bare
    httpx2.Request objects sent via client.send(), which skips httpx2's
    default per-request headers entirely — including User-Agent. Some
    remote servers' edge/WAF (confirmed against IBKR's) reject requests
    with no User-Agent at all. This request hook backstops it regardless
    of how the request was built."""
    request.headers.setdefault("User-Agent", _USER_AGENT)


class MCPToolClient:
    def __init__(
        self,
        name: str,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
        url: str | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.env = env
        self.url = url
        self._session: mcp.ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        """Open an MCP ClientSession — spawn a subprocess (stdio) if `command`
        was given, otherwise connect to `url` over Streamable HTTP with OAuth."""

        if self.url:
            provider = build_oauth_provider(self.name, self.url)
            http_client = await self._exit_stack.enter_async_context(
                httpx2.AsyncClient(auth=provider, event_hooks={"request": [_ensure_user_agent]})
            )
            read, write = await self._exit_stack.enter_async_context(
                streamable_http_client(self.url, http_client=http_client)
            )
        else:
            params = mcp.StdioServerParameters(
                command=self.command[0],
                args=self.command[1:],
                env=self.env,
            )
            read, write = await self._exit_stack.enter_async_context(mcp.stdio_client(params))

        self._session = await self._exit_stack.enter_async_context(mcp.ClientSession(read, write))
        await self._session.initialize()

    async def list_tools(self) -> list[ToolSpec]:
        """Ask the server what tools it has; translate to our ToolSpec shape."""
        result = await self._session.list_tools()
        return [
            ToolSpec(name=tool.name, description=tool.description, parameters=tool.input_schema)
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

        return "\n".join(text_parts)

    async def close(self) -> None:
        await self._exit_stack.aclose()
