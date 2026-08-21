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

let sharedAudioEl: HTMLAudioElement | null = null;

function getAudioElement(): HTMLAudioElement {
  if (!sharedAudioEl) {
    sharedAudioEl = new Audio();
    sharedAudioEl.crossOrigin = "anonymous";
    audioEngine.connectElement(sharedAudioEl);
  }
  return sharedAudioEl;
}

export async function speak(text: string): Promise<void> {
  const res = await fetch(TTS_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`TTS server error: ${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audioEl = getAudioElement();
  // Make sure the shared AudioContext is actually running before playback
  // starts — see AudioEngine.resume() for why skipping this clips the start
  // of the audio.
  await audioEngine.resume();

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      audioEl.removeEventListener("ended", onEnded);
      audioEl.removeEventListener("error", onError);
      URL.revokeObjectURL(url);
    };
    const onEnded = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("Audio playback failed"));
    };
    audioEl.addEventListener("ended", onEnded);
    audioEl.addEventListener("error", onError);
    audioEl.src = url;
    audioEl.play().catch(onError);
  });
}

// ---------------------------------------------------------------------------
// Agent chat: sends user text to the Jarvis backend's /chat endpoint and
// returns its reply. The backend owns the actual reasoning/tool-calling loop
// (see src/jarvis/agent.py) — this is just the HTTP seam.
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
