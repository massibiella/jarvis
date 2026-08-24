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
  private freqData: Uint8Array<ArrayBuffer> | null = null;
  private currentSource: AudioBufferSourceNode | null = null;

  private ensureContext(): { ctx: AudioContext; analyser: AnalyserNode } {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.75;
      this.freqData = new Uint8Array(new ArrayBuffer(this.analyser.frequencyBinCount));
      this.startKeepAlive(this.ctx);
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return { ctx: this.ctx, analyser: this.analyser! };
  }

  /**
   * Keeps the OS/browser audio output stream continuously active with an
   * inaudible tone for the page's lifetime, connected straight to
   * destination (not through the analyser, so it never skews
   * getLevel()/getFrequencyData()).
   *
   * Why: there's often a long silent gap between replies (listening +
   * thinking), and when the output device has been idle, waking it back up
   * to start a new utterance silently drops the first ~100-300ms of audio —
   * this was clipping the first word/character off replies even after
   * switching TTS playback to AudioBufferSourceNode with a fully
   * pre-decoded buffer (verified directly: the WAV Piper returns already
   * has full audio content from ~20ms in, so the loss isn't in the audio
   * data itself or in decoding — it's downstream, at the output
   * device/driver level going from idle to active). A continuously-active
   * signal, even inaudible, keeps that stream warm so it's never idle when
   * a real reply needs to play.
   */
  private startKeepAlive(ctx: AudioContext): void {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    gain.gain.value = 0.00001;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
  }

  private autoResumeArmed = false;

  /**
   * Arms a one-time listener that creates + resumes the AudioContext (and
   * so starts the keep-alive tone above) on the user's very first
   * interaction with the page, instead of waiting for the specific action
   * that needs real audio.
   *
   * Why this matters: for a typed (no mic) conversation, nothing ever
   * touches the AudioContext until speak() calls playBuffer() for the
   * first reply -- so the keep-alive tone starts and the real TTS audio
   * needs to play in the same breath, giving it zero time to actually warm
   * up the output stream (see startKeepAlive() -- a suspended context's
   * oscillator isn't flowing any samples yet either, so merely
   * constructing it earlier doesn't help; it has to actually be resumed).
   * Calling this once on app mount means the very first click/keypress
   * anywhere on the page -- typically several seconds before any reply is
   * ready, given the listening/thinking round trip -- is what resumes the
   * context, so the keep-alive tone has real lead time before it matters.
   */
  armAutoResume(): () => void {
    if (this.autoResumeArmed) return () => {};
    this.autoResumeArmed = true;

    const cleanup = () => {
      window.removeEventListener("pointerdown", onFirstInteraction);
      window.removeEventListener("keydown", onFirstInteraction);
    };
    const onFirstInteraction = () => {
      void this.resume();
      cleanup();
    };

    window.addEventListener("pointerdown", onFirstInteraction);
    window.addEventListener("keydown", onFirstInteraction);
    return cleanup;
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

  /**
   * Decodes raw audio bytes (a Piper WAV response) and plays them through
   * the shared analyser graph, resolving once playback ends.
   *
   * Deliberately NOT an <audio> element piped through
   * createMediaElementSource(): that combination has a long-documented
   * Chromium bug where the first render quantum(s) of a *new* source are
   * silently dropped, independent of whether the element has already fired
   * "canplay" — for a short reply, that dropped chunk can be the entire
   * audible clip. decodeAudioData() fully decodes the WAV into memory
   * first, so start() below has nothing left to race: the whole buffer is
   * already sample data before playback begins.
   */
  async playBuffer(data: ArrayBuffer): Promise<void> {
    const { ctx, analyser } = this.ensureContext();
    await this.resume();

    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await ctx.decodeAudioData(data);
    } catch {
      throw new Error("Audio playback failed");
    }

    // Guards against overlapping playback if a caller somehow starts a
    // second reply before the first finishes (App.tsx normally serializes
    // this via busyRef, but this keeps the audio graph consistent either way).
    this.currentSource?.stop();

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(analyser);
    source.connect(ctx.destination);
    this.currentSource = source;

    return new Promise((resolve) => {
      source.onended = () => {
        if (this.currentSource === source) this.currentSource = null;
        resolve();
      };
      source.start();
    });
  }

  /**
   * User-requested interrupt: stops whatever TTS reply is currently
   * playing, if any. Calling .stop() on an AudioBufferSourceNode still
   * fires its 'ended' event, so playBuffer()'s pending promise resolves
   * normally through the same onended handler it already has -- callers
   * awaiting speak() just see it finish early, not hang or reject.
   * Safe to call with nothing playing (no-op).
   */
  stopSpeaking(): void {
    this.currentSource?.stop();
    this.currentSource = null;
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
