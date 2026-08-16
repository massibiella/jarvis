# Session Log — 2026-08-16

A record of what was decided and built for Jarvis today, kept alongside the
code so the reasoning isn't lost once the conversation that produced it is
gone.

## 1. PRD → formal v1.0

The original 15-bullet PRD (`PRD.md` on `main`) was expanded into a full
v1.0 spec: overview/vision, goals & non-goals, personas, 12 functional
requirement sections (each with scope + acceptance criteria), non-functional
requirements (security, reliability, extensibility, performance,
observability), architecture principles, nice-to-haves, assumptions, and
open questions.

Notable decision made during that pass: **voice interaction is a must-have
for v1**, not a stretch goal — the user corrected this explicitly after the
first draft under-scoped it. The frontend must support full voice in/out,
with text/chat as a fallback, not the other way around.

Commits on `main`:
- `65b75dd` — original PRD (pre-existing)
- `be3cb50` — expand to formal v1.0, voice marked must-have

## 2. Branching model

Created a `frontend-hud` branch + a separate git worktree at
`../jarvis-frontend-hud` so front-end work proceeds independently of
`main` without switching directories back and forth. This is the
established pattern going forward for parallel workstreams: new branch,
new worktree folder, not just a branch switch in the same directory.

## 3. v1 HUD prototype (this branch)

Built and verified the first working version of the front-end described in
PRD §4.5 and §4.12:

- **`frontend/`** — React + TypeScript + Vite. Full-screen dark HUD.
  - `src/components/Orb.tsx` — canvas-based, audio-reactive circular
    waveform ("orb") that visualizes four assistant states: idle
    (calm breathing), listening (mic-amplitude reactive), thinking
    (rotating synthetic sweep, no audio input), speaking (TTS-playback
    reactive). Chosen over WebGL/three.js deliberately — plain Canvas 2D
    + Web Audio API `AnalyserNode` gets the sci-fi glow/wave look without
    the extra dependency weight, and is fast enough at this scale.
  - `src/lib/audioEngine.ts` — singleton `AudioContext`/`AnalyserNode`
    shared by mic input and TTS playback, read directly by the Orb's
    `requestAnimationFrame` loop (not routed through React state, to avoid
    re-rendering the component tree every frame).
  - `src/hooks/useSpeechRecognition.ts` — wraps the browser's Speech
    Recognition API (`webkitSpeechRecognition`/`SpeechRecognition`) for
    voice input. **Known tradeoff:** this is convenient (zero setup, built
    into Chrome/Edge) but not itself open-source/local — it depends on the
    browser vendor's backend. Flagged as the likely first thing to swap for
    a Whisper-based local STT if a fully open pipeline matters more than
    v1 convenience.
  - `src/lib/stubAssistant.ts` — placeholder responder. There is no
    reasoning/agent backend yet (PRD §4.12/§6 core), so this just closes
    the loop end-to-end for demo purposes. Replace wholesale once the
    agent core exists — it's intentionally not designed to be extended.
  - Text input is a fully-functional fallback alongside voice, per PRD
    §4.5's requirement that voice not be the *only* input path.

- **`voice-server/`** — small local Flask server wrapping
  [Piper](https://github.com/OHF-Voice/piper1-gpl) (`piper-tts` PyPI
  package), an open-source, fully offline neural TTS engine. Chosen
  specifically because the user asked for something "readily available and
  open source" to give Jarvis a voice. Voice model: `en_GB-alan-medium`
  (British male, ~63MB, downloaded from the `rhasspy/piper-voices` model
  repo on Hugging Face) — picked for a tone fitting a JARVIS-style
  assistant. Model binaries are gitignored; `voice-server/README.md` has
  the download commands.
  - `POST /speak` takes `{ "text": "..." }`, returns `audio/wav`.
  - This is explicitly a temporary standalone service for the prototype —
    once the real agent core exists, Piper likely gets called directly
    from it rather than over HTTP from the browser.

- **Color scheme:** initial pass used a cyan/light-blue accent. User asked
  to switch it to red — updated both the CSS custom properties
  (`frontend/src/index.css`) and the Orb's idle/listening palette
  (`frontend/src/components/Orb.tsx`) to red tones. Thinking (purple) and
  speaking (amber) states were deliberately left alone since they read as
  distinct-state colors, not part of the "light blue" complaint.

### Verification

No headless browser tool (`chromium-cli`) was available in this
environment, so verification used Playwright directly (`npx playwright
install chromium`, temporary driver script, removed after use — not kept
as a project dependency). Confirmed via screenshot + `console --errors`
equivalent that:
- The HUD renders correctly in all four states.
- The full loop (text input → stub response → Piper synthesizes → orb
  reacts to playback amplitude → returns to idle) works with zero console
  errors.

### Commits on `frontend-hud`

- `dd0e1ea` — v1 HUD prototype (orb, voice input/output, stub responder)
- (color change — see branch history for the follow-up commit hash)

## 4. Known gaps / next steps

- No agent/reasoning backend. This is the biggest missing piece — the
  stub responder exists only to make the voice/orb loop demoable.
- No auth or multi-user support yet (PRD §4.6).
- STT is browser-native, not open-source/local (see tradeoff above).
- LLM-agnostic core (PRD §4.12) hasn't been started — that's a backend
  concern, not part of this branch's scope.
