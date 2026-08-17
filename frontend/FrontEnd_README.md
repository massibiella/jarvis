# Frontend — how it works

Developer-facing notes on the frontend's internals: file layout, data flow,
and the reasoning behind the non-obvious parts. For setup/run/test commands,
see the root [README.md](../README.md) — this file doesn't repeat those.

## File layout

```
src/
  main.tsx              entry point — mounts <App /> into #root
  App.tsx                state machine + layout (the only file that ties
                          voice/text input, the backend calls, and the two
                          views together)
  App.css                all styles, sectioned by HUD region
  types.ts               shared types (AssistantState) + the neural-map
                          placeholder data
  components/
    Orb.tsx               canvas orb — visualizes AssistantState
    MindMap.tsx            canvas radial tree — visualizes the (placeholder)
                            memory graph
  lib/
    voice.ts               audio IN: mic capture/analysis (AudioEngine) +
                            browser speech-to-text (useSpeechRecognition)
    backend.ts              calls OUT: Piper TTS request (speak) + the
                             placeholder "reasoning" response (getStubResponse)
  *.test.ts(x)            colocated next to the file they test
  testSetup.ts            vitest/jest-dom wiring, shared by every test file
```

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
5. State → `idle` once playback ends (or the request fails).

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

## Known frontend-only quirks

- **Speech-to-text is browser-native** (`SpeechRecognition` /
  `webkitSpeechRecognition`), not local/open-source. It's the fastest path
  to a working demo, but it's the first thing to swap for local Whisper if
  a fully offline pipeline matters later. `isSupported` in
  `useSpeechRecognition` is `false` on any non-Chromium browser — the mic
  button disables itself and the text field becomes the only input path.
- **`getStubResponse()` is a placeholder**, not a real design to extend —
  it exists purely to close the voice/orb loop before an actual agent
  backend is wired in (see root `README.md`'s "Known gaps"). Once that
  backend exists, this function gets deleted, not grown.
- **Canvas components (`Orb`, `MindMap`) no-op under jsdom** — `getContext`
  returns `null` in the test environment, and both components already
  handle that by skipping their draw loop entirely. That's why their tests
  are light smoke tests (renders, doesn't crash) rather than pixel checks.
