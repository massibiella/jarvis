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
