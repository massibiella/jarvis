# Jarvis Frontend

React + TypeScript + Vite app implementing the JARVIS-style HUD described in
[`../PRD.md`](../PRD.md) §4.5 and §4.12. Full-screen dark interface with a
canvas-based, audio-reactive "orb" that visualizes assistant state
(idle / listening / thinking / speaking), voice input via the browser's
Speech Recognition API, and a text input as a fully-functional fallback.

Talks to the real Jarvis agent backend (`../src/jarvis/`) over HTTP — see
[`src/lib/backend.ts`](src/lib/backend.ts)'s `getAgentResponse()`. This
document covers the frontend's internals: folder structure, what each file
does and why it's there, data flow, and known quirks/tradeoffs.

## Running it

```sh
npm install
npm run dev
```

The app expects the Jarvis agent backend (`jarvis`, see the root
[`README.md`](../README.md)) for chat, and a local Piper TTS server for
voice output — see [`../voice-server/README.md`](../voice-server/README.md).
Without the agent backend, sending a message shows an error instead of a
reply; without the voice server, replies still render as text but
`speak()` calls will fail.

## Testing

```sh
npm run test    # Vitest + React Testing Library
npm run lint     # oxlint
npm run build    # tsc typecheck + production build
```

## Folder structure

```
frontend/
├── README.md              this file
├── index.html              HTML shell — loads src/main.tsx as a module
├── package.json             dependencies + npm scripts (dev/build/lint/test)
├── package-lock.json         locked dependency versions, keep in sync with package.json
├── .env.example               documents VITE_TTS_ENDPOINT for local setup
├── .gitignore                 excludes node_modules/, dist/, editor cruft
├── package/                 tool config, kept out of the frontend/ root
│   ├── tsconfig.json           TypeScript compiler config; every npm script
│   │                           that runs tsc/oxlint points at this file with
│   │                           -p/--tsconfig, since neither tool auto-finds
│   │                           a tsconfig outside the directory it's run from
│   ├── vite.config.ts           Vite bundler + Vitest test-runner config,
│   │                            loaded explicitly via --config in every
│   │                            vite/vitest npm script
│   └── .oxlintrc.json           lint rules, loaded via oxlint's -c flag
├── public/
│   └── favicon.ico             browser tab icon, referenced by index.html
├── src/                      application source
│   ├── main.tsx                entry point — mounts <App /> into #root
│   ├── App.tsx                  state machine + layout; the only file that
│   │                            ties voice/text input, backend calls, and
│   │                            the two views (assistant/neural-map) together
│   ├── App.css                   all styles, sectioned by HUD region
│   ├── types.ts                   shared types (AssistantState, MindMapNode)
│   │                              kept separate so components/ don't import
│   │                              from each other or from App.tsx
│   ├── components/                presentational canvas views
│   │   ├── Orb.tsx                  audio-reactive circular waveform —
│   │   │                            visualizes AssistantState (Jarvis only,
│   │   │                            not the user's mic — see MicLevelBar)
│   │   ├── MicLevelBar.tsx           header meter for the USER's mic input,
│   │   │                            kept separate from the Orb
│   │   └── MindMap.tsx               radial tree — visualizes the
│   │                                 (placeholder) memory graph
│   └── lib/                       non-visual logic / external calls
│       ├── voice.ts                 audio IN: mic capture/analysis
│       │                            (AudioEngine) + browser speech-to-text
│       │                            (useSpeechRecognition)
│       ├── backend.ts                calls OUT: Piper TTS request (speak)
│       │                            + the Jarvis agent backend's /chat
│       │                            request (getAgentResponse)
│       └── greeting.ts               pure time-of-day greeting text
│                                     (getGreeting) — App.tsx speaks it via
│                                     speak() once on mount
└── tests/                    unit tests, mirrors src/ 1:1 so each test's
    │                          home file is easy to find
    ├── testSetup.ts              runs once before every test file — wires
    │                             jest-dom matchers into vitest's `expect`
    │                             and calls cleanup() after each test
    ├── App.test.tsx               tests src/App.tsx
    ├── components/
    │   ├── Orb.test.tsx             tests src/components/Orb.tsx
    │   ├── MicLevelBar.test.tsx      tests src/components/MicLevelBar.tsx
    │   └── MindMap.test.tsx          tests src/components/MindMap.tsx
    └── lib/
        ├── voice.test.ts             tests src/lib/voice.ts
        ├── backend.test.ts            tests src/lib/backend.ts
        └── greeting.test.ts            tests src/lib/greeting.ts
```

