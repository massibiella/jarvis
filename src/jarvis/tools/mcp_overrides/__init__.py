"""Per-server MCP tool registration policy: schema overrides and read-only
allowlists, dispatched by server_name. Each server's own rules live in its
own module (calendar.py, ibkr.py) — this file only wires them together, so
adding a third server's overrides never means touching an unrelated one.

Keyed by (server_name, tool_name) rather than tool_name alone, so two
different MCP servers can't collide by coincidentally naming a tool the
same thing.
"""

from __future__ import annotations

from typing import Any

from jarvis.tools.mcp_overrides import calendar, ibkr

_SCHEMA_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "calendar": calendar.SCHEMA_OVERRIDES,
}

_READONLY_ALLOWLISTS: dict[str, set[str]] = {
    "ibkr": ibkr.READONLY_ALLOWLIST,
}


def get_override(server_name: str, tool_name: str) -> dict[str, Any] | None:
    return _SCHEMA_OVERRIDES.get(server_name, {}).get(tool_name)


def is_allowed(server_name: str, tool_name: str) -> bool:
    """False only for a tool explicitly excluded by a server's allowlist.
    Servers with no allowlist entry (e.g. Calendar) are unaffected."""
    allowlist = _READONLY_ALLOWLISTS.get(server_name)
    return allowlist is None or tool_name in allowlist
