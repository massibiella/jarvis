"""Entry point: `jarvis` on the command line.

TODO (Step 4, extended in Step 7): implement `main()`. See docs/PLAN.md
§ "CLI chat loop":

1. Parse `--config` (argparse), call `load_config(args.config)`.
2. Resolve the adapter class from `ADAPTER_REGISTRY[config.llm.provider]`
   (jarvis.llm.registry) and build it via `.from_config(config.llm)`.
3. Build a ToolRegistry (register the example tool if
   `config.agent.enable_example_tools`; register the recall tools once
   Step 7 exists) and a MemoryStore(config.memory.root_dir, config.memory.user_id).
4. Build an Agent(adapter, tools, memory, system_prompt=...).
5. Loop on input("you> "): support `/exit` (or Ctrl+D), `/remember <text>`
   (calls memory.append("facts.md", text)), and otherwise call
   `agent.step(user_input)` and print the result. Catch exceptions per
   turn so one bad turn doesn't kill the whole session.
"""

from __future__ import annotations

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    raise NotImplementedError("TODO: Step 4 — see docs/PLAN.md")


if __name__ == "__main__":
    main()
