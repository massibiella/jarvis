import { StrictMode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App, { GREETING_DELAY_MS } from "../src/App";

// Isolate App's own state/wiring from the network calls — both are covered
// directly in lib/backend.test.ts. Mic input is exercised naturally here:
// jsdom has no SpeechRecognition constructor, so the mic button is disabled
// without needing to mock lib/voice at all.
vi.mock("../src/lib/backend", () => ({
  getAgentResponse: vi.fn().mockResolvedValue("Hello from the agent"),
  getCheckin: vi.fn().mockResolvedValue(null),
  speak: vi.fn().mockResolvedValue(undefined),
}));

// App speaks a time-of-day greeting on mount (see src/lib/greeting.ts) after
// GREETING_DELAY_MS, which briefly puts it in "speaking" before settling
// back to idle. Every test below fast-forwards through that delay first so
// assertions aren't racing — or literally waiting seconds on — the mount
// effect.
async function renderSettled() {
  vi.useFakeTimers();
  render(<App />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(GREETING_DELAY_MS);
  });
  vi.useRealTimers();
  await waitFor(() => expect(screen.getByText("Standing by")).toBeInTheDocument());
}

describe("App", () => {
  it("speaks a time-of-day greeting on mount when no check-in is due", async () => {
    const { speak } = await import("../src/lib/backend");
    await renderSettled();
    expect(speak).toHaveBeenCalledWith(expect.stringMatching(/good (morning|afternoon|evening), sir\./i));
  });

  it("speaks the check-in instead of the greeting when one is due", async () => {
    const { getCheckin, speak } = await import("../src/lib/backend");
    (getCheckin as ReturnType<typeof vi.fn>).mockResolvedValueOnce("Good morning. Here's your briefing.");
    await renderSettled();
    expect(speak).toHaveBeenCalledWith("Good morning. Here's your briefing.");
  });

  it("falls back to the greeting when the check-in request fails", async () => {
    const { getCheckin, speak } = await import("../src/lib/backend");
    (getCheckin as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("network error"));
    await renderSettled();
    expect(speak).toHaveBeenCalledWith(expect.stringMatching(/good (morning|afternoon|evening), sir\./i));
  });

  // Regression test for a real bug: main.tsx wraps the app in <StrictMode>,
  // which double-invokes effects in dev (mount -> cleanup -> mount) to catch
  // missing cleanup. The launch effect used to guard scheduling with a ref
  // check *before* setTimeout -- StrictMode's simulated cleanup cancelled
  // the first timer, and the ref (already set) blocked the second
  // invocation from scheduling a replacement, so nothing ever spoke in a
  // real browser tab. renderSettled()/render() above don't use StrictMode,
  // so they never caught this -- this test renders through it deliberately.
  it("still speaks exactly once when mounted through StrictMode's double-invoke", async () => {
    const { speak } = await import("../src/lib/backend");
    (speak as ReturnType<typeof vi.fn>).mockClear();
    vi.useFakeTimers();
    render(
      <StrictMode>
        <App />
      </StrictMode>
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(GREETING_DELAY_MS);
    });
    vi.useRealTimers();
    await waitFor(() => expect(screen.getByText("Standing by")).toBeInTheDocument());
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak).toHaveBeenCalledWith(expect.stringMatching(/good (morning|afternoon|evening), sir\./i));
  });

  it("renders the HUD idle state", async () => {
    await renderSettled();
    expect(screen.getByText("JARVIS")).toBeInTheDocument();
    expect(screen.getByText("Standing by")).toBeInTheDocument();
  });

  it("sends typed text through the agent backend and displays the reply", async () => {
    const { getAgentResponse, speak } = await import("../src/lib/backend");
    await renderSettled();

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hello jarvis" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => expect(getAgentResponse).toHaveBeenCalledWith("hello jarvis"));
    await waitFor(() => expect(screen.getByText("Hello from the agent")).toBeInTheDocument());
    expect(speak).toHaveBeenCalledWith("Hello from the agent");
    await waitFor(() => expect(screen.getByText("Standing by")).toBeInTheDocument());
  });

  it("toggles between the assistant view and the neural map", async () => {
    await renderSettled();
    fireEvent.click(screen.getByTitle("View neural map"));
    expect(screen.getByText("Neural Map")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Back to Jarvis"));
    expect(screen.getByText("Standing by")).toBeInTheDocument();
  });

  it("disables voice input when the browser has no SpeechRecognition support", () => {
    render(<App />);
    expect(screen.getByTitle(/voice input not supported/i)).toBeDisabled();
  });
});
