# Jarvis — Architecture (current state)

This is a snapshot of how Jarvis actually works *today* — present tense, no TODOs, no step numbers. For what's being built next and why, see [`PLAN.md`](PLAN.md); for the feature-level checklist against the PRD, see [`TODO.md`](TODO.md). Update this file when the *shape* of the system changes (a new module, a new data flow), not every time a stub gets filled in.

## What runs today

Two interfaces share one agent core (`runtime.build_agent()`): `jarvis`, a terminal chat agent, and `jarvis-server`, an HTTP server the frontend HUD (`frontend/`) talks to. Both load config, register native tools (weather, web browsing, maps, memory), launch every configured MCP server and register its tools too, build an `Agent`, and run `Agent.step()` per turn — so the model can actually call real tools and use the result to answer. Verified live end-to-end, both interfaces.

## Request flow, as it exists right now

```
runtime.build_agent(config)                        [src/jarvis/runtime.py] — shared by both interfaces below
  → get_adapter_class(...) + adapter.from_config    [src/jarvis/llm/registry.py, adapters/gemini_adapter.py]
  → register_weather_tools(tools)                   [tools/weather_tools.py] — native, no subprocess
  → register_web_browsing_tools(tools)               [tools/web_browsing_tools.py] — native
  → register_maps_tools(tools)                       [tools/maps_tools.py] — native, TomTom (travel time/traffic)
  → for each config.mcp_servers entry (Google Calendar, IBKR):
      MCPToolClient(...).connect() + list_tools()    [src/jarvis/tools/mcp_client.py]
      → tools not on a server's allowlist skipped (mcp_overrides.is_allowed) —
        e.g. IBKR's write-capable tools never get registered at all
      → each remaining tool wrapped (_mcp_tool_to_tool) — swaps in a
        trimmed schema from mcp_overrides.get_override() when one
        exists for that (server_name, tool_name) [tools/mcp_overrides/],
        otherwise passes the MCP server's schema through unchanged —
        and registered into a ToolRegistry             [src/jarvis/tools/registry.py]
  → MemoryStore(...) built + register_memory_tools(tools, memory)  [tools/memory_tools.py]
  → system prompt loaded (system_prompt.md, or config.agent.system_prompt_file if set)
  → yields Agent(adapter, tools, memory, system_prompt)  [src/jarvis/agent.py]
    → Agent.__init__ appends memory.load_index() to the system prompt
  → on the caller's `async with` block exiting (clean, or a crash): every MCPToolClient is closed

jarvis (console script)                              [src/jarvis/cli.py: main() → asyncio.run(_main())]
  → load_dotenv() + load_config()                    [src/jarvis/config.py]
  → async with build_agent(config) as agent:
      loop: input("you> ") → await agent.step(user_input) → print result

jarvis-server (console script)                       [src/jarvis/server.py: main() → uvicorn.run(create_app())]
  → load_dotenv() + load_config()
  → FastAPI app; lifespan does async with build_agent(config) as agent: app.state.agent = agent
  → POST /chat {text} → (behind an asyncio.Lock, since one Agent's history
    isn't safe for concurrent callers) await agent.step(text) → {reply}
  → CORS restricted to the Vite dev origin (JARVIS_CORS_ORIGINS to override)
  → frontend/src/lib/backend.ts's getAgentResponse() is the browser-side caller
  → if config.telegram is set: start_telegram_bot(config, agent, lock)     [telegram_bot.py]
      long-polls Telegram (getUpdates) for messages from an allowlisted chat id,
      calls the *same* agent.step() under the *same* lock as /chat, replies via
      sendMessage — so a Telegram chat and the web HUD share one conversation
    stopped the same way MCP clients are: in the lifespan's shutdown path, clean exit or crash
```

`Agent.step()` owns the full tool-call loop internally: send history + available tools to the adapter, execute any requested tool calls via `ToolRegistry`, feed results back in, repeat until the model answers in plain text.

## Package layout

