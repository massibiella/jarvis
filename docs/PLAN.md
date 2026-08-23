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
7. **MCP transport: stdio for now, not SSE/HTTP.** Servers Jarvis launches itself run as local subprocesses — their code has to be physically present on whatever machine runs Jarvis. Fine since Jarvis runs on one machine; revisit with SSE/HTTP transport only if Jarvis and its MCP servers ever need to live on separate hosts.
8. **Weather moved off MCP, back to a native tool.** Originally built as `weather-mcp` (a standalone MCP server) specifically to learn how MCP itself works — a deliberate pedagogical choice, not a technical requirement. Reconsidered once Google Calendar became the real, ongoing MCP integration (a genuine third-party server, needs MCP): weather isn't meaningfully reused outside Jarvis in practice (unlike the abstract "any MCP client could use it" argument), and Calendar already exercises the MCP-client code path, so there's no remaining reason to pay subprocess/stdio overhead for what's really one simple HTTP call. Logic ported unchanged into `tools/weather_tools.py`; `weather-mcp` still exists standalone, just unused by Jarvis now. General takeaway: whether something belongs in its own MCP server or as a native tool comes down to "is this genuinely reusable outside Jarvis," not a fixed rule — decide per-tool, and it's fine to move a tool between the two if that answer changes.
9. **`MCPServerConfig`/`MCPToolClient` gained `env` support.** The Google Calendar MCP server needs an OAuth credentials file path passed via a `GOOGLE_OAUTH_CREDENTIALS` environment variable — not something the command line itself covers. Added `env: dict[str, str] | None` to `MCPServerConfig`, passed through to `mcp.StdioServerParameters(env=...)`, which merges it with the subprocess's normal inherited environment rather than replacing it. Verified live with a throwaway test server before trusting it.

## MCP integrations (target list, tackle one at a time — user writes the code)

