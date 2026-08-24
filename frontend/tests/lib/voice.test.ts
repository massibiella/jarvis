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

class FakeBufferSourceNode extends EventTarget {
  static instances: FakeBufferSourceNode[] = [];
  buffer: unknown = null;
  connect = vi.fn();
  onended: (() => void) | null = null;
  // Mimics real playback finishing asynchronously, after start() is called.
  start = vi.fn(() => {
    queueMicrotask(() => this.onended?.());
  });
  stop = vi.fn(() => this.onended?.());

  constructor() {
    super();
    FakeBufferSourceNode.instances.push(this);
  }
}

class FakeGainNode {
  static instances: FakeGainNode[] = [];
  gain = { value: 1 };
  connect = vi.fn();
  constructor() {
    FakeGainNode.instances.push(this);
  }
}

class FakeOscillatorNode {
  static instances: FakeOscillatorNode[] = [];
  connect = vi.fn();
  start = vi.fn();
  constructor() {
    FakeOscillatorNode.instances.push(this);
  }
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  state = "running";
  destination = {};
  createAnalyser() {
    return new FakeAnalyserNode();
  }
  createMediaStreamSource() {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }
  createBufferSource() {
    return new FakeBufferSourceNode();
  }
  createGain() {
    return new FakeGainNode();
  }
  createOscillator() {
    return new FakeOscillatorNode();
  }
  decodeAudioData = vi.fn(async () => ({ duration: 1 }) as unknown as AudioBuffer);
  resume = vi.fn();
  constructor() {
    FakeAudioContext.instances.push(this);
  }
}

