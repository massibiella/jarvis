import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// audioEngine: fakes the Web Audio API (jsdom has no real AudioContext) and
// re-imports the module fresh in each test so the exported singleton starts
// with a clean slate.
// ---------------------------------------------------------------------------
class FakeAnalyserNode {
  fftSize = 0;
  smoothingTimeConstant = 0;
  frequencyBinCount = 4;
  connect = vi.fn();
  getByteFrequencyData(out: Uint8Array) {
    out.set([100, 150, 200, 250]);
  }
}

class FakeAudioContext {
  state = "running";
  destination = {};
  createAnalyser() {
    return new FakeAnalyserNode();
  }
  createMediaStreamSource() {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }
  createMediaElementSource() {
    return { connect: vi.fn() };
  }
  resume = vi.fn();
}

async function freshVoiceModule() {
  vi.resetModules();
  return import("../../src/lib/voice");
}

describe("audioEngine", () => {
  let stopTrack: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    stopTrack = vi.fn();
    vi.stubGlobal("AudioContext", FakeAudioContext);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (navigator as unknown as { mediaDevices?: unknown }).mediaDevices;
  });

  it("has no signal until a mic or playback element is connected", async () => {
    const { audioEngine } = await freshVoiceModule();
    expect(audioEngine.getFrequencyData()).toBeNull();
    expect(audioEngine.getLevel()).toBe(0);
  });

  it("computes the average amplitude from the analyser after the mic connects", async () => {
    const { audioEngine } = await freshVoiceModule();
    await audioEngine.connectMic();
    expect(Array.from(audioEngine.getFrequencyData()!)).toEqual([100, 150, 200, 250]);
    expect(audioEngine.getLevel()).toBeCloseTo((100 + 150 + 200 + 250) / 4 / 255);
  });

  it("stops the mic's tracks on disconnect", async () => {
    const { audioEngine } = await freshVoiceModule();
    await audioEngine.connectMic();
    audioEngine.disconnectMic();
    expect(stopTrack).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// useSpeechRecognition: fakes the browser's SpeechRecognition constructor.
// ---------------------------------------------------------------------------
class FakeSpeechRecognition extends EventTarget {
  static instances: FakeSpeechRecognition[] = [];
  continuous = false;
  interimResults = false;
  lang = "";
  onresult:
    | ((event: {
        resultIndex: number;
        results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
      }) => void)
    | null = null;
  onerror: (() => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());

  constructor() {
    super();
    FakeSpeechRecognition.instances.push(this);
  }
}

describe("useSpeechRecognition", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    FakeSpeechRecognition.instances = [];
  });

  it("reports unsupported when the browser has no SpeechRecognition constructor", async () => {
    const { useSpeechRecognition } = await freshVoiceModule();
    const { result } = renderHook(() => useSpeechRecognition());
    expect(result.current.isSupported).toBe(false);
  });

  it("tracks listening state and forwards the final transcript", async () => {
    vi.stubGlobal("SpeechRecognition", FakeSpeechRecognition);
    const { useSpeechRecognition } = await freshVoiceModule();
    const { result } = renderHook(() => useSpeechRecognition());
    expect(result.current.isSupported).toBe(true);

    const onFinal = vi.fn();
    act(() => result.current.start(onFinal));
    expect(result.current.isListening).toBe(true);

    const recognition = FakeSpeechRecognition.instances.at(-1)!;
    act(() => {
      recognition.onresult?.({
        resultIndex: 0,
        results: [{ isFinal: true, 0: { transcript: "hello jarvis" } }],
      });
    });

    expect(onFinal).toHaveBeenCalledWith("hello jarvis");
    expect(result.current.transcript).toBe("hello jarvis");

    act(() => result.current.stop());
    expect(result.current.isListening).toBe(false);
  });
});