Weather is done, but as a **native tool**, not MCP (see Key Decisions #8 above and `ARCHITECTURE.md`). Three real MCP targets:

1. **Google Calendar** — PRD item 1, wired and working. Chose the community server [`nspady/google-calendar-mcp`](https://github.com/nspady/google-calendar-mcp) over Google's own official one — at the time, the official server (`calendarmcp.googleapis.com`) used HTTP transport, which `MCPToolClient` didn't support yet (stdio-only then; it gained a remote HTTP+OAuth path for IBKR below — see item 3 — but Calendar's community server was also chosen for its documented read/write scopes, not transport alone, so it stays as-is), and its documented scopes looked read-only (view/freebusy, no create/update/delete — the PRD needs full CRUD). The community server supports stdio, full read/write, and local one-time OAuth ("Desktop app" credential type, no hosted redirect URI needed). Setup: Google Cloud Console project → enable Calendar API → OAuth client (Desktop app type, "User data" access) → download `gcp-oauth.keys.json` → add self as a test user under Audience. Wired into `config.yaml`:
   ```yaml
   mcp_servers:
     calendar:
       command: ["npx", "@cocal/google-calendar-mcp", "--enable-tools", "list-events,create-event,update-event,delete-event,get-freebusy,get-current-time"]
       env:
         GOOGLE_OAUTH_CREDENTIALS: "/path/to/gcp-oauth.keys.json"
   ```
   Needs Node/npm installed (the server is distributed via `npx`, not Python — MCP servers can be any language, `MCPToolClient` is language-agnostic). OAuth working, 6 tools enabled, schemas trimmed for `create-event`/`update-event`/`list-events` (see "Resolved: Google Calendar tool-schema cost" below). `create-event` verified live previously (a real event was created); manual re-verification of create/update/list against the new trimmed schemas specifically is still open.
2. **Google Maps / traffic (commute time)** — PRD item 15. Same "find an existing server first" approach, not started.
3. **IBKR (investment portal)** — PRD item, done, verified live against a real account. IBKR's classic APIs (TWS API, Client Portal Web API) need an IBKR Pro account plus a locally-running companion process — ruled out (Lite account). Instead uses IBKR's official hosted MCP connector (`https://api.ibkr.com/v1/api/mcp-public`): remote, Streamable HTTP transport, OAuth 2.1, read-only enforced both by scope and by an allowlist (see "Resolved: remote MCP transport + IBKR" below). First remote MCP server Jarvis talks to, so `MCPToolClient`/`config.py` gained a second transport. Wired into `config.yaml`:
   ```yaml
   mcp_servers:
     ibkr:
       url: "https://api.ibkr.com/v1/api/mcp-public"
   ```
   First `jarvis` run opens a browser to IBKR's consent screen; later runs — including after the access token expires — reuse/refresh the cached token from `~/.jarvis/mcp_oauth/ibkr.json` silently, no browser.

For each: confirm a real MCP server (existing or hand-built) before writing any registry-side code against it — same "verify the real shape, don't guess" approach used throughout this project.

## Memory (index + on-demand recall)

**Decision (from discussion): the agent writes memory itself, via a tool — not the user, and not through a manually-curated `index.md`.** Originally sketched as a user-triggered `/remember` CLI command plus a hand-maintained `index.md`; reconsidered because a human was never actually going to be the one deciding what's worth remembering — the whole point was the *agent* judging that during a conversation. That reframing also killed the manually-maintained `index.md` idea: if the agent can invent arbitrary new topics/files as it goes, nobody's around to write a good description for each one, and an undescribed file is invisible to the agent's own future reasoning (can't decide something's relevant if the index gives no signal about what's in it). Fixed by constraining the agent to a **small, fixed set of categories** (not free-form file/topic creation) — each category's description only needs writing once, by a human, in code — and deriving the index automatically from what's actually on disk, rather than trusting anyone to keep a separate file in sync.

```
data/memory/
└── users/default/
    ├── memory_facts.md          # durable facts about the user
    ├── memory_preferences.md    # communication/style preferences
    └── sessions/                 # optional dated notes, not built
```

Each file: YAML frontmatter (`title`, `description`, ...) + markdown body. Frontmatter parsed with a `---` split + `yaml.safe_load` (PyYAML — already used by `config.py`). `description` in each file's frontmatter is what `load_index()` surfaces — see below.

`MemoryStore` (`src/jarvis/memory/store.py`) — **all five methods done, implemented, tested:**
- `read`/`write`/`append` — `write` always emits the `---`/`---` structure even for an empty/`None` frontmatter, so `read()` can always parse it back; `write` also creates missing parent directories, since nothing else does; `append` takes an optional `default_frontmatter`, used only the first time a file is created (so a category's description gets set on creation, not lost or left blank) — an existing file's frontmatter is always preserved as-is on later appends.
- `load_index()` — globs `user_dir` for `memory_*.md`, `read()`s each one, pulls `.frontmatter.get("description", "(no description)")`, returns a formatted list. No separate `index.md` file — the index is *derived* from the real files every time, so it can't drift out of sync.
- `search()` — plain substring match over file contents, no embeddings.

**Tools** (`src/jarvis/tools/memory_tools.py`, not `cli.py` — same reasoning as MCP tools living in their own file, not inline in the entry point) — **all done:**
- `remember(category: str, text: str) -> str` — `category` restricted to `"facts"` / `"preferences"`, enforced two ways: the docstring tells the model, and the function body validates against `_CATEGORY_DESCRIPTIONS` at runtime, returning a clear error instead of writing anything if an unknown category slips through (`tools/schema.py` doesn't support `Literal` yet, so this can't be enforced at the schema level — the runtime check is the actual guarantee). Calls `memory.append(f"memory_{category}.md", text, default_frontmatter=...)`, where the frontmatter (including `description`) for each category is a fixed dict written once in `memory_tools.py` (`_CATEGORY_DESCRIPTIONS`), not invented by the model per call.
- `list_memory()` / `read_memory(path)` / `search_memory(query)` — thin wrappers around `MemoryStore`.

Wiring — **done:**
- **Startup**: `Agent.__init__` appends `memory.load_index()` to the system prompt.
- `system_prompt.md` tells the model the `remember` tool exists and when to use it (durable info worth recalling later, not one-off conversational context).

`users/default/` is the multi-user-ready layout from Key Decisions above; no auth logic in this milestone.

**Real bug found and fixed along the way:** `tools/schema.py` broke on any native tool defined in a module using `from __future__ import annotations` (true for nearly every file in this project) — `param.annotation` becomes a plain string (e.g. `'str'`) under PEP 563's deferred evaluation, not the actual type object, so a direct `_PYTHON_TO_JSON_TYPES[param.annotation]` lookup raised `KeyError`. This had never surfaced before because every native tool tested so far lived in a throwaway script without that import. Fixed by using `typing.get_type_hints(func)` instead of raw signature annotations — resolves deferred string annotations back into real type objects regardless of the defining module's own imports.

## Suggested implementation order (each step independently testable)

Steps 1–7 are done — see `ARCHITECTURE.md` for current state. `jarvis` runs end-to-end today: real config, real MCP tool (weather), real tool-calling loop, real persistent memory (agent-driven, not user-triggered), all verified live.

8. **Polish** — clean error surfacing in the CLI, logging, README.
9. **End-to-end verification** (below) + final `pytest` / `ruff check` / `ruff format --check` pass — automated tests for `MemoryStore`/`memory_tools.py` still to write (manual/scripted verification only so far).

## Verification

**Manual CLI session:**
```
$ jarvis
you> what's the weather in Boston?
jarvis> [agent calls get_current_weather via MCPToolClient, answers correctly]   ✅ verified
you> I'm doing a 12-week Spanish study plan, currently on week 3
jarvis> Noted.   [agent decided on its own to call remember(category="facts", ...)]  ✅ verified
you> what am I working on right now?
jarvis> [agent uses list_memory/read_memory to find the note, answers correctly]  ✅ verified
you> /exit
```
All three exchanges above are real and verified live — memory is agent-driven, there's no `/remember` command (see "Memory" section above for why that changed from the original plan).

**Automated tests (pytest):** still to write — memory read/write/append/index/search round trips (only manually/scripted-verified so far); `FakeAdapter`-driven agent loop test with zero network calls.

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

## Resolved: concurrent requests against one Agent

Became real once `server.py` (the HTTP interface the frontend HUD talks to) existed — a browser can fire a second `/chat` request before the first reply comes back, which would otherwise mean two overlapping `agent.step()` calls mutating the same shared `self.history` concurrently. Fixed exactly as anticipated below: `server.py` holds one `asyncio.Lock` around its `agent.step()` call, so a second incoming request queues behind the first instead of interleaving. Single shared `Agent`/history for the whole process, matching today's single-user scope — not one `Agent` per HTTP client.

## Resolved: Google Calendar tool-schema cost

Was: `as_llm_tool_specs()` sends *every* registered tool's full JSON schema on *every single request*, regardless of whether that turn needs it. Measured live with Calendar's 7 tools registered: ~5,484 tokens of pure schema, every turn, dominated by 3 tools — `create-event` (47.5%), `update-event` (28.5%), `list-events` (10.9%), ~87% combined. Directly caused hitting Gemini's free-tier per-minute token quota during testing. First mitigation was Google Calendar's `--enable-tools` whitelist flag (13 → 7 tools, ~32% reduction) — a config change, no code.

Considered and rejected as the real fix: general tool-relevance pre-filtering (deciding at request time which tools' schemas to even send). Explored a refined "try first with no schemas, ask for tool names only if needed" design — even that still costs 2 sequential LLM calls for any turn that genuinely needs a tool, because a tool's full schema has to be present in the same call that produces a structured `tool_call` for it. Since the real cost driver was 3 specific bloated schemas (not the number of tools), filtering would have added real complexity to `Agent.step()`'s loop to work around a much smaller, more direct problem.

Fixed instead: `src/jarvis/tools/mcp_overrides.py` — hand-written, trimmed JSON schemas for `create-event`/`update-event`/`list-events`, keyed by `(server_name, tool_name)` so a same-named tool on a different future MCP server can't collide. Inspecting the real schemas showed most of the bulk was Google-Workspace-only fields (`focusTimeProperties`, `outOfOfficeProperties`, `workingLocationProperties`, `conferenceData`, `extendedProperties`, `attachments`, `source`) and edge cases (a 32-value `fields` enum on `list-events`, multi-account filtering) that don't apply to a personal account. `cli.py`'s `_mcp_tool_to_tool()` now takes `server_name` and uses `mcp_overrides.get_override()`'s schema when one exists, otherwise passes the MCP server's own schema through unchanged (every other tool, unaffected). The override only changes what schema the LLM sees — the tool call still goes to the real MCP server, validated against its full original schema, so nothing breaks. Result: Calendar's total tool-schema cost dropped from ~5,484 to ~1,511 tokens (72% reduction), measured the same way as the original diagnosis.

**Remaining, not decided:** dropping `manage-accounts` (a setup-time tool for adding/removing Google accounts, not something the agent should call mid-conversation) from the registry entirely — the one real remaining reduction candidate; everything else left (`delete-event`, `get-freebusy`, `get-current-time`) was already small.

**Still open, general problem for later:** every *new* tool (Maps, IBKR, etc.) still adds fixed per-turn cost regardless of relevance. This fix solved the actual instance that caused real pain, not the general "ship everything every turn" architecture — revisit only if/when a future tool turns out as bloated as Calendar's was.

## Resolved: remote MCP transport + IBKR (verified live)

`MCPToolClient` only spoke stdio until IBKR's official connector needed a second path — remote, not spawned locally. `list_tools()`/`call_tool()`/`close()` didn't change; they only ever touch `self._session`. `connect()` gained a branch: `command` → stdio (unchanged); `url` → `streamable_http_client()` with an OAuth-authenticated `httpx2.AsyncClient`. `MCPServerConfig` requires exactly one of `command`/`url` per server; Calendar's entry is untouched.

`tools/mcp_oauth.py` holds everything stdio never needed: token/client-info persistence (`~/.jarvis/mcp_oauth/<server>.json`), a one-time browser consent flow, and read-only enforcement. IBKR's server always tries to grant both read and write scope by default regardless of what's requested, so the SDK's scope selection is patched to strip write before it's ever requested — confirmed live, a write call returns `"Insufficient scope: mcp.write required"`. `tools/mcp_overrides/ibkr.py`'s allowlist adds a second layer on top: write-capable tools never get registered into Jarvis at all, so the agent doesn't see them as options.

Four real bugs found in the third-party `mcp` SDK's OAuth client along the way (not our own code), each confirmed by tracing live requests against IBKR's real servers, all patched in `mcp_oauth.py`/`mcp_client.py`:
1. OAuth requests missing `User-Agent` entirely — IBKR's edge blocks them. Fixed with a request hook.
2. IBKR's own metadata fails the standard issuer-match check — narrow, exact-pair exception, not a general bypass.
3. Scope selection ignores a client's requested narrower scope, always requesting everything the server advertises.
4. Silent refresh after a restart: the SDK never tracks a cached token's real expiry, and guesses the wrong token endpoint before real discovery runs.

Live end-to-end: real account, real browser consent, real read-only data, and a real silent refresh confirmed working after simulating an expired token.

## Future step: packaging & distribution (native app, not Docker)

Not in scope now — a few in-progress features land first; revisit once those are done. Notes captured here so the decisions from discussion aren't lost in the meantime.

**Context:** Jarvis needs to run as a normal double-click app on the user's own Mac/Windows machine (not a dedicated always-on server), started manually for a first pass — no OS autostart-at-login or tray icon yet, those are separate later steps. PRD §5.2/§6 want an eventual always-on background service with a scheduler; packaging is the prerequisite, not the scheduler itself.

**Decision: native packaging, not Docker.** Docker is built for headless servers — it needs Docker Desktop running as an extra dependency, doesn't give tray icons/autostart/mic access, and this runs on the user's own laptop/desktop, not a dedicated box. Its main appeal (filesystem isolation via volumes) isn't worth the tradeoff here — Jarvis already has no shell/file-write tool, and that constraint holds going forward regardless of packaging choice (see "Filesystem/system safety" below).

**Work items, when this gets picked up:**
1. **Bundle the Python backend into a standalone binary** — PyInstaller or Nuitka, so the machine running Jarvis doesn't need Python installed. Evaluate both: PyInstaller is the more battle-tested default; Nuitka compiles to a real binary (smaller/faster) but is trickier with dynamic imports. Decide once we're actually here, not now.
2. **Build the frontend to static files** (`npm run build` in `frontend/`) and **serve them from `jarvis-server`** instead of relying on the Vite dev server — `create_app()` (`src/jarvis/server.py`) currently only exposes `/health` and `/chat`, no static-file mount. One process, one thing to launch, instead of two terminals.
3. **Wrap into an OS installer** — `.dmg`/`.pkg` on Mac, NSIS/Inno Setup `.exe` on Windows — placing the app in the normal `/Applications` / `Program Files` location.
4. **Node/npm dependency risk:** the Google Calendar MCP server is launched via `npx @cocal/google-calendar-mcp` (`config.yaml`'s `mcp_servers.calendar.command`) — PyInstaller/Nuitka only bundle the Python side, so a packaged Jarvis would still require Node.js installed separately for Calendar to work, undermining the "no manual setup" goal. Needs a decision when we get here: bundle a Node runtime too, find/build a pure-Python or HTTP-based calendar path, or accept Node as a documented prerequisite.
5. **voice-server folding-in:** `voice-server/` is an explicitly temporary standalone Flask prototype (per its own README) — decide whether it gets absorbed into the main agent process before or as part of packaging, since a packaged app shouldn't require a third manually-started service.
6. **Code signing:** Gatekeeper (Mac) and SmartScreen (Windows) both flag/block unsigned apps by default — needs an Apple Developer cert + notarization, and a Windows code-signing cert, or the app will look broken/untrusted on first launch.
7. Explicitly deferred out of this first pass (per discussion): tray icon, autostart-at-login, and any native window shell (Tauri/Electron) — HUD stays browser-based for now.

**Filesystem/system safety (holds regardless of packaging approach):** no shell/exec or unscoped file-write tool on the agent; any future tool that touches disk stays scoped to Jarvis's own `data/` directory; the packaged app runs as a standard user, no elevated/admin permissions; uninstall means deleting the app, no registry edits or scattered files.

## Remaining files

None — Milestone 1's core implementation is complete. What's left is Step 8/9 (polish, automated tests for memory), the two deferred "Future step" sections above (history management, concurrent requests), the packaging/distribution future step above, and manually re-verifying Calendar's create/update/list-event tools against the new trimmed schemas (code done, live re-test not yet run — separate from IBKR's, which is verified).
