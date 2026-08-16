# Jarvis

A personal assistant agent. See [`docs/PLAN.md`](docs/PLAN.md) for the current milestone's scope, architecture, and implementation order.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/config.example.yaml config.yaml
export ANTHROPIC_API_KEY=sk-...
```

## Development

```bash
pytest
ruff check .
ruff format --check .
```

## Status

Milestone 1 (core agent skeleton) in progress. Config loading is implemented; the LLM adapter, agent loop, tool registry, and memory store are stubbed with `TODO`s — see `docs/PLAN.md` for what's next.
