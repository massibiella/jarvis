"""IBKR's read-only tool allowlist.

The IBKR connector is authorized with a read-only OAuth scope (mcp.read
only — see tools/mcp_oauth.py), so write/trading tools already get
rejected server-side ("Insufficient scope: mcp.write required", confirmed
live). This allowlist is defense-in-depth on top of that, not a substitute
for it — it just keeps write-capable tools (create_order_instruction,
delete_watchlist, etc.) from ever being offered to the model in the first
place, rather than letting it attempt one and get an error back.

An explicit allowlist, not a denylist matching name prefixes like
"create_"/"delete_" — a denylist would silently let a new write tool
through if IBKR names it something we didn't anticipate. An allowlist
fails closed instead: a new tool just doesn't show up until someone
deliberately adds it here.
"""

from __future__ import annotations

READONLY_ALLOWLIST: set[str] = {
    "get_alert",
    "get_alerts",
    "search_contracts",
    "get_combo_identifier",
    "get_option_data",
    "get_option_parameters",
    "search_futures",
    "get_company_connections",
    "get_company_themes",
    "get_theme_details",
    "search_investment_topics",
    "get_price_history",
    "get_price_snapshot",
    "get_order_instructions",
    "get_account_orders",
    "get_pa_allocation",
    "get_pa_performance_all_periods",
    "get_account_balances",
    "get_account_positions",
    "get_account_summary",
    "get_account_trades",
    "get_watchlist",
    "get_watchlists",
    "whats_new",
}
