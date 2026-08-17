import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App, { GREETING_DELAY_MS } from "../src/App";

// Isolate App's own state/wiring from the network call and the stub
// "reasoning" — both are covered directly in lib/backend.test.ts. Mic input
// is exercised naturally here: jsdom has no SpeechRecognition constructor,
// so the mic button is disabled without needing to mock lib/voice at all.
vi.mock("../src/lib/backend", () => ({
  getStubResponse: vi.fn().mockResolvedValue("Hello from stub"),
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
  it("speaks a time-of-day greeting on mount", async () => {
    const { speak } = await import("../src/lib/backend");
    await renderSettled();
    expect(speak).toHaveBeenCalledWith(expect.stringMatching(/good (morning|afternoon|evening), sir\./i));
  });

  it("renders the HUD idle state", async () => {
    await renderSettled();
    expect(screen.getByText("JARVIS")).toBeInTheDocument();
    expect(screen.getByText("Standing by")).toBeInTheDocument();
  });

  it("sends typed text through the stub backend and displays the reply", async () => {
    const { getStubResponse, speak } = await import("../src/lib/backend");
    await renderSettled();

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hello jarvis" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => expect(getStubResponse).toHaveBeenCalledWith("hello jarvis"));
    await waitFor(() => expect(screen.getByText("Hello from stub")).toBeInTheDocument());
    expect(speak).toHaveBeenCalledWith("Hello from stub");
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
