# Jarvis

A personal assistant agent. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it's built today, and [`docs/PLAN.md`](docs/PLAN.md) for the current milestone's scope and implementation order.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/config.example.yaml config.yaml
cp .env.example .env   # then fill in your real API keys — .env is gitignored
```

`jarvis` loads `.env` automatically on startup; alternatively `export GEMINI_API_KEY=...` in your shell works too.

### MCP servers (optional)

Weather is a built-in native tool, no setup needed. For tools that live in a separate MCP server (e.g. Google Calendar via [`nspady/google-calendar-mcp`](https://github.com/nspady/google-calendar-mcp), run via `npx`) — Jarvis launches them as a local subprocess, it doesn't fetch them, so the server itself must be runnable on this machine first (a local clone for a Python server, or Node/npm installed for an npm-distributed one like the calendar server).

Then add it to `config.yaml`'s `mcp_servers` section — see `config/config.example.yaml` for the format, and `docs/PLAN.md`'s "MCP integrations" section for the calendar server's specific Google Cloud Console setup steps.

For the calendar server specifically, you also need to authenticate once before first use — run `npx @cocal/google-calendar-mcp auth`, it opens a browser link to sign in and grant access, and caches the resulting token locally. `jarvis` itself won't prompt for this; if calendar tools fail with an auth error, this is the step to (re-)run.

Some MCP servers are remote instead of local — configured with `url` instead of `command` (e.g. IBKR's official hosted connector). No local process needed for these; `jarvis` itself opens a browser for you to authorize on first connect, and caches the resulting token under `~/.jarvis/mcp_oauth/`. Nothing to run manually first, unlike the calendar server above.

## Development

```bash
pytest
ruff check .
ruff format --check .
```
