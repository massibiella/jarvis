# Jarvis Frontend

React + TypeScript + Vite app implementing the JARVIS-style HUD described in
[`../PRD.md`](../PRD.md) §4.5 and §4.12. Full-screen dark interface with a
canvas-based, audio-reactive "orb" that visualizes assistant state
(idle / listening / thinking / speaking), voice input via the browser's
Speech Recognition API, and a text input as a fully-functional fallback.

There is no agent/reasoning backend wired in yet — see
[`src/lib/backend.ts`](src/lib/backend.ts). This document covers the
frontend's internals: folder structure, what each file does and why it's
there, data flow, and known quirks/tradeoffs.

## Running it

```sh
npm install
npm run dev
```

The app expects a local Piper TTS server for voice output — see
[`../voice-server/README.md`](../voice-server/README.md). Without it, text
input still works but `speak()` calls will fail.

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
│   └── favicon.svg            browser tab icon, referenced by index.html
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
│   │   │                            visualizes AssistantState
│   │   └── MindMap.tsx               radial tree — visualizes the
│   │                                 (placeholder) memory graph
│   └── lib/                       non-visual logic / external calls
│       ├── voice.ts                 audio IN: mic capture/analysis
│       │                            (AudioEngine) + browser speech-to-text
│       │                            (useSpeechRecognition)
│       └── backend.ts                calls OUT: Piper TTS request (speak)
│                                     + the placeholder "reasoning" response
│                                     (getStubResponse)
└── tests/                    unit tests, mirrors src/ 1:1 so each test's
    │                          home file is easy to find
    ├── testSetup.ts              runs once before every test file — wires
    │                             jest-dom matchers into vitest's `expect`
    │                             and calls cleanup() after each test
    ├── App.test.tsx               tests src/App.tsx
    ├── components/
    │   ├── Orb.test.tsx             tests src/components/Orb.tsx
    │   └── MindMap.test.tsx          tests src/components/MindMap.tsx
    └── lib/
        ├── voice.test.ts             tests src/lib/voice.ts
        └── backend.test.ts            tests src/lib/backend.ts
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

1. User speaks (mic, via `useSpeechRecognition`) or types → `respond()` in
   `App.tsx` fires.
2. State → `thinking`, text goes to `getStubResponse()` (`lib/backend.ts`).
3. Reply comes back, state → `speaking`, reply goes to `speak()`, which
   POSTs to the voice-server and plays the returned WAV.
4. `Orb` reads `AssistantState` as a prop and re-renders its `<canvas>`
   accordingly — see below.
5. State → `idle` once playback ends (or the request fails, or speech
   recognition ends on its own without going through the mic button).

## The Orb's audio reactivity

`Orb.tsx` doesn't get audio data through React props or state — that would
re-render the component every animation frame. Instead, `lib/voice.ts`
exports a singleton `audioEngine` wrapping one shared `AudioContext` +
`AnalyserNode`. Both the mic (during `listening`) and the TTS `<audio>`
element (during `speaking`) connect to that same analyser. The Orb's own
`requestAnimationFrame` loop reads `audioEngine.getFrequencyData()` /
`getLevel()` directly on every frame — no state hookup, no extra re-renders.

For `idle` and `thinking`, there's no real audio source, so the waveform
motion is synthetic (a calm sine-wave breathing effect vs. a faster rotating
sweep) rather than driven by the analyser.

## Known quirks / tradeoffs

- **Speech-to-text is browser-native** (`SpeechRecognition` /
  `webkitSpeechRecognition`), not local/open-source. It's the fastest path
  to a working demo, but it's the first thing to swap for local Whisper if
  a fully offline pipeline matters later. `isSupported` in
  `useSpeechRecognition` is `false` on any non-Chromium browser — the mic
  button disables itself and the text field becomes the only input path.
- **`getStubResponse()` is a placeholder**, not a real design to extend —
  it exists purely to close the voice/orb loop before an actual agent
  backend is wired in (see root [`../README.md`](../README.md)'s "Known
  gaps"). Once that backend exists, this function gets deleted, not grown.
- **Canvas components (`Orb`, `MindMap`) no-op under jsdom** — `getContext`
  returns `null` in the test environment, and both components already
  handle that by skipping their draw loop entirely. That's why their tests
  are light smoke tests (renders, doesn't crash) rather than pixel checks.