```
jarvis/
├── pyproject.toml              # deps: anthropic, google-genai, pyyaml, python-dotenv, mcp, httpx2, fastapi, uvicorn, python-telegram-bot
├── config/config.example.yaml  # template; real config.yaml is gitignored, per-machine
├── src/jarvis/
│   ├── config.py                        # JarvisConfig dataclasses + load_config()
│   ├── runtime.py                       # build_agent(): shared setup/teardown, used by cli.py and server.py
│   ├── cli.py                           # terminal entry point — see "Request flow" above
│   ├── server.py                        # HTTP entry point (jarvis-server) — what frontend/ talks to
│   ├── telegram_bot.py                  # optional Telegram long-polling interface, started from server.py's lifespan
│   ├── system_prompt.md                 # built-in default system prompt
│   ├── agent.py                         # Agent orchestrator — full tool-call loop, wired into cli.py and server.py
│   ├── llm/
│   │   ├── base.py                      # ChatMessage/ToolSpec/LLMResponse/LLMAdapter — the
│   │   │                                #   provider-neutral shape everything else imports
│   │   ├── registry.py                  # provider name -> adapter class
│   │   ├── adapters/gemini_adapter.py   # GeminiAdapter — active provider
│   │   └── adapters/anthropic_adapter.py  # unfinished, unregistered, deferred (needs paid billing)
│   ├── tools/
│   │   ├── schema.py                    # build_schema_from_signature(): inspect.signature -> JSON schema
│   │   ├── registry.py                  # ToolRegistry: register/add_tool/execute/as_llm_tool_specs
│   │   ├── mcp_client.py                # MCPToolClient: talks to one MCP server, stdio or remote HTTP
│   │   ├── mcp_oauth.py                 # OAuth (token cache + browser consent) for remote MCP servers
│   │   ├── mcp_overrides/               # per-server schema overrides + tool allowlists
│   │   │   ├── calendar.py              # Calendar's trimmed create/update/list-event schemas
│   │   │   └── ibkr.py                  # IBKR's read-only tool allowlist
│   │   ├── memory_tools.py              # remember/list_memory/read_memory/search_memory, wrapping MemoryStore
│   │   └── weather_tools.py             # get_current_weather — native, calls Open-Meteo directly
│   └── memory/store.py                  # MemoryStore: read/write/append/load_index/search
└── tests/test_config.py                 # only module with automated tests so far
```

## Components

**Config (`config.py`)** — YAML, resolved from an explicit path, `$JARVIS_CONFIG`, `./config.yaml`, or `~/.jarvis/config.yaml`, in that order. Holds `llm` (provider/model/api key env var), `memory` (root dir, user id), `agent` (system prompt override), `logging`, and `mcp_servers` (name → either a subprocess `command`, or a remote `url` — exactly one of the two, validated in `_parse_mcp_servers()` — used by `MCPToolClient`). API keys are read lazily from the environment, never stored in the config object itself.

**LLM adapters (`llm/`)** — `LLMAdapter` is an ABC with one method, `chat(messages, tools, system, max_tokens) -> LLMResponse`; every provider implements it, translating to/from that provider's own wire format. `llm/registry.py` maps a config string (`"gemini"`) to the adapter class. `GeminiAdapter` is the only complete, working one — both plain-message chat and tool-calling (both directions: offering tools, parsing the model's function-call requests back out) are verified against the real API. `AnthropicAdapter` exists but its `chat()` is unfinished and it's deliberately left out of the registry.

**Runtime (`runtime.py`)** — `build_agent(config)`, an async context manager that does all the setup `cli.py` used to do inline (build the adapter, register native + MCP tools, build memory, build the `Agent`) and guarantees every `MCPToolClient` is closed on the way out. The one place this logic lives, so `cli.py` and `server.py` can't drift apart.

**Tools (`tools/`)** — three pieces, wired together and into `Agent` via `runtime.build_agent()`:
- `schema.py`'s `build_schema_from_signature()` turns a Python function's signature into a JSON Schema dict (`str`/`int`/`float`/`bool`, required-if-no-default).
- `registry.py`'s `ToolRegistry` holds a `dict[str, Tool]` (`Tool` = name/description/parameters/func). `register()` is a decorator for native Python functions (uses `schema.py`); `add_tool()` takes an already-fully-described `Tool` directly (what MCP wiring will use). `execute()` calls a tool's `func` and handles both sync and async callables uniformly (`inspect.isawaitable` check). `as_llm_tool_specs()` converts everything registered into the `ToolSpec` list `LLMAdapter.chat()` expects.
- `mcp_client.py`'s `MCPToolClient` wraps one MCP server, over either of two transports: `connect()` spawns a subprocess and speaks stdio (`command` set — Google Calendar's path), or opens a Streamable HTTP connection to `url` with OAuth via `mcp_oauth.build_oauth_provider()` (IBKR's hosted connector). Both feed the same `read, write` streams into one `mcp.ClientSession`, so `list_tools()`/`call_tool()`/`close()` are identical regardless of transport. Google Calendar (stdio) and IBKR (remote) are verified live end-to-end on each path.
- `mcp_oauth.py` — everything the remote-HTTP branch needs that stdio never did: `_FileTokenStorage` (persists tokens + client registration per server under `~/.jarvis/mcp_oauth/`) and `build_oauth_provider()`, which adds a one-time browser consent flow on top. Only runs that flow when no valid cached token exists; every later `connect()` — including after the access token expires — reuses or silently refreshes the cached one. Also patches four bugs found in the third-party OAuth client itself (missing request header, a metadata mismatch on IBKR's side, scope not narrowing to read-only by default, and refresh not working after a restart) — see `PLAN.md`'s "Resolved: remote MCP transport + IBKR" for details on each.
- `mcp_overrides/` — per-server registration policy, one file per server (`calendar.py`, `ibkr.py`) plus a thin `__init__.py` dispatcher: `get_override(server_name, tool_name)` returns a hand-written, trimmed JSON schema when one's registered (Calendar's oversized `create-event`/`update-event`/`list-events`), else `None` — the tool call itself still goes to the real MCP server, validated against its own full schema. `is_allowed(server_name, tool_name)` returns `False` only for a tool a server's allowlist explicitly excludes (IBKR's write-capable tools); servers with no allowlist are unaffected. Both used by `runtime.build_agent()`'s registration loop.

