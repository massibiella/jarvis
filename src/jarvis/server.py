"""HTTP interface for the Jarvis agent — what `frontend/` talks to instead
of its old in-browser stub (see `frontend/src/lib/backend.ts`).

One shared `Agent` (and its conversation history) for the process's
lifetime, matching today's single-user scope — auth/multi-user isolation
(PRD §4.6) isn't built yet, so there's exactly one conversation, not one
per HTTP client. Requests are serialized through a lock since `Agent.step()`
mutates shared history and two concurrent calls would interleave it.

Run: `jarvis-server` (see pyproject.toml). Reuses `runtime.build_agent()`,
the same setup/teardown `cli.py` uses, so this and the terminal chat loop
never drift apart.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from jarvis.agent import Agent
from jarvis.config import load_config
from jarvis.runtime import build_agent

logger = logging.getLogger(__name__)

# Vite's default dev server origin (see frontend/.env.example's
# VITE_DEV_SERVER_URL). Override with a comma-separated list via
# JARVIS_CORS_ORIGINS if the HUD is served from somewhere else.
_DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    reply: str


def _cors_origins() -> list[str]:
    raw = os.environ.get("JARVIS_CORS_ORIGINS")
    return [origin.strip() for origin in raw.split(",")] if raw else _DEFAULT_ORIGINS


def create_app() -> FastAPI:
    load_dotenv()
    config = load_config()
    logging.basicConfig(level=config.logging.level)
    logging.getLogger("google_genai").setLevel(logging.ERROR)

    # Guards agent.step() — Agent.history isn't safe for concurrent callers.
    lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with build_agent(config) as agent:
            app.state.agent = agent
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        agent: Agent = app.state.agent
        async with lock:
            reply = await agent.step(req.text)
        return ChatResponse(reply=reply)

    return app


def main() -> None:
    """Sync entry point for pyproject.toml's [project.scripts]."""
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
