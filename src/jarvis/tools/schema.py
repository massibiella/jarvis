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

import inspect

from collections.abc import Callable
from typing import Any

_PYTHON_TO_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}

def build_schema_from_signature(func: Callable[..., Any]) -> dict[str, Any]:
    """Return a JSON schema `{"type": "object", "properties": {...}, "required": [...]}`
    describing `func`'s parameters, derived via `inspect.signature(func)`.
    """

    sig = inspect.signature(func)

    # Build dict that holds the input parameters of func
    # OrderedDict({'location': <Parameter "location: str">})
    params = sig.parameters

    # Collect all parameters before concatenating into final return dict
    properties = {}
    required = []
    for name, param in params.items():
        properties[name] =  {"type": _PYTHON_TO_JSON_TYPES[param.annotation]}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    # Assemble the properties object
    return {"type": "object", "properties": properties, "required": required}