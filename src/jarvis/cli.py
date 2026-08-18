"""Entry point: `jarvis` on the command line.

TODO (Step 4, extended in Step 7): implement `main()`. See docs/PLAN.md
§ "CLI chat loop":

1. Parse `--config` (argparse), call `load_config(args.config)`.
2. Resolve the adapter class from `ADAPTER_REGISTRY[config.llm.provider]`
   (jarvis.llm.registry) and build it via `.from_config(config.llm)`.
3. Build a ToolRegistry (register the recall tools once Step 7 exists)
   and a MemoryStore(config.memory.root_dir, config.memory.user_id).
4. Build an Agent(adapter, tools, memory, system_prompt=...).
5. Loop on input("you> "): support `/exit` (or Ctrl+D), `/remember <text>`
   (calls memory.append("facts.md", text)), and otherwise call
   `agent.step(user_input)` and print the result. Catch exceptions per
   turn so one bad turn doesn't kill the whole session.
"""

from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv

from jarvis.config import load_config
from jarvis.llm.base import ChatMessage
from jarvis.llm.registry import get_adapter_class

logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()
    config = load_config()
    logging.basicConfig(level=config.logging.level)
    # google-genai warns on every call that we're not using its Chat helper —
    # a style recommendation, not an actual problem for us. Silence it specifically
    # rather than raising our own app's logging level to hide it.
    logging.getLogger("google_genai").setLevel(logging.ERROR)
    adapter_cls = get_adapter_class(config.llm.provider)
    adapter = adapter_cls.from_config(config.llm)

    history: list[ChatMessage] = []

    while True:
        try:
            user_input = await asyncio.to_thread(input, "Say something: ")
        except EOFError:
            break
        if user_input == "/exit":
            break

        history.append(ChatMessage(role="user", content=user_input))
        try:
            response = await asyncio.to_thread(adapter.chat, history)
        except Exception as e:
            history.pop()   # needed since if the .chat() call fails, the loop would continue to append
                            # another 'user' message, which would cause issues.
            logger.error("Chat request failed: %s - try again later", e)
            continue
        print(response.content)
        history.append(ChatMessage(role="assistant", content=response.content))


if __name__ == "__main__":
    asyncio.run(main())