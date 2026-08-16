"""The agent orchestrator: owns conversation history and the tool-call loop.

TODO (Step 6): implement `Agent.step()`. See docs/PLAN.md § "CLI chat loop":

1. Append the user's message to self.history.
2. Call `self.adapter.chat(messages=self.history, tools=self.tools.as_llm_tool_specs(),
   system=self.system_prompt)`.
3. If the response has tool_calls:
   - Append an assistant ChatMessage carrying `response.content` and `response.tool_calls`.
   - For each tool call, run it via `self.tools.execute(call.name, call.arguments)`,
     catching exceptions and turning them into an error string (don't crash —
     feed the error back to the model as the tool result so it can adapt).
   - Append a ChatMessage(role="tool", tool_call_id=call.id, content=result) per call.
   - Loop back to step 2.
4. Otherwise: append the assistant turn and return its text.
"""

from __future__ import annotations

from jarvis.llm.base import ChatMessage, LLMAdapter
from jarvis.memory.store import MemoryStore
from jarvis.tools.registry import ToolRegistry


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

    def step(self, user_text: str) -> str:
        raise NotImplementedError("TODO: Step 6 — see docs/PLAN.md")
