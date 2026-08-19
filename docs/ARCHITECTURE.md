# Jarvis — Architecture (current state)

This is a snapshot of how Jarvis actually works *today* — present tense, no TODOs, no step numbers. For what's being built next and why, see [`PLAN.md`](PLAN.md); for the feature-level checklist against the PRD, see [`TODO.md`](TODO.md). Update this file when the *shape* of the system changes (a new module, a new data flow), not every time a stub gets filled in.

## What runs today

`jarvis` (installed via `pyproject.toml`'s `[project.scripts]`) is a terminal chat loop: it loads config, builds one LLM adapter (Gemini), and repeatedly sends whatever you type straight to that adapter, printing the reply. Tool-calling infrastructure (`ToolRegistry`, `MCPToolClient`) is fully built and independently tested, but **not yet wired into the running chat loop** — see "Known gaps" below.

## Request flow, as it exists right now

```
jarvis (console script)
  → src/jarvis/cli.py: main() → asyncio.run(_main())
    → load_dotenv() + load_config()               [src/jarvis/config.py]
    → get_adapter_class(config.llm.provider)       [src/jarvis/llm/registry.py]
    → adapter = GeminiAdapter.from_config(...)     [src/jarvis/llm/adapters/gemini_adapter.py]
    → loop:
        input() → append to a local `history` list
        → await asyncio.to_thread(adapter.chat, history)
        → print(response.content)
```

Notable: this loop calls `adapter.chat()` **directly** — it does not go through `Agent`, `ToolRegistry`, or `MemoryStore`. Those three exist and (except `Agent`) are fully implemented, but nothing in `cli.py` constructs or uses them yet.

## Package layout

```
jarvis/
├── pyproject.toml              # deps: anthropic, google-genai, pyyaml, python-dotenv, mcp
├── config/config.example.yaml  # template; real config.yaml is gitignored, per-machine
├── src/jarvis/
│   ├── config.py                        # JarvisConfig dataclasses + load_config()
│   ├── cli.py                           # entry point — see "Request flow" above
│   ├── agent.py                         # Agent orchestrator — in progress, not wired into cli.py
│   ├── llm/
│   │   ├── base.py                      # ChatMessage/ToolSpec/LLMResponse/LLMAdapter — the
│   │   │                                #   provider-neutral shape everything else imports
│   │   ├── registry.py                  # provider name -> adapter class
│   │   ├── adapters/gemini_adapter.py   # GeminiAdapter — active provider
│   │   └── adapters/anthropic_adapter.py  # unfinished, unregistered, deferred (needs paid billing)
│   ├── tools/
│   │   ├── schema.py                    # build_schema_from_signature(): inspect.signature -> JSON schema
│   │   ├── registry.py                  # ToolRegistry: register/add_tool/execute/as_llm_tool_specs
│   │   └── mcp_client.py                # MCPToolClient: talks to one MCP server over stdio
│   └── memory/store.py                  # MemoryStore — stub, not implemented
└── tests/test_config.py                 # only module with automated tests so far
```

## Components

**Config (`config.py`)** — YAML, resolved from an explicit path, `$JARVIS_CONFIG`, `./config.yaml`, or `~/.jarvis/config.yaml`, in that order. Holds `llm` (provider/model/api key env var), `memory` (root dir, user id), `agent` (system prompt override), `logging`, and `mcp_servers` (name → subprocess launch command, used by `MCPToolClient`). API keys are read lazily from the environment, never stored in the config object itself.

**LLM adapters (`llm/`)** — `LLMAdapter` is an ABC with one method, `chat(messages, tools, system, max_tokens) -> LLMResponse`; every provider implements it, translating to/from that provider's own wire format. `llm/registry.py` maps a config string (`"gemini"`) to the adapter class. `GeminiAdapter` is the only complete, working one — both plain-message chat and tool-calling (both directions: offering tools, parsing the model's function-call requests back out) are verified against the real API. `AnthropicAdapter` exists but its `chat()` is unfinished and it's deliberately left out of the registry.

**Tools (`tools/`)** — three independent pieces, each tested in isolation, not yet connected to each other or to `Agent`:
- `schema.py`'s `build_schema_from_signature()` turns a Python function's signature into a JSON Schema dict (`str`/`int`/`float`/`bool`, required-if-no-default).
- `registry.py`'s `ToolRegistry` holds a `dict[str, Tool]` (`Tool` = name/description/parameters/func). `register()` is a decorator for native Python functions (uses `schema.py`); `add_tool()` takes an already-fully-described `Tool` directly (what MCP wiring will use). `execute()` calls a tool's `func` and handles both sync and async callables uniformly (`inspect.isawaitable` check). `as_llm_tool_specs()` converts everything registered into the `ToolSpec` list `LLMAdapter.chat()` expects.
- `mcp_client.py`'s `MCPToolClient` wraps one MCP server subprocess (stdio transport): `connect()` (spawn + handshake, via `AsyncExitStack` so the connection survives past the method call), `list_tools()` (→ `list[ToolSpec]`), `call_tool()` (→ `str`), `close()`. Verified end-to-end against the real [`weather-mcp`](https://github.com/massibiella/weather-mcp) server.

**Agent (`agent.py`)** — owns `self.history: list[ChatMessage]` and runs the tool-calling loop: `step()` sends history + available tools to the adapter, executes any requested tool calls via `ToolRegistry`, feeds results back in, and repeats until the model answers in plain text. Implemented and verified end-to-end against the real Gemini API, including a real tool call. Not yet wired into `cli.py` — that's the remaining gap (see above).

**Memory (`memory/store.py`)** — designed (markdown + YAML frontmatter, one dir per `user_id`, an index loaded into the system prompt plus on-demand `read`/`search` tools) but not implemented — every method still raises.

**weather-mcp** — not part of this repo. A separate, standalone MCP server ([github.com/massibiella/weather-mcp](https://github.com/massibiella/weather-mcp)) exposing one tool, `get_current_weather`, via the Open-Meteo API. Runs as its own subprocess, launched by `MCPToolClient` per the `mcp_servers.weather` entry in `config.yaml`.

## Known gaps (today, not a roadmap — see PLAN.md for that)

- `cli.py` bypasses `Agent`/`ToolRegistry`/`MemoryStore` entirely — talks to the adapter directly.
- `MemoryStore` is fully unimplemented.
- Nothing yet builds an `MCPToolClient` from `config.mcp_servers` at runtime — it's only been exercised manually/in throwaway test scripts.

`Agent.step()` and `GeminiAdapter`'s tool-calling translation (both directions — offering tools, and parsing the model's function-call requests back out, including Gemini's `thought_signature` round-trip requirement) are both done and verified end-to-end against the real API.
