// The two things the frontend calls out to:
//   - speak()           -> POSTs to the local Piper TTS server (voice-server/).
//   - getAgentResponse() -> POSTs to the Jarvis agent backend (src/jarvis/server.py),
//                            which runs the real tool-calling loop (Agent.step()).

import { audioEngine } from "./voice";

// ---------------------------------------------------------------------------
// Text-to-speech: sends text to the local Piper voice server (see
// voice-server/) and plays back the synthesized speech, routed through the
// shared audio graph so the Orb can visualize it.
// ---------------------------------------------------------------------------
const TTS_ENDPOINT = import.meta.env.VITE_TTS_ENDPOINT ?? "http://localhost:8765/speak";

// LLM replies routinely carry markdown (**bold**, # headers, (asides),
// bullet dashes, `code`) that Piper would otherwise read aloud literally
// (e.g. saying "asterisk asterisk" instead of just the word). Strip every
// character down to words, numbers, whitespace, and sentence-ending
// punctuation, with two exceptions:
//   - a "-" immediately before a digit is a negative sign, not a symbol, so
//     it's swapped for an ASCII token that survives the symbol sweep below,
//     then restored afterward -- otherwise "-5" would silently become "5",
//     flipping its meaning.
//   - "." / "!" / "?" are kept as sentence terminators (not stripped like
//     other punctuation) so the voice server can still tell where one
//     sentence ends and the next begins, and insert a pause there -- see
//     voice-server/server.py. This also means a decimal point like "26.7"
//     survives intact instead of splitting into "26 7".
const NEG_TOKEN = "NEGSIGN";

export function sanitizeForSpeech(text: string): string {
  return text
    .split(/-(?=\d)/).join(NEG_TOKEN)
    // "°" alone isn't spoken as anything -- and "°C"/"°F" specifically
    // should read as the actual unit name, not the bare letter.
    .replace(/°\s*([CF])\b/gi, (_match, letter: string) =>
      letter.toUpperCase() === "C" ? " degrees Celsius " : " degrees Fahrenheit "
    )
    .split("°").join(" degrees ")
    .replace(/[^A-Za-z0-9\s.!?]/g, " ")
    .split(NEG_TOKEN).join("-")
    .replace(/\s+/g, " ")
    .replace(/\s+([.!?])/g, "$1")
    .trim();
}

export async function speak(text: string, signal?: AbortSignal): Promise<void> {
  const res = await fetch(TTS_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: sanitizeForSpeech(text) }),
    signal,
  });
  if (!res.ok) {
    throw new Error(`TTS server error: ${res.status} ${res.statusText}`);
  }
  const data = await res.arrayBuffer();
  // playBuffer() (lib/voice.ts) decodes and plays this through the shared
  // WebAudio graph via AudioBufferSourceNode -- not an <audio> element, which
  // has a long-documented Chromium bug that silently drops the first render
  // quantum(s) of a new source, clipping the start of short replies.
  await audioEngine.playBuffer(data);
}

// ---------------------------------------------------------------------------
// Agent chat: sends user text to the Jarvis backend's /chat endpoint and
// returns its reply. The backend owns the actual reasoning/tool-calling loop
// (see src/jarvis/agent.py) -- this is just the HTTP seam.
// ---------------------------------------------------------------------------
const CHAT_ENDPOINT = import.meta.env.VITE_AGENT_ENDPOINT ?? "http://localhost:8000/chat";

export async function getAgentResponse(userText: string): Promise<string> {
  const res = await fetch(CHAT_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: userText }),
  });
  if (!res.ok) {
    throw new Error(`Agent server error: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as { reply: string };
  return data.reply;
}

// ---------------------------------------------------------------------------
// Check-in: polls the Jarvis agent backend's /checkin endpoint (see
// src/jarvis/checkin.py) once on launch. Returns null when no morning/evening
// check-in is due right now (outside the configured window, already run
// today, or check-ins aren't enabled) -- App.tsx falls back to the static
// time-of-day greeting in that case.
// ---------------------------------------------------------------------------
const CHECKIN_ENDPOINT = import.meta.env.VITE_CHECKIN_ENDPOINT ?? "http://localhost:8000/checkin";

export async function getCheckin(): Promise<string | null> {
  const res = await fetch(CHECKIN_ENDPOINT);
  if (!res.ok) {
    throw new Error(`Checkin server error: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as { reply: string | null };
  return data.reply;
}
