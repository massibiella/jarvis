# Jarvis — Feature Checklist

Tracks the PRD (`../PRD.md`) feature by feature — checked off once a feature is actually usable, not just started. See `PLAN.md` for the current milestone's implementation details and in-progress work.

- [x] LLM-agnostic (works with any LLM given a config file) — provider adapter pattern; `GeminiAdapter` working end to end, `AnthropicAdapter` partial
- [x] Local weather — native tool (`tools/weather_tools.py`, Open-Meteo, no key). Originally an MCP server (`weather-mcp`), moved to native once Google Calendar became the real MCP use case — see `PLAN.md`. Verified live: `jarvis` answers real weather questions end to end.
- [ ] Google/Apple Calendar (view/create/delete/update/remind/reorganize) — MCP-based, needs Google OAuth
- [ ] Commute time (Google Maps / traffic) — MCP-based, needs Google OAuth
- [ ] Investment portal via IBKR
- [ ] Newsletter updates (investments + interest categories)
- [x] Memory files (persistent, cross-session) — `MemoryStore` fully implemented (read/write/append/load_index/search) and wired into `Agent`/`cli.py`. Agent has `remember`/`list_memory`/`read_memory`/`search_memory` tools and decides on its own when something's worth remembering, restricted to two categories (facts, preferences) — see `PLAN.md` for why. Verified live end-to-end.
- [ ] JARVIS-style frontend
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