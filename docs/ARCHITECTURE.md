# Jarvis — Architecture (current state)

This is a snapshot of how Jarvis actually works *today* — present tense, no TODOs, no step numbers. For what's being built next and why, see [`PLAN.md`](PLAN.md); for the feature-level checklist against the PRD, see [`TODO.md`](TODO.md). Update this file when the *shape* of the system changes (a new module, a new data flow), not every time a stub gets filled in.

## What runs today

`jarvis` (installed via `pyproject.toml`'s `[project.scripts]`) is a working terminal chat agent: it loads config, registers native tools (weather, memory), launches every configured MCP server and registers its tools too, builds an `Agent`, and runs a chat loop through `Agent.step()` — so the model can actually call real tools and use the result to answer. Verified live end-to-end.

## Request flow, as it exists right now

```
jarvis (console script)
  → src/jarvis/cli.py: main() → asyncio.run(_main())
    → load_dotenv() + load_config()                [src/jarvis/config.py]
    → get_adapter_class(...) + adapter.from_config  [src/jarvis/llm/registry.py, adapters/gemini_adapter.py]
    → register_weather_tools(tools)                 [tools/weather_tools.py] — native, no subprocess
    → for each config.mcp_servers entry (e.g. Google Calendar):
        MCPToolClient(...).connect() + list_tools()  [src/jarvis/tools/mcp_client.py]
        → each discovered tool wrapped (_mcp_tool_to_tool) — swaps in a
          trimmed schema from mcp_overrides.get_override() when one
          exists for that (server_name, tool_name) [tools/mcp_overrides.py],
          otherwise passes the MCP server's schema through unchanged —
          and registered into a ToolRegistry             [src/jarvis/tools/registry.py]
    → MemoryStore(...) built + register_memory_tools(tools, memory)  [tools/memory_tools.py]
    → system prompt loaded (system_prompt.md, or config.agent.system_prompt_file if set)
    → Agent(adapter, tools, memory, system_prompt) built  [src/jarvis/agent.py]
      → Agent.__init__ appends memory.load_index() to the system prompt
    → loop:
        input("you> ") → await agent.step(user_input) → print result
    → on any exit path (clean /exit, EOF, or a crash): every MCPToolClient is closed
```

`Agent.step()` owns the full tool-call loop internally: send history + available tools to the adapter, execute any requested tool calls via `ToolRegistry`, feed results back in, repeat until the model answers in plain text.

## Package layout

```
jarvis/
├── pyproject.toml              # deps: anthropic, google-genai, pyyaml, python-dotenv, mcp, httpx2
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
│   │   ├── mcp_client.py                # MCPToolClient: talks to one MCP server over stdio
│   │   ├── mcp_overrides.py             # hand-written schema overrides for specific bloated MCP tools
│   │   ├── memory_tools.py              # remember/list_memory/read_memory/search_memory, wrapping MemoryStore
│   │   └── weather_tools.py             # get_current_weather — native, calls Open-Meteo directly
│   └── memory/store.py                  # MemoryStore: read/write/append/load_index/search
└── tests/test_config.py                 # only module with automated tests so far
```

## Components

**Config (`config.py`)** — YAML, resolved from an explicit path, `$JARVIS_CONFIG`, `./config.yaml`, or `~/.jarvis/config.yaml`, in that order. Holds `llm` (provider/model/api key env var), `memory` (root dir, user id), `agent` (system prompt override), `logging`, and `mcp_servers` (name → subprocess launch command, used by `MCPToolClient`). API keys are read lazily from the environment, never stored in the config object itself.

**LLM adapters (`llm/`)** — `LLMAdapter` is an ABC with one method, `chat(messages, tools, system, max_tokens) -> LLMResponse`; every provider implements it, translating to/from that provider's own wire format. `llm/registry.py` maps a config string (`"gemini"`) to the adapter class. `GeminiAdapter` is the only complete, working one — both plain-message chat and tool-calling (both directions: offering tools, parsing the model's function-call requests back out) are verified against the real API. `AnthropicAdapter` exists but its `chat()` is unfinished and it's deliberately left out of the registry.

