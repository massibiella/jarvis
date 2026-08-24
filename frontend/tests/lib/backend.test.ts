import { afterEach, describe, expect, it, vi } from "vitest";
import { getAgentResponse, getCheckin, sanitizeForSpeech, speak } from "../../src/lib/backend";

// backend.ts always imports voice.ts for audioEngine.playBuffer(); stub it
// out so these tests never touch the real Web Audio API. Playback timing
// and the AudioBufferSourceNode graph itself are covered in voice.test.ts.
vi.mock("../../src/lib/voice", () => ({
  audioEngine: { playBuffer: vi.fn().mockResolvedValue(undefined) },
}));

// ---------------------------------------------------------------------------
// getAgentResponse: POSTs to the Jarvis agent backend's /chat endpoint.
// fetch is faked so no real network is used.
// ---------------------------------------------------------------------------
describe("getAgentResponse", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the text to the chat endpoint and returns the reply", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reply: "Hello, Sir." }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAgentResponse("hello jarvis")).resolves.toBe("Hello, Sir.");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "hello jarvis" }),
      })
    );
  });

  it("rejects when the agent server responds with an error status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: "Internal Error" })
    );

    await expect(getAgentResponse("hi")).rejects.toThrow(/Agent server error/);
  });
});

// ---------------------------------------------------------------------------
// getCheckin: GETs the Jarvis agent backend's /checkin endpoint. fetch is
// faked so no real network is used.
// ---------------------------------------------------------------------------
describe("getCheckin", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the reply when a check-in is due", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reply: "Good morning. Here's your briefing." }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCheckin()).resolves.toBe("Good morning. Here's your briefing.");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/checkin"));
  });

  it("returns null when no check-in is due", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ reply: null }) })
    );

    await expect(getCheckin()).resolves.toBeNull();
  });

  it("rejects when the checkin server responds with an error status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: "Internal Error" })
    );

    await expect(getCheckin()).rejects.toThrow(/Checkin server error/);
  });
});

// ---------------------------------------------------------------------------
// sanitizeForSpeech: strips markdown/symbols so Piper never reads punctuation
// aloud literally, while preserving negative numbers, decimal points,
// sentence-ending punctuation (for pacing -- see voice-server/server.py),
// and spelling out ° / °C / °F.
// ---------------------------------------------------------------------------
describe("sanitizeForSpeech", () => {
  it("strips markdown formatting symbols but keeps the words", () => {
    expect(sanitizeForSpeech("**Sure**, here's the #plan: (do it).")).toBe("Sure here s the plan do it.");
  });

  it("preserves the minus sign on negative numbers", () => {
    expect(sanitizeForSpeech("the balance is -42 dollars")).toBe("the balance is -42 dollars");
  });

  it("does not treat a hyphen between words as a negative sign", () => {
    expect(sanitizeForSpeech("a well-known fact")).toBe("a well known fact");
  });

  it("collapses whitespace left behind by stripped symbols", () => {
    expect(sanitizeForSpeech("hello   ***   world")).toBe("hello world");
  });

  it("leaves plain word/number text untouched", () => {
    expect(sanitizeForSpeech("temperature is 72 degrees")).toBe("temperature is 72 degrees");
  });

  it("spells out a bare degree sign instead of dropping it", () => {
    expect(sanitizeForSpeech("rotate 90° clockwise")).toBe("rotate 90 degrees clockwise");
  });

  it("expands °C and °F into Celsius and Fahrenheit", () => {
    expect(sanitizeForSpeech("27.0°C (80.6°F) with clear skies")).toBe(
      "27.0 degrees Celsius 80.6 degrees Fahrenheit with clear skies"
    );
  });

  it("preserves a decimal point between digits", () => {
    expect(sanitizeForSpeech("the reading was 26.7 today")).toBe("the reading was 26.7 today");
  });

  it("preserves sentence-ending punctuation so replies can be paced into separate sentences", () => {
    expect(sanitizeForSpeech("It's sunny. Bring a hat!")).toBe("It s sunny. Bring a hat!");
  });
});

// ---------------------------------------------------------------------------
// speak: posts the sanitized text to the Piper TTS server and hands the
// decoded audio to audioEngine.playBuffer() for playback.
// ---------------------------------------------------------------------------
describe("speak", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("forwards an AbortSignal to fetch, so Stop can cancel an in-flight TTS request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)),
    });
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await speak("hi", controller.signal);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/speak"),
      expect.objectContaining({ signal: controller.signal })
    );
  });

  it("posts the sanitized text to the TTS endpoint and plays the response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { audioEngine } = await import("../../src/lib/voice");

    await speak("**Sure**, here's #2 for you.");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/speak"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "Sure here s 2 for you." }),
      })
    );
    expect(audioEngine.playBuffer).toHaveBeenCalledOnce();
  });

  it("rejects when the TTS server responds with an error status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: "Internal Error" })
    );

    await expect(speak("hi")).rejects.toThrow(/TTS server error/);
  });

  it("propagates a playback failure from audioEngine.playBuffer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)) })
    );
    const { audioEngine } = await import("../../src/lib/voice");
    (audioEngine.playBuffer as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Audio playback failed")
    );

    await expect(speak("hi")).rejects.toThrow(/playback failed/i);
  });
});