**Agent (`agent.py`)** — owns `self.history: list[ChatMessage]` and runs the tool-calling loop: `step()` sends history + available tools to the adapter, executes any requested tool calls via `ToolRegistry`, feeds results back in, and repeats until the model answers in plain text. Implemented, wired into both `cli.py` and `server.py`, and verified end-to-end against the real Gemini API with a real MCP tool call.

**System prompt (`system_prompt.md`)** — the built-in default, loaded by `runtime.load_system_prompt()`; `config.agent.system_prompt_file`, if set, overrides it with a different file instead.

**HTTP server (`server.py`)** — `jarvis-server` (FastAPI + uvicorn): one shared `Agent` built via `runtime.build_agent()` at startup (FastAPI `lifespan`), torn down on shutdown. `POST /chat {text} -> {reply}` calls `agent.step()` behind an `asyncio.Lock`, since one `Agent`'s history isn't safe for two concurrent callers (see `PLAN.md`'s "Resolved: concurrent requests against one Agent"). CORS restricted to the Vite dev origin by default (`JARVIS_CORS_ORIGINS` env var to override). This is what `frontend/`'s HUD talks to — see `frontend/src/lib/backend.ts`'s `getAgentResponse()`. No streaming — `Agent.step()`/the LLM adapters return a full reply at once, not tokens incrementally.

**Telegram (`telegram_bot.py`)** — optional, fully off unless `config.telegram` is set. Started/stopped from `server.py`'s FastAPI lifespan using `python-telegram-bot`'s manual `Application` lifecycle (`initialize`/`start`/`updater.start_polling`, not the blocking `run_polling()`, since it has to live inside uvicorn's already-running event loop). Long-polls Telegram's `getUpdates` — outbound-only, so it works from behind a home NAT/router with no port-forwarding or public URL. Every incoming message is checked against `config.telegram.allowed_chat_ids`; anything else is logged and dropped, unanswered, since a reply would confirm the bot is alive to a stranger. Allowed messages go through the *same* `agent.step()` call and `asyncio.Lock` as `/chat`, so Telegram and the web HUD share one conversation history. Replies over 4096 characters (Telegram's per-message cap) are split on line boundaries before sending.

**Memory (`memory/store.py` + `tools/memory_tools.py`)** — markdown files with YAML frontmatter, one dir per `user_id`, under `config.memory.root_dir`. `MemoryStore`: `read`/`write`/`append` (all implemented and tested — `write` always emits the `---`/`---` structure so `read()` can always parse it back, and creates missing parent directories; `append` reads the existing entry or falls back to an empty one via `except FileNotFoundError`, preserving existing frontmatter unchanged); `load_index()` globs `memory_*.md` and pulls each file's `description` from its own frontmatter — no separate manually-maintained index file, so it can't drift out of sync; `search()` is plain substring matching, no embeddings.

Files aren't freely named by the model — writes go through `tools/memory_tools.py`'s `remember(category, text)` tool, restricted to a small fixed set of categories (`facts`, `preferences`), each with a description written once in code (`_CATEGORY_DESCRIPTIONS`), not invented per-call by the model. This was a deliberate choice (see `PLAN.md`'s "Memory" section) — an undescribed file is invisible to the model's own reasoning about what's worth reading, and free-form category creation makes that hard to guarantee. `list_memory`/`read_memory`/`search_memory` are the read-side counterparts, thin wrappers over the same store. `Agent.__init__` appends `memory.load_index()` to the system prompt at startup, so the model always knows what's been remembered without loading full contents by default.

**Weather (`tools/weather_tools.py`)** — `get_current_weather(location)`, a native tool calling Open-Meteo's geocoding + forecast APIs directly (`httpx2`). Originally built as a standalone MCP server ([weather-mcp](https://github.com/massibiella/weather-mcp), kept for reference/reuse elsewhere) and moved to a native tool once Google Calendar became the real, ongoing MCP integration — weather isn't reused outside Jarvis in practice, so there was no remaining reason to pay subprocess overhead for one simple HTTP call (see `PLAN.md`'s "Key decisions" for the full reasoning). Logic ported unchanged: same WMO weather-code mapping, same `httpx2.HTTPError`-specific error handling.

## Known gaps (today, not a roadmap — see PLAN.md for that)

- `AnthropicAdapter` is unfinished and unregistered — Gemini is the only usable provider today.
- No auto-summarization of a session into memory — the agent only remembers what it explicitly decided to save *during* a conversation via `remember`; nothing catches things it didn't flag in the moment, and nothing persists once `jarvis` exits unless `remember` was actually called (see `TODO.md`'s "Nice to have").
- `sessions/` (dated, per-session notes) from the original memory design sketch was never built — only the two fixed categories (`facts`, `preferences`) exist.
