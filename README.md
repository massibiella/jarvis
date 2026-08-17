# Jarvis

A personal assistant agent. See [`docs/PLAN.md`](docs/PLAN.md) for the current milestone's scope, architecture, and implementation order.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/config.example.yaml config.yaml
export GEMINI_API_KEY=...
```

Alternatively, put `GEMINI_API_KEY=...` in a `.env` file at the repo root — `jarvis` loads it automatically on startup. See .env.example.

### MCP servers (optional)

Tools that live in a separate MCP server (e.g. [weather-mcp](https://github.com/massibiella/weather-mcp)) must be cloned and set up on this machine too — Jarvis launches them as a local subprocess, it doesn't fetch them:

```bash
git clone https://github.com/massibiella/weather-mcp ../weather-mcp
cd ../weather-mcp && python3 -m venv .venv && source .venv/bin/activate && pip install "mcp[cli]"
```

Then point `config.yaml`'s `mcp_servers` section at that venv's Python — see `config/config.example.yaml` for the format.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

## Status

Milestone 1 (core agent skeleton) in progress. Config loading is implemented; the LLM adapter, agent loop, tool registry, and memory store are stubbed with `TODO`s — see `docs/PLAN.md` for what's next.
