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

Weather is a built-in native tool, no setup needed. For tools that live in a separate MCP server (e.g. Google Calendar via [`nspady/google-calendar-mcp`](https://github.com/nspady/google-calendar-mcp), run via `npx`) — Jarvis launches them as a local subprocess, it doesn't fetch them, so the server itself must be runnable on this machine first (a local clone for a Python server, or Node/npm installed for an npm-distributed one like the calendar server).

Then add it to `config.yaml`'s `mcp_servers` section — see `config/config.example.yaml` for the format, and `docs/PLAN.md`'s "MCP integrations" section for the calendar server's specific Google Cloud Console setup steps.

For the calendar server specifically, you also need to authenticate once before first use — run `npx @cocal/google-calendar-mcp auth`, it opens a browser link to sign in and grant access, and caches the resulting token locally. `jarvis` itself won't prompt for this; if calendar tools fail with an auth error, this is the step to (re-)run.

## Development

```bash
pytest
ruff check .
ruff format --check .
```



# Jarvis — Front-End HUD (v1 prototype)

First pass at the JARVIS-style interface described in [PRD.md](PRD.md) §4.5
and §4.12. This branch is scoped to the front-end and voice pipeline only —
there is no agent/reasoning backend wired in yet (see `frontend/src/lib/backend.ts`).

## What's here

- **`frontend/`** — React + TypeScript + Vite app. Full-screen dark HUD with
  a canvas-based, audio-reactive "orb" at its center that visualizes the
  assistant's state (idle / listening / thinking / speaking) as a glowing
  circular waveform. Voice input via the browser's Speech Recognition API,
  with a text input as a fully-functional fallback. See
  `frontend/README.md` for how it works internally (file layout,
  data flow, the audio pipeline).
- **`voice-server/`** — minimal local HTTP server wrapping
  [Piper](https://github.com/OHF-Voice/piper1-gpl), an open-source, fully
  offline neural TTS engine, so Jarvis has an actual voice. See
  `voice-server/README.md` for setup.

## Running it

```sh
# Terminal 1 — voice server
cd voice-server
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt
# download the voice model — see voice-server/README.md
./.venv/Scripts/python server.py

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open the printed local URL. Click **Speak** (Chrome/Edge required for voice
input) or type into the text field — either path goes through the same
stub-response → Piper TTS → orb-reacts-to-audio loop.

## Tests

```sh
# frontend — Vitest + React Testing Library
cd frontend
npm run test

# voice server — pytest, no model download needed (piper is mocked)
cd voice-server
./.venv/Scripts/python -m pytest
```

## Known gaps (expected at this stage)

- No real reasoning/agent backend — responses are canned placeholders.
- No auth/multi-user support yet (PRD §4.6).
- STT uses the browser's built-in Speech Recognition API, which is
  convenient for a v1 demo but not itself open-source/local; a Whisper-based
  swap is the likely upgrade path if a fully local STT+TTS pipeline is
  wanted later.
# Jarvis — Front-End HUD (v1 prototype)

First pass at the JARVIS-style interface described in [PRD.md](PRD.md) §4.5
and §4.12. This branch is scoped to the front-end and voice pipeline only —
there is no agent/reasoning backend wired in yet (see `frontend/src/lib/stubAssistant.ts`).

## What's here

- **`frontend/`** — React + TypeScript + Vite app. Full-screen dark HUD with
  a canvas-based, audio-reactive "orb" at its center that visualizes the
  assistant's state (idle / listening / thinking / speaking) as a glowing
  circular waveform. Voice input via the browser's Speech Recognition API,
  with a text input as a fully-functional fallback.
- **`voice-server/`** — minimal local HTTP server wrapping
  [Piper](https://github.com/OHF-Voice/piper1-gpl), an open-source, fully
  offline neural TTS engine, so Jarvis has an actual voice. See
  `voice-server/README.md` for setup.

## Running it

```sh
# Terminal 1 — voice server
cd voice-server
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt
# download the voice model — see voice-server/README.md
./.venv/Scripts/python server.py

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open the printed local URL. Click **Speak** (Chrome/Edge required for voice
input) or type into the text field — either path goes through the same
stub-response → Piper TTS → orb-reacts-to-audio loop.

## Known gaps (expected at this stage)

- No real reasoning/agent backend — responses are canned placeholders.
- No auth/multi-user support yet (PRD §4.6).
- STT uses the browser's built-in Speech Recognition API, which is
  convenient for a v1 demo but not itself open-source/local; a Whisper-based
  swap is the likely upgrade path if a fully local STT+TTS pipeline is
  wanted later.
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

Weather is a built-in native tool, no setup needed. For tools that live in a separate MCP server (e.g. Google Calendar via [`nspady/google-calendar-mcp`](https://github.com/nspady/google-calendar-mcp), run via `npx`) — Jarvis launches them as a local subprocess, it doesn't fetch them, so the server itself must be runnable on this machine first (a local clone for a Python server, or Node/npm installed for an npm-distributed one like the calendar server).

Then add it to `config.yaml`'s `mcp_servers` section — see `config/config.example.yaml` for the format, and `docs/PLAN.md`'s "MCP integrations" section for the calendar server's specific Google Cloud Console setup steps.

For the calendar server specifically, you also need to authenticate once before first use — run `npx @cocal/google-calendar-mcp auth`, it opens a browser link to sign in and grant access, and caches the resulting token locally. `jarvis` itself won't prompt for this; if calendar tools fail with an auth error, this is the step to (re-)run.

Some MCP servers are remote instead of local — configured with `url` instead of `command` (e.g. IBKR's official hosted connector). No local process needed for these; `jarvis` itself opens a browser for you to authorize on first connect, and caches the resulting token under `~/.jarvis/mcp_oauth/`. Nothing to run manually first, unlike the calendar server above.

## Development

```bash
pytest
ruff check .
ruff format --check .
```
