"""The agent orchestrator: owns conversation history and the tool-call loop.

TODO (Step 6): implement `Agent.step()`. See docs/PLAN.md § "CLI chat loop":

1. Append the user's message to self.history.
2. Call `self.adapter.chat(...)` via `asyncio.to_thread` — the adapter's own
   `chat()` stays a plain sync method (it's just a blocking HTTP call), but
   `step()` is async so it doesn't block the event loop while waiting on it.
   `await asyncio.to_thread(self.adapter.chat, messages=self.history,
   tools=self.tools.as_llm_tool_specs(), system=self.system_prompt)`.
3. If the response has tool_calls:
   - Append an assistant ChatMessage carrying `response.content` and `response.tool_calls`.
   - For each tool call, run it via `await self.tools.execute(call.name, call.arguments)`
     (execute is async so MCP-backed tools can await their own network/subprocess calls),
     catching exceptions and turning them into an error string (don't crash —
     feed the error back to the model as the tool result so it can adapt).
   - Append a ChatMessage(role="tool", tool_call_id=call.id, content=result) per call.
   - Loop back to step 2.
4. Otherwise: append the assistant turn and return its text.
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
        self.system_prompt = system_prompt

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