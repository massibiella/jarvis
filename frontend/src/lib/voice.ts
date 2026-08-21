// Everything related to getting audio INTO the app: microphone capture,
// live amplitude/frequency analysis (so the Orb can react to it), and
// browser speech-to-text. TTS/playback lives in backend.ts instead, since
// that's audio coming FROM the (future) assistant, not user input.

// ---------------------------------------------------------------------------
// Audio graph: shared AudioContext/AnalyserNode used by both mic input and
// TTS playback, so the Orb's requestAnimationFrame loop can read live
// amplitude/frequency data directly (not routed through React state, which
// would repaint the component tree every frame).
// ---------------------------------------------------------------------------
class AudioEngine {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private micStream: MediaStream | null = null;
  private elementSource: MediaElementAudioSourceNode | null = null;
  private freqData: Uint8Array<ArrayBuffer> | null = null;

  private ensureContext(): { ctx: AudioContext; analyser: AnalyserNode } {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.75;
      this.freqData = new Uint8Array(new ArrayBuffer(this.analyser.frequencyBinCount));
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return { ctx: this.ctx, analyser: this.analyser! };
  }

  async connectMic(): Promise<void> {
    const { ctx, analyser } = this.ensureContext();
    if (this.micSource) return;
    this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.micSource = ctx.createMediaStreamSource(this.micStream);
    this.micSource.connect(analyser);
  }

  disconnectMic(): void {
    this.micSource?.disconnect();
    this.micSource = null;
    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = null;
  }

  /**
   * Ensures the underlying AudioContext exists and has actually finished
   * resuming (not just asked to). Browsers start a new AudioContext
   * "suspended" until a user gesture unlocks it; ensureContext() kicks that
   * off but doesn't wait for it, so playing audio right after connecting it
   * can start pushing samples through the graph before it's running,
   * silently dropping the first fraction of a second. Callers that are
   * about to play audio (not just visualize it) should await this first.
   */
  async resume(): Promise<void> {
    const { ctx } = this.ensureContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
  }

  connectElement(el: HTMLAudioElement): void {
    const { ctx, analyser } = this.ensureContext();
    if (this.elementSource) {
      this.elementSource.disconnect();
    }
    this.elementSource = ctx.createMediaElementSource(el);
    this.elementSource.connect(analyser);
    this.elementSource.connect(ctx.destination);
  }

  /** Snapshot of frequency-bin amplitudes (0-255), or null if no audio graph exists yet. */
  getFrequencyData(): Uint8Array | null {
    if (!this.analyser || !this.freqData) return null;
    this.analyser.getByteFrequencyData(this.freqData);
    return this.freqData;
  }

  /** Average amplitude across all bins, normalized to 0-1. */
  getLevel(): number {
    const data = this.getFrequencyData();
    if (!data) return 0;
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    return sum / data.length / 255;
  }
}

export const audioEngine = new AudioEngine();

// ---------------------------------------------------------------------------
// Speech-to-text: wraps the browser's built-in Speech Recognition API
// (webkitSpeechRecognition/SpeechRecognition — Chromium only). TypeScript's
// DOM lib doesn't ship types for it, so it's typed minimally below.
//
// Known tradeoff: convenient (zero setup, built into Chrome/Edge) but not
// itself open-source/local — it depends on the browser vendor's backend.
// First candidate to swap for a local Whisper-based STT if that matters
// more than v1 convenience.
// ---------------------------------------------------------------------------
import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

// Errors where the mic session is unrecoverable and shouldn't be auto-restarted.
const FATAL_SPEECH_ERRORS = new Set(["not-allowed", "service-not-allowed", "audio-capture"]);

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useSpeechRecognition() {
  const [isSupported] = useState(() => getSpeechRecognitionCtor() !== null);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  // Whether the user still wants the mic on — distinct from isListening,
  // which tracks the browser engine's own (unreliable) run state.
  const shouldListenRef = useRef(false);

  useEffect(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let finalChunk = "";
      let interimChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) finalChunk += result[0].transcript;
        else interimChunk += result[0].transcript;
      }
      if (finalChunk) {
        setTranscript((prev) => (prev ? `${prev} ${finalChunk}` : finalChunk).trim());
        onFinalRef.current?.(finalChunk.trim());
      }
      setInterimTranscript(interimChunk);
    };

    recognition.onerror = (event) => {
      if (FATAL_SPEECH_ERRORS.has(event.error)) {
        shouldListenRef.current = false;
        setIsListening(false);
      }
      // Transient errors (no-speech, network, aborted) are followed by
      // onend, which restarts the session below if still wanted.
    };

    // Chrome/Edge auto-stop "continuous" recognition on its own (silence
    // timeout, transient errors) — restart transparently rather than
    // treating every onend as the user having stopped.
    recognition.onend = () => {
      if (shouldListenRef.current) {
        try {
          recognition.start();
          return;
        } catch {
          // Engine refused to restart (e.g. rapid stop/start) — fall through.
        }
      }
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    return () => {
      shouldListenRef.current = false;
      recognition.stop();
      recognitionRef.current = null;
    };
  }, []);

  const start = useCallback((onFinal?: (text: string) => void) => {
    if (!recognitionRef.current) return;
    onFinalRef.current = onFinal ?? null;
    setTranscript("");
    setInterimTranscript("");
    shouldListenRef.current = true;
    recognitionRef.current.start();
    setIsListening(true);
  }, []);

  const stop = useCallback(() => {
    shouldListenRef.current = false;
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  return { isSupported, isListening, transcript, interimTranscript, start, stop };
}
