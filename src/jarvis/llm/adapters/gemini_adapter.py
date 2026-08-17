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

Status: plain-message chat() is implemented and verified against the real
API (message/role translation, system prompt, max_tokens, stop_reason
mapping). Tool-calling translation is NOT implemented yet — see the TODO
on the `tools=` line in chat() below.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from jarvis.config import LLMConfig
from jarvis.llm.base import ChatMessage, LLMAdapter, LLMResponse, ToolSpec

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
            default_max_tokens=llm_config.max_tokens
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
                tools=tools # TODO: still our raw ToolSpec objects — needs translation to
                            # Gemini's tool format (types.Tool/FunctionDeclaration) before
                            # this works with a non-empty tools list
            )
        )

        # Translate gemini's reponse to something Jarvis understands
        gemini_reason = response.candidates[0].finish_reason.value
        stop_reason = _STOP_REASON_MAP.get(gemini_reason, gemini_reason)

        return LLMResponse(content=response.text, stop_reason=stop_reason, tool_calls=[])


    def _to_gemini_message(self, messages: list[ChatMessage]) -> list[types.Content]:
        gemini_messages = []
        for message in messages:
            # Gemini only supports 'model' and 'user' roles
            role = message.role if message.role != 'assistant' else 'model'
            
            gemini_messages.append(
                types.Content(role=role, parts=[types.Part.from_text(text=message.content)])
            )

        return gemini_messages