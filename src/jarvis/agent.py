"""The agent orchestrator: owns conversation history and the tool-call loop.

`step(user_text)`: append the user's message → call the adapter with the
current history + available tools → if the response has tool_calls, append
the assistant's request, execute each via `ToolRegistry.execute` (errors
become an error string fed back to the model, not a crash), append each
result, and loop back to calling the adapter again → once there are no more
tool_calls, append the assistant's text and return it.

Implemented and verified end-to-end (real Gemini API, real MCP tool call
via ToolRegistry/MCPToolClient) — see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
import logging

from jarvis.llm.base import ChatMessage, LLMAdapter
from jarvis.memory.store import MemoryStore
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self,
        adapter: LLMAdapter,
        tools: ToolRegistry,
        memory: MemoryStore,
        system_prompt: str,
    ) -> None:
        self.adapter = adapter
        self.tools = tools
        self.memory = memory
        self.history: list[ChatMessage] = []

        index = memory.load_index()
        self.system_prompt = f"{system_prompt}\n\n{index}" if index else system_prompt

    async def step(self, user_text: str) -> str:
        self.history.append(ChatMessage(role="user", content=user_text))

        while True:
            try:
                response = await asyncio.to_thread(
                    self.adapter.chat,
                    self.history,
                    self.tools.as_llm_tool_specs(),
                    system=self.system_prompt,
                )
            except Exception as e:
                self.history.pop()
                logger.error(
                    "An error was encountered while waiting for a response from the model: %s", e
                )
                return "Sorry, something went wrong talking to the model."

            if not response.tool_calls:
                self.history.append(ChatMessage(role="assistant", content=response.content))
                return response.content

            self.history.append(
                ChatMessage(
                    role="assistant", content=response.content, tool_calls=response.tool_calls
                )
            )

            for tool_call in response.tool_calls:
                try:
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                except Exception as e:
                    result = f"Error running tool {tool_call.name}: {e}"

                self.history.append(
                    ChatMessage(role="tool", tool_call_id=tool_call.id, content=result)
                ) 