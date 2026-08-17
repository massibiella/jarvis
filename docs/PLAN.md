# Jarvis — Milestone 1: Core Agent Skeleton

## Context

Jarvis is a from-scratch personal assistant project. The PRD (`../PRD.md`) lists 14 eventual features — calendar, IBKR investing, newsletters, memory, a JARVIS-style UI, multi-user auth, weather, daily check-ins, standalone reminders, web research, and an explicit requirement to be **LLM-agnostic via config**. That's too much to build at once, and most of it depends on a working agent core existing first.

This plan covers only the first milestone: **the core agent skeleton** — the foundation every later feature (calendar, IBKR, weather, web research, etc.) will plug into as a tool. No real integrations ship in this milestone; the goal is a working, testable chat loop with the right extension points already in place.

Team context: one experienced dev + one dev newer to programming, both new to agentic applications specifically. This shaped two decisions below — hand-writing the agent loop instead of adopting a framework (LangChain/Pydantic AI), and keeping the memory design simple (flat files, no vector DB) until there's an actual reason to add complexity.

## How we'll work

This is a learning project as much as a build. This plan file lives in the repo so it's a shared reference you both read and edit directly. The "Suggested implementation order" section below is deliberately broken into small, independently-testable steps for exactly this reason.

**Split:** steps 1–2 (scaffolding + config loading) are implemented as a worked example of the patterns (package layout, dataclass config, error handling, test structure) — see `src/jarvis/config.py` and `tests/test_config.py`. From step 3 onward (LLM adapter, CLI loop, tool registry, memory + recall), the corresponding files are stubs with docstrings and `TODO` markers pointing back to this plan — you and Adnan write the actual logic there.

## Key decisions (from discussion)

