# Jarvis — Architecture (current state)

This is a snapshot of how Jarvis actually works *today* — present tense, no TODOs, no step numbers. For what's being built next and why, see [`PLAN.md`](PLAN.md); for the feature-level checklist against the PRD, see [`TODO.md`](TODO.md). Update this file when the *shape* of the system changes (a new module, a new data flow), not every time a stub gets filled in.

## What runs today

`jarvis` (installed via `pyproject.toml`'s `[project.scripts]`) is a working terminal chat agent: it loads config, launches every configured MCP server and registers its tools, builds an `Agent`, and runs a chat loop through `Agent.step()` — so the model can actually call real tools (e.g. `get_current_weather` via `weather-mcp`) and use the result to answer. Verified live end-to-end.

## Request flow, as it exists right now

```
jarvis (console script)
  → src/jarvis/cli.py: main() → asyncio.run(_main())
    → load_dotenv() + load_config()                [src/jarvis/config.py]
    → get_adapter_class(...) + adapter.from_config  [src/jarvis/llm/registry.py, adapters/gemini_adapter.py]
    → for each config.mcp_servers entry:
        MCPToolClient(...).connect() + list_tools()  [src/jarvis/tools/mcp_client.py]
        → each discovered tool wrapped (_mcp_tool_to_tool) and
          registered into a ToolRegistry                [src/jarvis/tools/registry.py]
    → MemoryStore(...) built (constructed only — nothing calls its methods yet)
    → system prompt loaded (system_prompt.md, or config.agent.system_prompt_file if set)
    → Agent(adapter, tools, memory, system_prompt) built  [src/jarvis/agent.py]
    → loop:
        input("you> ") → await agent.step(user_input) → print result
    → on any exit path (clean /exit, EOF, or a crash): every MCPToolClient is closed
```

`Agent.step()` owns the full tool-call loop internally: send history + available tools to the adapter, execute any requested tool calls via `ToolRegistry`, feed results back in, repeat until the model answers in plain text.

## Package layout

```
jarvis/
├── pyproject.toml              # deps: anthropic, google-genai, pyyaml, python-dotenv, mcp
├── config/config.example.yaml  # template; real config.yaml is gitignored, per-machine
├── src/jarvis/
│   ├── config.py                        # JarvisConfig dataclasses + load_config()
│   ├── cli.py                           # entry point — see "Request flow" above
│   ├── system_prompt.md                 # built-in default system prompt
│   ├── agent.py                         # Agent orchestrator — full tool-call loop, wired into cli.py
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

**Tools (`tools/`)** — three pieces, wired together and into `Agent` via `cli.py`:
- `schema.py`'s `build_schema_from_signature()` turns a Python function's signature into a JSON Schema dict (`str`/`int`/`float`/`bool`, required-if-no-default).
- `registry.py`'s `ToolRegistry` holds a `dict[str, Tool]` (`Tool` = name/description/parameters/func). `register()` is a decorator for native Python functions (uses `schema.py`); `add_tool()` takes an already-fully-described `Tool` directly (what MCP wiring will use). `execute()` calls a tool's `func` and handles both sync and async callables uniformly (`inspect.isawaitable` check). `as_llm_tool_specs()` converts everything registered into the `ToolSpec` list `LLMAdapter.chat()` expects.
- `mcp_client.py`'s `MCPToolClient` wraps one MCP server subprocess (stdio transport): `connect()` (spawn + handshake, via `AsyncExitStack` so the connection survives past the method call), `list_tools()` (→ `list[ToolSpec]`), `call_tool()` (→ `str`), `close()`. Verified end-to-end against the real [`weather-mcp`](https://github.com/massibiella/weather-mcp) server.

**Agent (`agent.py`)** — owns `self.history: list[ChatMessage]` and runs the tool-calling loop: `step()` sends history + available tools to the adapter, executes any requested tool calls via `ToolRegistry`, feeds results back in, and repeats until the model answers in plain text. Implemented, wired into `cli.py`, and verified end-to-end against the real Gemini API with a real MCP tool call.

**System prompt (`system_prompt.md`)** — the built-in default, loaded by `cli.py`'s `_load_system_prompt()`; `config.agent.system_prompt_file`, if set, overrides it with a different file instead.

**Memory (`memory/store.py`)** — designed (markdown + YAML frontmatter, one dir per `user_id`, an index loaded into the system prompt plus on-demand `read`/`search` tools) but not implemented — every method still raises. `cli.py` constructs a `MemoryStore` and hands it to `Agent`, but nothing calls any of its methods yet.

**weather-mcp** — not part of this repo. A separate, standalone MCP server ([github.com/massibiella/weather-mcp](https://github.com/massibiella/weather-mcp)) exposing one tool, `get_current_weather`, via the Open-Meteo API. Runs as its own subprocess, launched by `MCPToolClient` per the `mcp_servers.weather` entry in `config.yaml`.

## Known gaps (today, not a roadmap — see PLAN.md for that)

- `MemoryStore` is fully unimplemented — nothing persists across sessions yet, and there's no `/remember` command or recall tools.
- `ToolRegistry.register()` (the native-Python-tool decorator path) has no real tool using it yet — only `add_tool()` (the MCP path) is exercised by the running app.
- `AnthropicAdapter` is unfinished and unregistered — Gemini is the only usable provider today.
