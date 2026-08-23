"""Derives a JSON schema for a tool's parameters from its function signature.

Supports str/int/float/bool annotations; a parameter with no default is
`required`. Optional[...]/list[...] annotations aren't handled yet — an
unsupported annotation raises KeyError (fails loudly rather than sending
the model a wrong schema), but that error isn't a purpose-built message
yet. See docs/ARCHITECTURE.md for how this fits into the rest of `tools/`.
"""

from __future__ import annotations

import inspect
import typing
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
    params = sig.parameters

    # get_type_hints resolves annotations back into real type objects even
    # when the defining module has `from __future__ import annotations`
    # (which makes param.annotation a plain string like 'str', not the type
    # str, breaking a plain _PYTHON_TO_JSON_TYPES[param.annotation] lookup).
    type_hints = typing.get_type_hints(func)

    properties = {}
    required = []
    for name, param in params.items():
        properties[name] = {"type": _PYTHON_TO_JSON_TYPES[type_hints[name]]}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    # Assemble the properties object
    return {"type": "object", "properties": properties, "required": required}