1. **No agent framework for the loop.** Hand-write the tool-calling loop (~40-80 lines) directly on the Anthropic SDK, behind a provider-agnostic adapter interface. Rationale: fewer layers to debug through while learning, keeps "LLM-agnostic" honest (a thin custom interface, not a framework's provider abstraction), and the loop is small enough that swapping in LangGraph later is a localized rewrite of one module, not a restart — the LLM adapter, tool registry, memory store, and CLI all survive that swap untouched.
2. **MCP-ready tool registry.** The tool registry's shape (name, description, JSON-schema parameters, execute) is designed so an MCP client can register MCP-server tools alongside native Python tools later, without changing the registry's interface. No MCP client ships in this milestone — this is an extension point, not a feature.
3. **Memory: flat files, index-at-startup + on-demand recall, no vector DB.** Persistent memory (distinct from in-conversation history) lives as markdown files with YAML frontmatter, mirroring the pattern Claude Code itself uses for its own memory. At session start, only a lightweight **index** (file list + one-line descriptions) loads into the system prompt — not full file contents. A `recall` tool lets the agent list/search/read specific files on demand mid-conversation. This is what makes "reference a study plan from months ago" work without blowing up context size as memory grows. Vector search is an explicit non-goal until plain-text/keyword lookup actually proves insufficient.
4. **Multi-user readiness without building auth.** Memory is laid out under `users/<user_id>/` with `user_id` defaulting to `"default"` in config. This costs nothing now and avoids a data-layout migration when auth (a separate future milestone) lands.

## Package layout

```
jarvis/
├── pyproject.toml
├── README.md
├── docs/
│   └── PLAN.md                      # this file
├── config/
│   └── config.example.yaml
├── src/jarvis/
│   ├── config.py                    # JarvisConfig dataclasses + load_config()  [done]
│   ├── cli.py                       # entry point: main() chat loop             [stub]
│   ├── agent.py                     # Agent orchestrator (history + tool-call loop) [stub]
│   ├── llm/
│   │   ├── base.py                  # LLMAdapter ABC, ChatMessage, ToolSpec, ToolCallRequest, LLMResponse [stub]
│   │   ├── registry.py              # provider name -> adapter class            [stub]
│   │   └── anthropic_adapter.py     # AnthropicAdapter(LLMAdapter)              [stub]
│   ├── tools/
│   │   ├── registry.py              # ToolRegistry, @registry.register decorator (MCP-ready shape) [stub]
│   │   ├── schema.py                # inspect.signature -> JSON schema          [stub]
│   │   └── examples.py              # gated demo tool, for plumbing verification only [stub]
│   └── memory/
│       └── store.py                 # MemoryStore: frontmatter read/write, index, recall [stub]
├── tests/
│   ├── test_config.py               # [done]
│   ├── test_tools_registry.py       # [to write, Step 5]
│   ├── test_memory_store.py         # [to write, Step 7]
│   ├── test_llm_anthropic_adapter.py   # [to write, Step 3] mocked anthropic client, no network
│   └── test_agent_tool_loop.py         # [to write, Step 6] FakeAdapter test double, no network
└── data/                              # gitignored, created at runtime
    └── memory/
        ├── index.md
        └── users/default/{facts.md,preferences.md}
```

`src/` layout avoids import-shadowing with `pip install -e`. `data/` and `config.yaml` are gitignored.

## LLM adapter (provider-agnostic)

`llm/base.py` — plain dataclasses (no pydantic needed yet) + an ABC:

```python
Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    role: Role
    content: str | None = None
    tool_calls: list[ToolCallRequest] | None = None
    tool_call_id: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest]
    stop_reason: str
    raw: Any = None


class LLMAdapter(ABC):
    @classmethod
    @abstractmethod
    def from_config(cls, llm_config: "LLMConfig") -> "LLMAdapter": ...

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
```

`llm/registry.py`: `dict[str, type[LLMAdapter]]` (e.g. `{"anthropic": AnthropicAdapter}`), resolved from `config.llm.provider`. Adding a provider later = one adapter module + one registry entry.

`llm/anthropic_adapter.py`: wraps `anthropic.Anthropic().messages.create(...)`. Translates `ToolSpec` → Anthropic's `{"name", "description", "input_schema"}`; walks `response.content` collecting `text` blocks into `.content` and `tool_use` blocks into `.tool_calls` (input is already parsed JSON — no manual parsing); maps `stop_reason` straight through. Non-streaming for this milestone; streaming is a natural v2 addition behind the same `chat()` shape. Model/API key come from config — nothing hardcoded (default in `config.example.yaml`: `claude-opus-5`).

## Tool registry (MCP-ready)

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., str]


class ToolRegistry:
    def register(
        self, name=None, description=None
    ): ...  # decorator, derives schema via inspect.signature
    def execute(self, name: str, arguments: dict) -> str: ...
    def as_llm_tool_specs(self) -> list[ToolSpec]: ...
```

`tools/schema.py` derives JSON schema from function type hints (str/int/float/bool/Optional/list); unsupported annotations raise clearly rather than guessing. Because a `Tool` is just name/description/schema/callable, an MCP client can register MCP-server tools into the same registry without changing this interface.

**Update (from discussion): the MCP client isn't deferred — it's the plan for the first real tools.** Original scope had a throwaway example tool proving the plumbing works, then real tools added later as plain Python functions. Decision now: skip the throwaway tool (removed `tools/examples.py`) and prove the registry directly with real MCP-sourced tools — see "MCP integrations" below.

## MCP integrations (target list, tackle one at a time — user writes the code)

Three target integrations, in this order (easiest first — the later two need Google OAuth, which is real setup friction similar to what we hit with API keys/billing; weather needs none):

1. **Weather** — no auth needed. Check whether a trustworthy existing MCP weather server exists before building one; if not, a small custom MCP server wrapping [Open-Meteo](https://open-meteo.com) (free, no API key) is a reasonable and genuinely educational fallback — mirrors the "write your own MCP server" pattern already called out for IBKR.
2. **Google Calendar** — PRD item 1. Needs Google OAuth setup; check for an existing community/official MCP server first rather than hand-rolling OAuth.
3. **Google Maps / traffic (commute time)** — PRD item 15 (added this session). Also needs Google OAuth/API access; same "find an existing server first" approach.

For each: confirm a real MCP server (existing or hand-built) before writing any registry-side code against it — same "verify the real shape, don't guess" approach used for the Gemini adapter. None of these are designed yet — do that when we get to each one, not now.

## Memory (index + on-demand recall)

```
data/memory/
├── index.md                      # file list + one-line descriptions; loaded into system prompt at startup
└── users/default/
    ├── facts.md
    ├── preferences.md
    └── sessions/                  # optional dated notes
