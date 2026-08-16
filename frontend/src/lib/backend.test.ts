import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getStubResponse } from "./backend";

// backend.ts always imports voice.ts (for audioEngine.connectElement); stub
// it out so these tests never touch the real Web Audio API.
vi.mock("./voice", () => ({
  audioEngine: { connectElement: vi.fn() },
}));

// ---------------------------------------------------------------------------
// getStubResponse: pure placeholder "reasoning" — no network involved.
// ---------------------------------------------------------------------------
describe("getStubResponse", () => {
  it("greets on hello", async () => {
    await expect(getStubResponse("Hello!")).resolves.toMatch(/online/i);
  });

  it("flags weather as not wired up yet", async () => {
    await expect(getStubResponse("what's the weather")).resolves.toMatch(/weather/i);
  });

  it("answers identity questions", async () => {
    await expect(getStubResponse("who are you")).resolves.toMatch(/jarvis/i);
  });

  it("asks the user to repeat blank input", async () => {
    await expect(getStubResponse("   ")).resolves.toMatch(/didn't catch/i);
  });

  it("echoes anything it doesn't recognize", async () => {
    await expect(getStubResponse("do my taxes")).resolves.toContain('"do my taxes"');
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
  return import("./backend");
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
