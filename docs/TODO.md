# Jarvis — Feature Checklist

Tracks the PRD (`../PRD.md`) feature by feature — checked off once a feature is actually usable, not just started. See `PLAN.md` for the current milestone's implementation details and in-progress work.

- [x] LLM-agnostic (works with any LLM given a config file) — provider adapter pattern; `GeminiAdapter` working end to end, `AnthropicAdapter` partial
- [x] Local weather — MCP server (`weather-mcp`, Open-Meteo, no key), wired into `Agent`/`cli.py` via `ToolRegistry`/`MCPToolClient`. Verified live: `jarvis` answers real weather questions end to end.
- [ ] Google/Apple Calendar (view/create/delete/update/remind/reorganize) — MCP-based, needs Google OAuth
- [ ] Commute time (Google Maps / traffic) — MCP-based, needs Google OAuth
- [ ] Investment portal via IBKR
- [ ] Newsletter updates (investments + interest categories)
- [ ] Memory files (persistent, cross-session) — designed (index + on-demand recall), not implemented yet
- [ ] JARVIS-style frontend
- [ ] Multi-user auth — memory layout is already auth-ready (`users/<user_id>/`), auth itself not built
- [ ] Security — ongoing, no dedicated pass yet
- [ ] Daily morning check-in (weather, news, investments, appointments)
- [ ] Daily night check-in (what was done today, what's deferred)
- [ ] Own reminders (independent of the user's calendar)
- [ ] Web browsing / research

## Nice to have
- [ ] Mobile connection (e.g. message the user via Telegram)
- [ ] GraphDB for facts and relationships. Other ideas?