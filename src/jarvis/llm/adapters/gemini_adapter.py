"""Google Gemini implementation of LLMAdapter.

NOTE — data privacy, revisit before Jarvis handles real personal data:
Google's *free* tier for the Gemini API allows prompts/responses to be
used to improve their products (including human review) — unlike their
paid tier, which comes with a no-training-on-your-data guarantee. Fine
for learning and development now, but once real features land (calendar,
IBKR, anything touching personal or financial data — see ../../../PRD.md),
revisit whether the free tier is still appropriate here, or switch to a
paid tier / a different provider with a stronger data guarantee.

This is exactly what the LLMAdapter abstraction (see ../base.py) is for:
that swap should cost one new/updated adapter file and a config change,
not a rewrite of the rest of the app.

Status: fully implemented and verified against the real API, including
tool-calling in both directions (offering tools, and parsing the model's
function-call requests back out) — see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from jarvis.config import LLMConfig
from jarvis.llm.base import ChatMessage, LLMAdapter, LLMResponse, ToolCallRequest, ToolSpec

# Maps Gemini's finish_reason values to our own neutral stop_reason vocabulary
# (see base.py). Only the two reachable without tool support are mapped —
# extend this once tool calls or safety-refusal handling are added.
_STOP_REASON_MAP = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
}


class GeminiAdapter(LLMAdapter):
    def __init__(self, model: str, api_key: str, default_max_tokens: int = 4096) -> None:
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.default_max_tokens = default_max_tokens

    @classmethod
    def from_config(cls, llm_config: LLMConfig) -> GeminiAdapter:
        return cls(
            model=llm_config.model,
            api_key=llm_config.api_key,
            default_max_tokens=llm_config.max_tokens,
        )

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:

        # Build message list according to Gemini's spec
        gemini_messages = self._to_gemini_message(messages)

        response = self._client.models.generate_content(
            model=self.model,
            contents=gemini_messages,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens or self.default_max_tokens,
                tools=self._to_gemini_tools(tools),
            ),
        )

        # Translate gemini's reponse to something Jarvis understands
        gemini_reason = response.candidates[0].finish_reason.value
        stop_reason = _STOP_REASON_MAP.get(gemini_reason, gemini_reason)

        tool_calls = []
        parts = response.candidates[0].content.parts if response.candidates[0].content else []
        for part in parts:
            if part.function_call is not None:
                tool_calls.append(
                    ToolCallRequest(
                        id=part.function_call.id or part.function_call.name,
                        name=part.function_call.name,
                        arguments=part.function_call.args or {},
                        raw=part,  # includes thought_signature — must be resent verbatim
                    )
                )

        return LLMResponse(content=response.text, stop_reason=stop_reason, tool_calls=tool_calls)

    def _to_gemini_tools(self, tools: list[ToolSpec] | None) -> list[types.Tool] | None:
        if not tools:
            return None
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters_json_schema=tool.parameters,
                    )
                    for tool in tools
                ]
            )
        ]

    def _to_gemini_message(self, messages: list[ChatMessage]) -> list[types.Content]:
        gemini_messages = []
        for i, message in enumerate(messages):
            if message.role == "tool":
                # Gemini has no 'tool' role — a function's result goes back as a
                # 'user' turn carrying a function_response part, tagged by the
                # tool's *name* (not an id — ChatMessage only stores
                # tool_call_id, so look up the matching name from the
                # assistant's earlier tool_calls request).
                name = self._find_tool_call_name(messages, i, message.tool_call_id)
                gemini_messages.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=name, response={"result": message.content}
                            )
                        ],
                    )
                )
                continue

            # Gemini only supports 'model' and 'user' roles
            role = message.role if message.role != "assistant" else "model"

            if message.tool_calls:
                # Reuse the original Part when we have one (round-trips Gemini's
                # opaque thought_signature verbatim, required for replay) — only
                # rebuild from scratch for tool_calls that didn't come from Gemini.
                parts = [
                    call.raw
                    if call.raw is not None
                    else types.Part.from_function_call(name=call.name, args=call.arguments)
                    for call in message.tool_calls
                ]
            else:
                parts = [types.Part.from_text(text=message.content)]

            gemini_messages.append(types.Content(role=role, parts=parts))

        return gemini_messages

    def _find_tool_call_name(
        self, messages: list[ChatMessage], before_index: int, tool_call_id: str | None
    ) -> str:
        for message in reversed(messages[:before_index]):
            if message.tool_calls:
                for call in message.tool_calls:
                    if call.id == tool_call_id:
                        return call.name
        return "unknown_tool"
