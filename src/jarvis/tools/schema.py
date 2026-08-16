"""Derives a JSON schema for a tool's parameters from its function signature.

TODO (Step 5): implement `build_schema_from_signature`. Support at least
str / int / float / bool / Optional[...] / list[...] annotations; a
parameter with no default is `required`. Raise a clear error (don't
guess) for any annotation type you don't handle — better to fail loudly
when someone writes a tool with an unsupported type than to silently
send the model a wrong schema. See docs/PLAN.md § "Tool registry
(MCP-ready)".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_schema_from_signature(func: Callable[..., Any]) -> dict[str, Any]:
    """Return a JSON schema `{"type": "object", "properties": {...}, "required": [...]}`
    describing `func`'s parameters, derived via `inspect.signature(func)`.
    """
    raise NotImplementedError("TODO: Step 5 — see docs/PLAN.md")
