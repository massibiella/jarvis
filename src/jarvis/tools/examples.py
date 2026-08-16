"""One throwaway tool that proves the round trip works end to end:
model asks for a tool -> we run it -> model sees the result -> replies.

Only registered when config.agent.enable_example_tools is true (see
config/config.example.yaml). Safe to delete once real tools exist.

TODO (Step 6): write one tiny tool (e.g. `get_current_time() -> str`,
using stdlib `datetime`) and a `register_example_tools` function that
registers it on a given ToolRegistry via `registry.register()`.
"""

from __future__ import annotations

from jarvis.tools.registry import ToolRegistry


def register_example_tools(registry: ToolRegistry) -> None:
    raise NotImplementedError("TODO: Step 6 — see docs/PLAN.md")