**Tools (`tools/`)** — three pieces, wired together and into `Agent` via `cli.py`:
- `schema.py`'s `build_schema_from_signature()` turns a Python function's signature into a JSON Schema dict (`str`/`int`/`float`/`bool`, required-if-no-default).
- `registry.py`'s `ToolRegistry` holds a `dict[str, Tool]` (`Tool` = name/description/parameters/func). `register()` is a decorator for native Python functions (uses `schema.py`); `add_tool()` takes an already-fully-described `Tool` directly (what MCP wiring will use). `execute()` calls a tool's `func` and handles both sync and async callables uniformly (`inspect.isawaitable` check). `as_llm_tool_specs()` converts everything registered into the `ToolSpec` list `LLMAdapter.chat()` expects.
- `mcp_client.py`'s `MCPToolClient` wraps one MCP server subprocess (stdio transport): `connect()` (spawn + handshake, via `AsyncExitStack` so the connection survives past the method call), `list_tools()` (→ `list[ToolSpec]`), `call_tool()` (→ `str`), `close()`. Optionally passes extra environment variables to the subprocess (e.g. an OAuth credentials path) via `MCPServerConfig.env`. Verified end-to-end originally against `weather-mcp` (since moved off MCP, see below); the Google Calendar integration is the current real user of this path.
- `mcp_overrides.py`'s `get_override(server_name, tool_name)` returns a hand-written, trimmed JSON schema for a specific MCP tool if one's registered, else `None`. Used by `cli.py`'s `_mcp_tool_to_tool()` to replace only what the LLM sees as a tool's schema — the tool call itself still goes to the real MCP server, validated against its own full original schema. Exists because some MCP servers ship far larger schemas than needed (Google Calendar's `create-event`/`update-event`/`list-events` — see `PLAN.md`'s "Resolved: Google Calendar tool-schema cost").

**Agent (`agent.py`)** — owns `self.history: list[ChatMessage]` and runs the tool-calling loop: `step()` sends history + available tools to the adapter, executes any requested tool calls via `ToolRegistry`, feeds results back in, and repeats until the model answers in plain text. Implemented, wired into `cli.py`, and verified end-to-end against the real Gemini API with a real MCP tool call.

**System prompt (`system_prompt.md`)** — the built-in default, loaded by `cli.py`'s `_load_system_prompt()`; `config.agent.system_prompt_file`, if set, overrides it with a different file instead.

**Memory (`memory/store.py` + `tools/memory_tools.py`)** — markdown files with YAML frontmatter, one dir per `user_id`, under `config.memory.root_dir`. `MemoryStore`: `read`/`write`/`append` (all implemented and tested — `write` always emits the `---`/`---` structure so `read()` can always parse it back, and creates missing parent directories; `append` reads the existing entry or falls back to an empty one via `except FileNotFoundError`, preserving existing frontmatter unchanged); `load_index()` globs `memory_*.md` and pulls each file's `description` from its own frontmatter — no separate manually-maintained index file, so it can't drift out of sync; `search()` is plain substring matching, no embeddings.

Files aren't freely named by the model — writes go through `tools/memory_tools.py`'s `remember(category, text)` tool, restricted to a small fixed set of categories (`facts`, `preferences`), each with a description written once in code (`_CATEGORY_DESCRIPTIONS`), not invented per-call by the model. This was a deliberate choice (see `PLAN.md`'s "Memory" section) — an undescribed file is invisible to the model's own reasoning about what's worth reading, and free-form category creation makes that hard to guarantee. `list_memory`/`read_memory`/`search_memory` are the read-side counterparts, thin wrappers over the same store. `Agent.__init__` appends `memory.load_index()` to the system prompt at startup, so the model always knows what's been remembered without loading full contents by default.

**Weather (`tools/weather_tools.py`)** — `get_current_weather(location)`, a native tool calling Open-Meteo's geocoding + forecast APIs directly (`httpx2`). Originally built as a standalone MCP server ([weather-mcp](https://github.com/massibiella/weather-mcp), kept for reference/reuse elsewhere) and moved to a native tool once Google Calendar became the real, ongoing MCP integration — weather isn't reused outside Jarvis in practice, so there was no remaining reason to pay subprocess overhead for one simple HTTP call (see `PLAN.md`'s "Key decisions" for the full reasoning). Logic ported unchanged: same WMO weather-code mapping, same `httpx2.HTTPError`-specific error handling.

## Known gaps (today, not a roadmap — see PLAN.md for that)

- `AnthropicAdapter` is unfinished and unregistered — Gemini is the only usable provider today.
- No auto-summarization of a session into memory — the agent only remembers what it explicitly decided to save *during* a conversation via `remember`; nothing catches things it didn't flag in the moment, and nothing persists once `jarvis` exits unless `remember` was actually called (see `TODO.md`'s "Nice to have").
- `sessions/` (dated, per-session notes) from the original memory design sketch was never built — only the two fixed categories (`facts`, `preferences`) exist.
