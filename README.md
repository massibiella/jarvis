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

## Development

```bash
pytest
ruff check .
ruff format --check .
```
