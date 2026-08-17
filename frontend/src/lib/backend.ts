// The two things the frontend calls out to. Both are placeholders for a
// real agent backend (PRD §4.12/§6) that doesn't exist yet:
//   - speak()           -> real network call, to the local Piper TTS server.
//   - getStubResponse() -> fake, in-browser "reasoning" until an actual
//                           agent core exists to replace it wholesale.

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
// Stub "reasoning" response: closes the voice/orb loop end-to-end for demos
// before a real agent backend exists. Not designed to be extended — replace
// wholesale once that backend is wired in.
// ---------------------------------------------------------------------------
export async function getStubResponse(userText: string): Promise<string> {
  await new Promise((resolve) => setTimeout(resolve, 500));

  const text = userText.toLowerCase();
  if (!text.trim()) {
    return "I didn't catch that. Could you say it again?";
  }
  if (text.includes("hello") || text.includes("hi jarvis")) {
    return "Hello. I'm online, though I'm still just a prototype interface for now.";
  }
  if (text.includes("weather")) {
    return "Weather lookups aren't wired up yet — that's coming once the agent core is connected.";
  }
  if (text.includes("who are you") || text.includes("what are you")) {
    return "I'm Jarvis, a work in progress. Right now I'm only a front-end and voice demo.";
  }
  return `You said: "${userText}". I heard you, but I'm not connected to a reasoning engine yet.`;
}