// Browsers start a fresh AudioContext "suspended" until a user gesture
// unlocks it — this variant models that so resume() has something to do.
// Instances are captured (like FakeSpeechRecognition.instances below) since
// AudioEngine keeps its AudioContext private.
class SuspendedFakeAudioContext extends FakeAudioContext {
  static instances: SuspendedFakeAudioContext[] = [];
  state = "suspended";
  resume = vi.fn(async () => {
    this.state = "running";
  });
  constructor() {
    super();
    SuspendedFakeAudioContext.instances.push(this);
  }
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
    FakeAudioContext.instances = [];
    SuspendedFakeAudioContext.instances = [];
    FakeBufferSourceNode.instances = [];
    FakeGainNode.instances = [];
    FakeOscillatorNode.instances = [];
  });

  it("keeps the output stream warm with a near-silent tone as soon as the context is created", async () => {
    const { audioEngine } = await freshVoiceModule();
    await audioEngine.connectMic();

    const ctx = FakeAudioContext.instances.at(-1)!;
    const osc = FakeOscillatorNode.instances.at(-1)!;
    const gain = FakeGainNode.instances.at(-1)!;
    expect(osc.connect).toHaveBeenCalledWith(gain);
    expect(gain.connect).toHaveBeenCalledWith(ctx.destination);
    expect(osc.start).toHaveBeenCalledOnce();
    // Inaudible, but non-zero so the stream can't be optimized away as silent.
    expect(gain.gain.value).toBeGreaterThan(0);
    expect(gain.gain.value).toBeLessThan(0.001);
  });

  it("only starts one keep-alive tone no matter how many times the context is touched", async () => {
    const { audioEngine } = await freshVoiceModule();
    await audioEngine.connectMic();
    await audioEngine.resume();
    await audioEngine.playBuffer(new ArrayBuffer(8));

    expect(FakeOscillatorNode.instances).toHaveLength(1);
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

  it("resume() waits for a suspended AudioContext to actually finish resuming", async () => {
    vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
    const { audioEngine } = await freshVoiceModule();

    await audioEngine.resume();

    const ctx = SuspendedFakeAudioContext.instances.at(-1)!;
    expect(ctx.resume).toHaveBeenCalledOnce();
    expect(ctx.state).toBe("running");
  });

  it("resume() is a no-op once the AudioContext is already running", async () => {
    const { audioEngine } = await freshVoiceModule();
    await audioEngine.connectMic(); // creates the (already "running") context

    await audioEngine.resume();

    const ctx = FakeAudioContext.instances.at(-1)!;
    expect(ctx.resume).not.toHaveBeenCalled();
  });

  describe("armAutoResume", () => {
    it("resumes the AudioContext on the first pointerdown, then stops listening", async () => {
      vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
      const { audioEngine } = await freshVoiceModule();
      audioEngine.armAutoResume();

      window.dispatchEvent(new Event("pointerdown"));
      await Promise.resolve(); // let the async resume() call settle

      const ctx = SuspendedFakeAudioContext.instances.at(-1)!;
      expect(ctx.resume).toHaveBeenCalledOnce();

      window.dispatchEvent(new Event("pointerdown"));
      await Promise.resolve();
      expect(ctx.resume).toHaveBeenCalledOnce(); // listener removed after first fire
    });

    it("resumes on the first keydown too", async () => {
      vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
      const { audioEngine } = await freshVoiceModule();
      audioEngine.armAutoResume();

      window.dispatchEvent(new Event("keydown"));
      await Promise.resolve();

      const ctx = SuspendedFakeAudioContext.instances.at(-1)!;
      expect(ctx.resume).toHaveBeenCalledOnce();
    });

    it("only arms once even if called multiple times", async () => {
      vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
      const { audioEngine } = await freshVoiceModule();
      audioEngine.armAutoResume();
      audioEngine.armAutoResume();

      window.dispatchEvent(new Event("pointerdown"));
      await Promise.resolve();

      // A second arm() call would have added a second listener, resuming
      // via a second (freshly-created) context -- only one should exist.
      expect(SuspendedFakeAudioContext.instances).toHaveLength(1);
    });

    it("the returned cleanup function removes the listeners before they fire", async () => {
      vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
      const { audioEngine } = await freshVoiceModule();
      const cleanupFn = audioEngine.armAutoResume();
      cleanupFn();

      window.dispatchEvent(new Event("pointerdown"));
      await Promise.resolve();

      expect(SuspendedFakeAudioContext.instances).toHaveLength(0);
    });
  });

  describe("playBuffer", () => {
    it("decodes the data and plays it through the analyser and destination, resolving when it ends", async () => {
      const { audioEngine } = await freshVoiceModule();

      await audioEngine.playBuffer(new ArrayBuffer(8));

      const ctx = FakeAudioContext.instances.at(-1)!;
      const source = FakeBufferSourceNode.instances.at(-1)!;
      expect(ctx.decodeAudioData).toHaveBeenCalledOnce();
      expect(source.buffer).toEqual({ duration: 1 });
      expect(source.connect).toHaveBeenCalledWith(expect.any(FakeAnalyserNode));
      expect(source.connect).toHaveBeenCalledWith(ctx.destination);
      expect(source.start).toHaveBeenCalledOnce();
    });

    it("waits for a suspended AudioContext to resume before starting playback", async () => {
      vi.stubGlobal("AudioContext", SuspendedFakeAudioContext);
      const { audioEngine } = await freshVoiceModule();

      await audioEngine.playBuffer(new ArrayBuffer(8));

      const ctx = SuspendedFakeAudioContext.instances.at(-1)!;
      expect(ctx.resume).toHaveBeenCalledOnce();
      const source = FakeBufferSourceNode.instances.at(-1)!;
      expect(source.start).toHaveBeenCalledOnce();
    });

    it("rejects when the audio data fails to decode", async () => {
      class FailingDecodeAudioContext extends FakeAudioContext {
        decodeAudioData = vi.fn().mockRejectedValue(new Error("bad wav"));
      }
      vi.stubGlobal("AudioContext", FailingDecodeAudioContext);
      const { audioEngine } = await freshVoiceModule();

      await expect(audioEngine.playBuffer(new ArrayBuffer(8))).rejects.toThrow(/playback failed/i);
    });
  });

  describe("stopSpeaking", () => {
    it("is a no-op when nothing is currently playing", async () => {
      const { audioEngine } = await freshVoiceModule();
      expect(() => audioEngine.stopSpeaking()).not.toThrow();
    });

    it("stops the in-progress source, which resolves the pending playBuffer() promise", async () => {
      // Unlike the base fake, start() here does NOT fire onended on its
      // own -- playback only "ends" if something explicitly stops it,
      // letting the test control exactly when that happens.
      class HangingBufferSourceNode extends FakeBufferSourceNode {
        start = vi.fn();
      }
      class HangingAudioContext extends FakeAudioContext {
        createBufferSource() {
          return new HangingBufferSourceNode();
        }
      }
      vi.stubGlobal("AudioContext", HangingAudioContext);
      const { audioEngine } = await freshVoiceModule();

      const playPromise = audioEngine.playBuffer(new ArrayBuffer(8));
      // Let playBuffer's internal awaits (resume, decodeAudioData) settle
      // so the source actually gets created/tracked before we stop it.
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();

      audioEngine.stopSpeaking();

      await expect(playPromise).resolves.toBeUndefined();
      const source = FakeBufferSourceNode.instances.at(-1)!;
      expect(source.stop).toHaveBeenCalledOnce();
    });
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
