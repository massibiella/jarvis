import { audioEngine } from "./audioEngine";

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

/**
 * Sends text to the local Piper TTS server and plays back the synthesized
 * speech, routed through the shared audio graph so the Orb can visualize it.
 */
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
    void audioEl.play();
  });
}
