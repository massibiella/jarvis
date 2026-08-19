# Jarvis — Milestone 1: Core Agent Skeleton

## Context

Jarvis is a from-scratch personal assistant project. The PRD (`../PRD.md`) lists 14 eventual features — calendar, IBKR investing, newsletters, memory, a JARVIS-style UI, multi-user auth, weather, daily check-ins, standalone reminders, web research, and an explicit requirement to be **LLM-agnostic via config**. That's too much to build at once, and most of it depends on a working agent core existing first.

This plan covers only the first milestone: **the core agent skeleton** — the foundation every later feature (calendar, IBKR, weather, web research, etc.) will plug into as a tool. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how the system works today; this file covers what's left to build and why past decisions were made the way they were.

Team context: one experienced dev + one dev newer to programming, both new to agentic applications specifically. This shaped several of the decisions below.

## How we'll work

This is a learning project as much as a build. This plan file lives in the repo so it's a shared reference you both read and edit directly.

**Split:** steps 1–2 (scaffolding + config loading) were implemented as a worked example of the patterns (package layout, dataclass config, error handling, test structure). From step 3 onward, the corresponding files are stubs with docstrings and `TODO` markers pointing back to this plan — you and Adnan write the actual logic there.

## Key decisions (from discussion)

1. **No agent framework for the loop.** Hand-write the tool-calling loop directly behind a provider-agnostic adapter interface. Rationale: fewer layers to debug through while learning, keeps "LLM-agnostic" honest (a thin custom interface, not a framework's provider abstraction), and the loop is small enough that swapping in LangGraph later is a localized rewrite of one module, not a restart.
2. **MCP-ready tool registry.** The tool registry's shape (name, description, JSON-schema parameters, execute) was designed so an MCP client could register MCP-server tools alongside native Python tools without changing the registry's interface. This paid off in practice: `MCPToolClient` plugs into `ToolRegistry` via `add_tool()` with zero changes to `ToolRegistry` itself.
3. **Memory: flat files, index-at-startup + on-demand recall, no vector DB.** Persistent memory (distinct from in-conversation history) lives as markdown files with YAML frontmatter, mirroring the pattern Claude Code itself uses for its own memory. At session start, only a lightweight **index** (file list + one-line descriptions) loads into the system prompt — not full file contents. A `recall` tool lets the agent list/search/read specific files on demand mid-conversation. Vector search is an explicit non-goal until plain-text/keyword lookup actually proves insufficient.
4. **Multi-user readiness without building auth.** Memory is laid out under `users/<user_id>/` with `user_id` defaulting to `"default"` in config. This costs nothing now and avoids a data-layout migration when auth (a separate future milestone) lands.
5. **Gemini over Anthropic as the first working provider.** Anthropic's API needs paid billing; Gemini has a usable free tier. `AnthropicAdapter` is left unfinished and unregistered until there's a reason to pay for API access — a sequencing choice, not a design problem. Note: Gemini's free tier allows prompt/response data to be used for training — revisit before Jarvis handles real personal/financial data (see the note in `gemini_adapter.py`).
6. **Async end-to-end, decided ahead of actually needing it.** The MCP client SDK is fully async, and a persistent MCP connection can't be reused across separate `asyncio.run()` calls — asyncio resources are loop-affine, so spinning up a new event loop per call breaks a connection opened in a previous one. Rather than retrofit later, `cli.py`, `Agent.step`, and `ToolRegistry.execute` were all made async from the start.
7. **MCP transport: stdio for now, not SSE/HTTP.** Servers Jarvis launches itself (like `weather-mcp`) run as local subprocesses — their code has to be physically present on whatever machine runs Jarvis. Fine since Jarvis runs on one machine; revisit with SSE/HTTP transport only if Jarvis and its MCP servers ever need to live on separate hosts.

## MCP integrations (target list, tackle one at a time — user writes the code)

Weather is done (see `ARCHITECTURE.md`). Two more targets, in order (both need Google OAuth — real setup friction, unlike weather):

1. **Google Calendar** — PRD item 1. Check for an existing community/official MCP server first rather than hand-rolling OAuth.
2. **Google Maps / traffic (commute time)** — PRD item 15. Same "find an existing server first" approach.

For each: confirm a real MCP server (existing or hand-built) before writing any registry-side code against it — same "verify the real shape, don't guess" approach used throughout this project. Neither is designed yet.

## Memory (index + on-demand recall) — not yet built, Step 7

```
data/memory/
├── index.md                      # file list + one-line descriptions; loaded into system prompt at startup
└── users/default/
    ├── facts.md
    ├── preferences.md
    └── sessions/                  # optional dated notes
```

Each file: YAML frontmatter (`title`, `tags`, `updated_at`) + markdown body. Frontmatter parsed with a `---` split + `yaml.safe_load` (PyYAML — already used by `config.py`).

`MemoryStore` (see `src/jarvis/memory/store.py` for the exact method signatures — already stubbed) needs: `read`/`write`/`append` on a single file under `users/<user_id>/`; `load_index()` returning just the index (not full file contents) for the system prompt; `search()` as plain keyword/grep, no embeddings.

Wiring, once implemented:
- **Startup**: `Agent.__init__` appends `memory.load_index()` to the system prompt.
- **Write path**: explicit `/remember <text>` CLI command → `memory.append("facts.md", text)`.
- **Recall path**: register `recall` tool(s) in `ToolRegistry` — `list_memory()`, `read_memory(path)`, `search_memory(query)` — thin wrappers around `MemoryStore`, so the agent can pull a specific file's content into context only when actually needed.

`users/default/` is the multi-user-ready layout from Key Decisions above; no auth logic in this milestone.

## Suggested implementation order (each step independently testable)

Steps 1–6 are done — see `ARCHITECTURE.md` for current state. `jarvis` runs end-to-end today: real config, real MCP tool (weather), real tool-calling loop, verified live.

7. **Memory store + recall** — see "Memory" section above. Tests: write-then-read round trip, index generation, search over sample files. `/remember <text>` CLI command once `MemoryStore` exists.
8. **Polish** — clean error surfacing in the CLI, logging, README.
9. **End-to-end verification** (below) + final `pytest` / `ruff check` / `ruff format --check` pass.

## Verification

**Manual CLI session:**
```
$ jarvis
you> what's the weather in Boston?
jarvis> [agent calls get_current_weather via MCPToolClient, answers correctly]   ✅ verified
you> /remember I'm doing a 12-week Spanish study plan, currently on week 3
jarvis> Noted.
you> what am I working on right now?
jarvis> [agent uses recall/search_memory to find the note, answers correctly]
you> /exit
```
The weather exchange above is real and already verified live. The `/remember`/recall exchange is the remaining target — confirm `data/memory/users/default/facts.md` contains the note and `index.md` reflects it once Step 7 is done.

**Automated tests (pytest):** memory read/write/index/search round trips; `FakeAdapter`-driven agent loop test with zero network calls.

**Acceptance gate:** `pytest` and `ruff check . && ruff format --check .` both clean.

## Future step: conversation history management (post–Milestone 1)

Not in scope for Milestone 1 — `self.history` in `agent.py` can grow unbounded for now. Revisit once the core loop (Step 6) is working end to end; don't let this block finishing `step()`.

**Decision (from discussion):** lean on Anthropic's native **compaction** feature rather than hand-rolling summarization or a trim-by-count policy ourselves.

- Beta feature, header `compact-2026-01-12`. Available on Claude Fable 5, Opus 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 5, Sonnet 4.6.
- Past a token threshold, Anthropic automatically summarizes older conversation content server-side and returns a `compaction` content block in the response.
- Hard requirement: the *full* `response.content` (not just the extracted text) must be appended back into history on the next request — the compaction block has to survive being stored and resent verbatim, or the mechanism breaks.

**Open design question to resolve when we get here (deliberately not decided now):** this doesn't fit cleanly into the "`chat()` is a pure stateless translator" model, because the compaction block is opaque, Anthropic-specific state that needs to round-trip through our own `ChatMessage` history untouched. Two directions to weigh at that point, not now:
  - (a) give `ChatMessage`/`LLMResponse` an opaque passthrough field the adapter fills in and later reads back, without `agent.py` needing to know what's inside it, or
  - (b) let the adapter keep its own internal copy of history in native format, with our neutral `list[ChatMessage]` as an external-facing view rather than the source of truth.

  Either way, this is a provider-specific mechanism — a future OpenAI/other adapter without an equivalent feature would need its own strategy (e.g. plain trim-by-count), which is fine: `agent.py` shouldn't have to know or care which approach a given adapter uses, only that history stays within bounds.

## Future step: concurrent requests against one Agent (post–Milestone 1)

Not a problem today — `cli.py`'s loop is strictly sequential (`input()` blocks until you type, `agent.step()` runs to completion before the next `input()` call), so `self.history` is only ever touched by one in-flight `step()` at a time.

**Why this will matter later:** any future interface that can send a *second* message before the first response comes back (Telegram, a web chat) would mean two overlapping `agent.step()` calls running concurrently against the same `Agent`, both reading/appending to the same shared `self.history` list — a race condition. Worse, a naive "pop the last message on failure" approach (like `cli.py`'s current error handling) breaks under overlap: the last message in `self.history` might belong to the *other* in-flight request, not the one that actually failed.

**Direction to take when this becomes real, not decided now:** serialize access per `Agent`/conversation — e.g. an `asyncio.Lock` so a second incoming message queues behind the first `step()` call instead of running concurrently, rather than trying to make concurrent history mutation itself safe.

## Remaining files
- `src/jarvis/memory/store.py` — not started, the only unfinished piece of Milestone 1
