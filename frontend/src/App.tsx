import { useCallback, useEffect, useRef, useState } from "react";
import { Orb } from "./components/Orb";
import { MicLevelBar } from "./components/MicLevelBar";
import { MindMap } from "./components/MindMap";
import { audioEngine, useSpeechRecognition } from "./lib/voice";
import { speak, getAgentResponse, getCheckin } from "./lib/backend";
import { getGreeting } from "./lib/greeting";
import { mindMapData, type AssistantState } from "./types";

const STATE_LABEL: Record<AssistantState, string> = {
  idle: "Standing by",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

// speak()'s fetch is aborted deliberately when the user hits Stop -- that
// rejection is expected control flow, not a real failure, so it shouldn't
// surface in errorText the way a genuine network/TTS error would.
function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

// A short pause before the launch greeting/check-in speaks -- brief enough
// to feel immediate, not a perceptual delay like the original 2000ms.
// Still routed through setTimeout, not called directly, because that's
// what makes the StrictMode double-mount fix work (see the effect below):
// only a real, cancellable/reschedulable timer survives React's dev-mode
// mount -> cleanup -> mount correctly.
export const GREETING_DELAY_MS = 500;

type View = "assistant" | "mindmap";

export default function App() {
  const [view, setView] = useState<View>("assistant");
  const [state, setState] = useState<AssistantState>("idle");
  const [responseText, setResponseText] = useState("");
  const [errorText, setErrorText] = useState("");
  const [textInput, setTextInput] = useState("");
  const busyRef = useRef(false);
  const greetedRef = useRef(false);
  // The AbortController for whatever speak() call is currently in flight --
  // handleStopSpeaking() uses it to cancel a TTS request that hasn't
  // returned audio yet (playback that HAS started is stopped separately,
  // via audioEngine.stopSpeaking()). Ref, not state: nothing needs to
  // re-render when this changes, only handleStopSpeaking needs to read it.
  const ttsAbortRef = useRef<AbortController | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const { isSupported, isListening, transcript, interimTranscript, start, stop } =
    useSpeechRecognition();

  // Arm the AudioContext to resume on the user's very first click/keypress
  // anywhere on the page, rather than waiting for the specific action that
  // needs real audio (e.g. the Send button) -- see armAutoResume() in
  // lib/voice.ts for why that lead time matters for not clipping the start
  // of the first reply.
  useEffect(() => audioEngine.armAutoResume(), []);

  // Speak a check-in (if one's due -- see src/jarvis/checkin.py) or, failing
  // that, a plain time-of-day greeting, once on launch before any user input.
  //
  // greetedRef is checked inside the timeout, not around it -- StrictMode's
  // dev-mode double-mount cancels the first timer, and a check placed
  // outside would then block a second one from ever being scheduled, so
  // nothing would fire in a real browser. Keeping the check inside means
  // whichever timer actually survives to fire is the one that counts.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (greetedRef.current) return;
      greetedRef.current = true;
      busyRef.current = true;
      void (async () => {
        let greeting: string;
        try {
          // null means no check-in is due right now (outside the window,
          // already run today, or disabled) -- fall back to the greeting.
          greeting = (await getCheckin()) ?? getGreeting();
        } catch {
          // Checkin endpoint unreachable/erroring shouldn't block the HUD's
          // launch greeting -- fall back the same way as a "not due" reply.
          greeting = getGreeting();
        }
        setState("speaking");
        setResponseText(greeting);
        const controller = new AbortController();
        ttsAbortRef.current = controller;
        try {
          await speak(greeting, controller.signal);
        } catch (err) {
          if (!isAbortError(err)) {
            setErrorText(err instanceof Error ? err.message : "Something went wrong.");
          }
        } finally {
          ttsAbortRef.current = null;
          setState("idle");
          busyRef.current = false;
        }
      })();
    }, GREETING_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  // Recognition can end on its own (silence timeout, browser cutoff, error)
  // without going through handleMicToggle — catch that drift and tear the
  // mic + UI state down instead of leaving a hot mic and a stale "Listening…".
  useEffect(() => {
    if (!isListening && state === "listening") {
      audioEngine.disconnectMic();
      setState("idle");
    }
  }, [isListening, state]);

  // ---- Core loop: user text -> agent backend -> Piper TTS -> Orb reacts ----
  const respond = useCallback(async (userText: string) => {
    if (!userText.trim() || busyRef.current) return;
    busyRef.current = true;
    setErrorText("");
    try {
      setState("thinking");
      const reply = await getAgentResponse(userText);
      setResponseText(reply);
      setState("speaking");
      const controller = new AbortController();
      ttsAbortRef.current = controller;
      await speak(reply, controller.signal);
    } catch (err) {
      if (!isAbortError(err)) {
        setErrorText(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      ttsAbortRef.current = null;
      setState("idle");
      busyRef.current = false;
    }
  }, []);

  // Interrupts whichever half of "speaking" is currently happening: aborts
  // the TTS fetch if it hasn't returned audio yet, and/or stops playback if
  // it has already started. Both are safe to call unconditionally -- each
  // is a no-op if that half isn't actually in progress.
  const handleStopSpeaking = useCallback(() => {
    audioEngine.stopSpeaking();
    ttsAbortRef.current?.abort();
  }, []);

  // ---- Input handlers: mic (voice), text field (fallback), view switch ----
  const handleMicToggle = useCallback(async () => {
    if (isListening) {
      stop();
      audioEngine.disconnectMic();
      setState("idle");
      return;
    }
    try {
      setErrorText("");
      await audioEngine.connectMic();
      setState("listening");
      start((finalText) => {
        stop();
        audioEngine.disconnectMic();
        void respond(finalText);
      });
    } catch {
      setErrorText("Microphone access was denied or is unavailable.");
      setState("idle");
    }
  }, [isListening, respond, start, stop]);

  const handleTextSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const value = textInput;
      setTextInput("");
      void respond(value);
    },
    [respond, textInput]
  );

  const handleToggleView = useCallback(() => {
    if (isListening) {
      stop();
      audioEngine.disconnectMic();
    }
    setView((v) => (v === "assistant" ? "mindmap" : "assistant"));
  }, [isListening, stop]);

  // Long replies (e.g. a check-in) can be taller than .transcript's capped
  // height (see App.css) -- scroll back to the top on each new reply so it
  // reads from the start instead of staying wherever a previous, shorter
  // reply had left the scroll position.
  useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = 0;
  }, [responseText]);

  const isSpeaking = state === "speaking";

  // ---- Layout: header, assistant view (Orb + transcript + controls) or
  // ---- neural-map view, and the corner button that switches between them ----
  return (
    <div className="hud">
      <header className="hud-header">
        <span className="hud-title">JARVIS</span>
        <span className="hud-status">
          {view === "assistant" ? STATE_LABEL[state] : "Neural Map"}
        </span>
      </header>

      {view === "assistant" && <MicLevelBar active={state === "listening"} />}

      {view === "assistant" ? (
        <>
          <main className="hud-main">
            <Orb state={state} />

            <div className="transcript" ref={transcriptRef}>
              {(transcript || interimTranscript) && (
                <p className="transcript-line user-line">
                  {transcript}
                  <span className="interim">{interimTranscript}</span>
                </p>
              )}
              {responseText && <p className="transcript-line assistant-line">{responseText}</p>}
              {errorText && <p className="transcript-line error-line">{errorText}</p>}
            </div>
          </main>

          <footer className="hud-footer">
            <button
              className={`mic-button ${isListening || isSpeaking ? "active" : ""}`}
              onClick={isSpeaking ? handleStopSpeaking : handleMicToggle}
              disabled={state === "thinking" || (!isSpeaking && !isSupported)}
              title={
                isSpeaking
                  ? "Stop Jarvis from speaking"
                  : isSupported
                    ? "Toggle voice input"
                    : "Voice input not supported in this browser"
              }
            >
              {isSpeaking || isListening ? "Stop" : "Speak"}
            </button>

            <form className="text-fallback" onSubmit={handleTextSubmit}>
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={isSupported ? "…or type instead" : "Voice unsupported — type here"}
              />
              <button type="submit" disabled={state === "thinking" || state === "speaking"}>
                Send
              </button>
            </form>
          </footer>
        </>
      ) : (
        <main className="hud-main mindmap-main">
          <MindMap root={mindMapData} />
        </main>
      )}

      <button
        className="view-toggle"
        onClick={handleToggleView}
        title={view === "assistant" ? "View neural map" : "Back to Jarvis"}
      >
        {view === "assistant" ? (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
            <circle cx="12" cy="5" r="2.2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="5" cy="17" r="2.2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="19" cy="17" r="2.2" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M12 7.2 L5 14.8 M12 7.2 L19 14.8 M6.8 17 H17.2"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
            <circle cx="12" cy="12" r="7" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="12" cy="12" r="2.2" fill="currentColor" />
          </svg>
        )}
      </button>
    </div>
  );
}