**Why `package.json`/`package-lock.json` stay at `frontend/` root, unlike
the other config files:** npm requires `package.json` to live in the
directory you run `npm install`/`npm run <script>` from, and it installs
`node_modules` as that file's sibling. Node/Vite's module resolution then
walks *up* from each importing file (e.g. `src/App.tsx`) looking for a
`node_modules` — which only works if `node_modules` is at `frontend/` or
above. Moving `package.json` into `package/` would move `node_modules`
there too and break every import in `src/`. `tsconfig.json`,
`vite.config.ts`, and `.oxlintrc.json` don't have this constraint — tsc,
Vite, and oxlint all accept an explicit config path, so every npm script in
`package.json` passes one (`-p package/tsconfig.json`,
`--config package/vite.config.ts`, `-c package/.oxlintrc.json`). Because npm
always runs scripts with `cwd` set to the directory containing
`package.json` (i.e. `frontend/`), Vite's `root` (which defaults to `cwd`)
still resolves correctly even though `vite.config.ts` itself now lives one
level down — see the comment at the top of `package/vite.config.ts`.
`index.html` is Vite's actual entry point (it references `src/main.tsx`
directly) and must stay at the Vite root; `public/` is Vite's convention for
static assets served as-is, also root-relative.

## Data flow

`App.tsx` holds one state machine: `AssistantState` = `idle → listening →
thinking → speaking → idle`. Everything else reacts to that state rather
than owning its own:

