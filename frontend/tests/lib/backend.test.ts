import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getAgentResponse } from "../../src/lib/backend";

// backend.ts always imports voice.ts (for audioEngine.connectElement); stub
// it out so these tests never touch the real Web Audio API.
vi.mock("../../src/lib/voice", () => ({
  audioEngine: { connectElement: vi.fn(), resume: vi.fn().mockResolvedValue(undefined) },
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
// speak: posts to the Piper TTS server and plays back the response. fetch
// and the <audio> element are faked so no real network/audio is used. Each
// test re-imports the module fresh (vi.resetModules) because backend.ts
// caches a single shared <audio> element across calls, and each test wants
// its own fake Audio class wired to that cache.
// ---------------------------------------------------------------------------
class FakeAudio extends EventTarget {
  src = "";
  crossOrigin = "";
  play = vi.fn(() => {
    queueMicrotask(() => this.dispatchEvent(new Event("ended")));
    return Promise.resolve();
  });
}

async function freshBackend() {
  vi.resetModules();
  return import("../../src/lib/backend");
}

describe("speak", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the text to the TTS endpoint and resolves once playback ends", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["fake audio"])),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { speak } = await freshBackend();

    await speak("hello there");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/speak"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "hello there" }),
      })
    );
  });

  it("waits for the AudioContext to resume before starting playback", async () => {
    const playOrder: string[] = [];
    class OrderedAudio extends FakeAudio {
      play = vi.fn(() => {
        playOrder.push("play");
        queueMicrotask(() => this.dispatchEvent(new Event("ended")));
        return Promise.resolve();
      });
    }
    vi.stubGlobal("Audio", OrderedAudio);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob([])) })
    );
    vi.resetModules();
    const { audioEngine } = await import("../../src/lib/voice");
    (audioEngine.resume as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      playOrder.push("resume");
    });
    const { speak } = await import("../../src/lib/backend");

    await speak("hi");

    expect(playOrder).toEqual(["resume", "play"]);
  });

  it("rejects when the TTS server responds with an error status", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: "Internal Error" })
    );
    const { speak } = await freshBackend();

    await expect(speak("hi")).rejects.toThrow(/TTS server error/);
  });

  it("rejects when audio playback fails", async () => {
    class FailingAudio extends FakeAudio {
      play = vi.fn(() => {
        queueMicrotask(() => this.dispatchEvent(new Event("error")));
        return Promise.resolve();
      });
    }
    vi.stubGlobal("Audio", FailingAudio);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob([])) })
    );
    const { speak } = await freshBackend();

    await expect(speak("hi")).rejects.toThrow(/playback failed/i);
  });
});
