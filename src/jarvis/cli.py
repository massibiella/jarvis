"""Entry point: `jarvis-cli` on the command line.

Loads config and runs a terminal chat loop through `agent.step()`, using
`runtime.build_agent()` for setup (adapter, tools, MCP clients, memory) and
teardown (every MCPToolClient closed on any exit path — clean `/exit`, EOF,
or a crash). See docs/ARCHITECTURE.md for the full request-flow diagram, and
`server.py` for the HTTP counterpart to this loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from dotenv import load_dotenv

from jarvis.agent import Agent
from jarvis.checkin import (
    determine_checkin,
    load_state,
    mark_ran,
    run_checkin,
    save_state,
    state_path,
)
from jarvis.config import load_config
from jarvis.runtime import build_agent

logger = logging.getLogger(__name__)


async def _run_turn(agent: Agent, user_text: str) -> str:
    """User text in, response text out — the same seam server.py's /chat
    endpoint calls into.
    """
    try:
        return await agent.step(user_text)
    except Exception as e:
        logger.error("Something went wrong: %s", e)
        return "Sorry, something went wrong."


async def _main() -> None:
    load_dotenv()
    config = load_config()
    logging.basicConfig(level=config.logging.level)
    # google-genai warns on every call that we're not using its Chat helper —
    # a style recommendation, not an actual problem for us. Silence it specifically
    # rather than raising our own app's logging level to hide it.
    logging.getLogger("google_genai").setLevel(logging.ERROR)

    async with build_agent(config) as agent:
        if config.checkin.enabled:
            path = state_path(config.memory.root_dir)
            state = load_state(path)
            kind = determine_checkin(datetime.now(), config.checkin, state)
            if kind is not None:
                try:
                    print(await run_checkin(agent, kind, config.checkin))
                except Exception as e:
                    logger.error("Check-in (%s) failed: %s", kind, e)
                else:
                    mark_ran(state, kind)
                    save_state(path, state)

        while True:
            try:
                user_input = await asyncio.to_thread(input, "you> ")
            except EOFError:
                break
            if user_input == "/exit":
                break
            print(await _run_turn(agent, user_input))


def main() -> None:
    """Sync entry point for pyproject.toml's [project.scripts] — that entry
    point calls this function directly, with no awareness of asyncio, so it
    has to be the thing that actually starts the event loop."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