0. On mount, before any user input: after a `GREETING_DELAY_MS` (2s) pause —
   so it doesn't fire the instant the HUD paints in — `App.tsx` calls
   `getGreeting()` (`lib/greeting.ts`) for a "Good morning/afternoon/evening,
   Sir." line based on the system clock, sets state → `speaking`, and passes
   it to `speak()` — same TTS path as every other reply, so the Orb reacts to
   it the same way. A ref (not just the effect's empty dep array) guards the
   effect itself so React StrictMode's dev-mode double-invoke doesn't
   schedule the greeting twice.
1. User speaks (mic, via `useSpeechRecognition`) or types → `respond()` in
   `App.tsx` fires.
2. State → `thinking`, text goes to `getAgentResponse()` (`lib/backend.ts`),
   which POSTs to the Jarvis agent backend's `/chat` endpoint
   (`../src/jarvis/server.py`) — the real tool-calling loop, not a stub.
3. Reply comes back, state → `speaking`, reply goes to `speak()`, which runs
   it through `sanitizeForSpeech()` (`lib/backend.ts` — strips markdown/
   symbols, expands `°`/`°C`/`°F`, keeps sentence-ending punctuation so the
   voice server can pace multi-sentence replies) and POSTs the result to the
   voice-server, then plays the returned WAV.
4. `Orb` reads `AssistantState` as a prop and re-renders its `<canvas>`
   accordingly — see below.
5. State → `idle` once playback ends (or the request fails, or speech
   recognition ends on its own without going through the mic button).

## The Orb's audio reactivity

`Orb.tsx` doesn't get audio data through React props or state — that would
re-render the component every animation frame. Instead, `lib/voice.ts`
exports a singleton `audioEngine` wrapping one shared `AudioContext` +
`AnalyserNode`. The Orb's own `requestAnimationFrame` loop reads
`audioEngine.getFrequencyData()` / `getLevel()` directly on every frame — no
state hookup, no extra re-renders. Only `speaking` is audio-reactive — the
mic (`listening`) intentionally isn't wired into the Orb at all; the Orb
visualizes Jarvis, not the person talking to it. The user's mic level gets
its own indicator instead — see `components/MicLevelBar.tsx`, driven by the
same `audioEngine`.

For `idle`, `listening`, and `thinking`, there's no real audio source, so the
waveform motion is synthetic (a calm sine-wave breathing effect vs. a faster
rotating sweep) rather than driven by the analyser.

TTS playback (`speak()` in `lib/backend.ts`) hands the fetched WAV bytes to
`audioEngine.playBuffer()`, which decodes them via `AudioContext.decodeAudioData()`
into an in-memory `AudioBuffer` and plays them with an `AudioBufferSourceNode`
connected to the same analyser + `ctx.destination`. This is deliberately
*not* an `<audio>` element piped through `createMediaElementSource()`: that
combination has a long-documented Chromium bug where the first render
quantum(s) of a *new* source are silently dropped, independent of whether
the element has already fired `"canplay"` — for a short reply, the dropped
chunk can be the entire audible clip (this is what used to clip "Good" off
the launch greeting, and later clipped leading words/digits off ordinary
replies too, even well after the `AudioContext` had been running for a
while). `AudioBufferSourceNode` avoids that specific bug: the buffer is
fully decoded in memory before `start()` is ever called, so there's no
decoder to race.

That alone wasn't the whole story, though — replies kept clipping their
first word/character even with `AudioBufferSourceNode` in place. Probing
the voice server directly (fetching a WAV and checking its PCM envelope)
showed the audio data itself has full content from ~20ms in — nothing is
missing at the source. The remaining loss is downstream, at the OS/browser
audio output level: there's often a long silent gap between replies
(listening + thinking), and waking the output stream back up from idle to
start a new utterance drops its first ~100-300ms, independent of which
WebAudio node feeds it. `AudioEngine`'s constructor works around this by
starting a continuous, effectively inaudible oscillator (`startKeepAlive()`
in `lib/voice.ts`, gain `0.00001`, wired straight to `ctx.destination` — not
through the analyser, so it never skews the Orb's readings) the moment the
`AudioContext` is created, so the output stream is never idle by the time a
real reply needs to play. `playBuffer()` also awaits `AudioContext.resume()`
first (a fresh context starts `"suspended"` until a user gesture unlocks
it).

## Known quirks / tradeoffs

- **The launch greeting can still be blocked entirely by browser autoplay
  policy**, separately from the decode/resume handling above. `speak()`
  plays audio with no prior user interaction, and Chromium-based browsers
  may silently refuse to produce audible output from an `AudioContext` on a
  page the user hasn't interacted with yet (autoplay restrictions loosen
  after the site builds up enough Media Engagement, e.g. from repeated
  visits during development). If the greeting doesn't play at all, that's
  why — it's a browser policy, not a bug in `speak()`/`greeting.ts`, and it
  self-resolves after the first click/keypress on the page in that browser
  session.
- **Speech-to-text is browser-native** (`SpeechRecognition` /
  `webkitSpeechRecognition`), not local/open-source. It's the fastest path
  to a working demo, but it's the first thing to swap for local Whisper if
  a fully offline pipeline matters later. `isSupported` in
  `useSpeechRecognition` is `false` on any non-Chromium browser — the mic
  button disables itself and the text field becomes the only input path.
- **No streaming.** `getAgentResponse()` awaits the full reply before
  returning — the HUD sits in `thinking` for the whole round trip, since
  neither `Agent.step()` nor the LLM adapters stream tokens yet.
- **Canvas components (`Orb`, `MindMap`) no-op under jsdom** — `getContext`
  returns `null` in the test environment, and both components already
  handle that by skipping their draw loop entirely. That's why their tests
  are light smoke tests (renders, doesn't crash) rather than pixel checks.