```

Each file: YAML frontmatter (`title`, `tags`, `updated_at`) + markdown body. Frontmatter parsed with a `---` split + `yaml.safe_load` (PyYAML — already needed for config).

```python
class MemoryStore:
    def __init__(self, root: Path, user_id: str = "default"): ...
    def read(self, relative_path: str) -> MemoryEntry: ...
    def write(self, relative_path: str, body: str, frontmatter: dict | None = None) -> None: ...
    def append(self, relative_path: str, text: str) -> None: ...
    def load_index(self) -> str: ...
    def search(self, query: str) -> list[str]: ...  # basic keyword/grep over file contents
```

Wiring:
- **Startup**: `Agent.__init__` appends `memory.load_index()` (not full file contents) to the system prompt.
- **Write path**: explicit `/remember <text>` CLI command → `memory.append("facts.md", text)`. Auto-summarizing conversation into memory is out of scope here (natural v2: either background summarization, or exposing `append` as an agent-callable tool).
- **Recall path**: register `recall` tool(s) in the `ToolRegistry` — `list_memory()`, `read_memory(path)`, `search_memory(query)` — thin wrappers around `MemoryStore`, so the agent can pull a specific file's full content into context only when the conversation actually needs it (e.g. "what's my study plan say"), rather than every file being loaded every turn.

`users/default/` is the multi-user-ready layout described above; no auth logic in this milestone.

## Config

YAML, human-editable — see `config/config.example.yaml`:

```yaml
llm:
  provider: anthropic
  model: claude-opus-5
  api_key_env: ANTHROPIC_API_KEY   # env var name, never the key itself
  max_tokens: 4096

memory:
  root_dir: ./data/memory
  user_id: default

agent:
  system_prompt_file: null

logging:
  level: INFO
