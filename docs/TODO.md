# Jarvis — Feature Checklist

Tracks the PRD (`../PRD.md`) feature by feature — checked off once a feature is actually usable, not just started. See `PLAN.md` for the current milestone's implementation details and in-progress work.

- [x] LLM-agnostic (works with any LLM given a config file) — provider adapter pattern; `GeminiAdapter` working end to end, `AnthropicAdapter` partial
- [x] Local weather — native tool (`tools/weather_tools.py`, Open-Meteo, no key). Originally an MCP server (`weather-mcp`), moved to native once Google Calendar became the real MCP use case — see `PLAN.md`. Verified live: `jarvis` answers real weather questions end to end.
- [x] Google Calendar (view/create/delete/update/remind/reorganize) — OAuth done, MCP server (`@cocal/google-calendar-mcp`) connected with 6 tools enabled, schemas trimmed for cost (`tools/mcp_overrides/calendar.py`, see `PLAN.md`). Verified live.
- [ ] Apple Calendar — not started
- [x] Commute time (Google Maps / traffic) — MCP-based, needs Google OAuth
- [x] Investment portal via IBKR — read-only, wired against IBKR's official hosted MCP connector (remote, OAuth 2.1; `tools/mcp_oauth.py`, `tools/mcp_overrides/ibkr.py`, see `PLAN.md`). Read-only enforced by both OAuth scope and a tool allowlist. Verified live against a real account, including silent token refresh after expiry.
- [ ] Newsletter updates (investments + interest categories)
- [x] Memory files (persistent, cross-session) — `MemoryStore` fully implemented (read/write/append/load_index/search) and wired into `Agent`/`cli.py`. Agent has `remember`/`list_memory`/`read_memory`/`search_memory` tools and decides on its own when something's worth remembering, restricted to two categories (facts, preferences) — see `PLAN.md` for why. Verified live end-to-end.
- [x] JARVIS-style frontend — connected to the real agent backend over HTTP (`src/jarvis/server.py`, `jarvis-server`), not the old in-browser stub. Verified live: text input round-trips through `Agent.step()` and renders the real reply.
- [ ] Multi-user auth — memory layout is already auth-ready (`users/<user_id>/`), auth itself not built
- [ ] Security — ongoing, no dedicated pass yet
- [ ] Daily morning check-in (weather, news, investments, appointments)
- [ ] Daily night check-in (what was done today, what's deferred)
- [ ] Own reminders (independent of the user's calendar)
- [x] Web browsing / research

## Nice to have
- [ ] Mobile connection (e.g. message the user via Telegram)
- [ ] GraphDB for facts and relationships. Other ideas?
- [ ] Auto-summarize a session into MemoryStore on exit (or periodically) — the agent can already decide *during* a conversation that something's worth remembering (via the `remember` tool), but nothing catches things it didn't explicitly flag in the moment. Different problem from the in-session compaction note in PLAN.md (that's about one long conversation not overflowing context; this is about remembering *across* separate runs of `jarvis`).
- [ ] `system_prompt.md` needs real guardrails on the `remember` tool — right now it has zero judgment about whether something's actually worth persisting beyond "durable vs one-off." Live-tested: joke/non-serious content fed to it got saved into `memory_facts.md` as if it were real. Needs explicit instruction not to remember things said in jest/testing, and/or a check before persisting.
- [x] Automated OAuth for remote MCP servers — done for the `url`-based (Streamable HTTP) path via `tools/mcp_oauth.py`: Jarvis opens a browser itself on first connect, no manual terminal step. Still open for stdio servers like Google Calendar, where authenticating means manually running `npx @cocal/google-calendar-mcp auth` — that's the community server's own internal OAuth flow, not something Jarvis's code controls the same way.