```

`src/jarvis/config.py`: plain dataclasses (`LLMConfig`, `MemoryConfig`, `AgentConfig`, `LoggingConfig`, `JarvisConfig`) + `load_config(path=None)` resolving explicit path → `$JARVIS_CONFIG` → `./config.yaml` → `~/.jarvis/config.yaml`. `LLMConfig.api_key` reads the env var lazily, raising `ConfigError` if unset. **Done — read this file for the patterns used elsewhere.**

## CLI chat loop

`agent.py` — `Agent.step(user_text)` runs: append user message → `adapter.chat(...)` → if `tool_calls`, execute each via `ToolRegistry.execute`, append `tool` results, loop; else append assistant message and return. Errors from tool execution are caught and returned as an error string in the tool result (visible to the model, not a crash).

`cli.py` — `main()`: parse `--config`, load config, resolve adapter from registry, build `ToolRegistry` (+ example tool if enabled, + recall tools always), build `MemoryStore`, build `Agent`, then a `input()` loop supporting `/exit`, `/remember <text>`, and plain chat. Entry point via `pyproject.toml` `[project.scripts] jarvis = "jarvis.cli:main"`.

## Suggested implementation order (each step independently testable)

1. **Scaffolding** — `pyproject.toml`, package skeleton, ruff config, empty `tests/`. Verify: `pip install -e .`, `ruff check .`, `python -c "import jarvis"`. **[done]**
2. **Config loading** — `config.py` + `config.example.yaml`. Tests: valid load, missing env var, missing file, resolution order. **[done]**
3. **LLM adapter, Anthropic only** — no tools/memory yet. Mocked unit test (monkeypatch `anthropic.Anthropic().messages.create`) for message/tool-spec translation; one manual smoke test against the real API. **[your turn]**
4. **Bare CLI loop** — adapter wired into `cli.py`, empty tools, no memory. Manual interactive test.
5. **Tool registry** — schema derivation + execute/error paths + shape tests.
6. **Wire tools into Agent** — implement the tool-call loop in `agent.py`; add the gated example tool. Automated test via a scripted `FakeAdapter` (tool_use → end_turn), no network.
7. **Memory store + recall** — frontmatter read/write, index, `search`; wire index into system prompt; add `list_memory`/`read_memory`/`search_memory` tools; wire `/remember`. Tests: write-then-read round trip, index generation, search over sample files.
8. **Polish** — clean error surfacing in the CLI, logging, README.
9. **End-to-end verification** (below) + final `pytest` / `ruff check` / `ruff format --check` pass.

## Verification

**Manual CLI session:**
```
$ export ANTHROPIC_API_KEY=sk-...
$ jarvis
you> /remember I'm doing a 12-week Spanish study plan, currently on week 3
jarvis> Noted.
you> what am I working on right now?
jarvis> [agent uses recall/search_memory to find the note, answers correctly]
you> /exit
```
Confirm `data/memory/users/default/facts.md` contains the note and `index.md` reflects it.

**Automated tests (pytest):** config resolution/validation; tool schema derivation + execute/error paths; memory read/write/index/search round trips; mocked Anthropic adapter request/response shape (system separate from messages, tool_result paired with tool_use ids, both text-only and tool_use response cases); `FakeAdapter`-driven agent loop test with zero network calls.

**Acceptance gate:** `pytest` and `ruff check . && ruff format --check .` both clean.

## Future step: conversation history management (post–Milestone 1)

Not in scope for Milestone 1 — `self.history` in `agent.py` can grow unbounded for now. Revisit once the core loop (Steps 3–6) is working end to end; don't let this block finishing `chat()`.

**Decision (from discussion):** lean on Anthropic's native **compaction** feature rather than hand-rolling summarization or a trim-by-count policy ourselves.

- Beta feature, header `compact-2026-01-12`. Available on Claude Fable 5, Opus 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 5, Sonnet 4.6.
- Past a token threshold, Anthropic automatically summarizes older conversation content server-side and returns a `compaction` content block in the response.
- Hard requirement: the *full* `response.content` (not just the extracted text) must be appended back into history on the next request — the compaction block has to survive being stored and resent verbatim, or the mechanism breaks.

**Open design question to resolve when we get here (deliberately not decided now):** this doesn't fit cleanly into the "`chat()` is a pure stateless translator" model established in Milestone 1, because the compaction block is opaque, Anthropic-specific state that needs to round-trip through our own `ChatMessage` history untouched. Two directions to weigh at that point, not now:
  - (a) give `ChatMessage`/`LLMResponse` an opaque passthrough field the adapter fills in and later reads back, without `agent.py` needing to know what's inside it, or
  - (b) let the adapter keep its own internal copy of history in native format, with our neutral `list[ChatMessage]` as an external-facing view rather than the source of truth.

  Either way, this is a provider-specific mechanism — a future OpenAI/other adapter without an equivalent feature would need its own strategy (e.g. plain trim-by-count), which is fine: `agent.py` shouldn't have to know or care which approach a given adapter uses, only that history stays within bounds.

## Critical files
- `pyproject.toml`
- `src/jarvis/llm/base.py`, `src/jarvis/llm/anthropic_adapter.py`
- `src/jarvis/agent.py`
- `src/jarvis/tools/registry.py`
- `src/jarvis/memory/store.py`
- `config/config.example.yaml`
