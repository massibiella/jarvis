import { useCallback, useEffect, useRef, useState } from "react";
import { Orb } from "./components/Orb";
import { MindMap } from "./components/MindMap";
import { audioEngine, useSpeechRecognition } from "./lib/voice";
import { speak, getStubResponse } from "./lib/backend";
import { mindMapData, type AssistantState } from "./types";

const STATE_LABEL: Record<AssistantState, string> = {
  idle: "Standing by",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

type View = "assistant" | "mindmap";

export default function App() {
  const [view, setView] = useState<View>("assistant");
  const [state, setState] = useState<AssistantState>("idle");
  const [responseText, setResponseText] = useState("");
  const [errorText, setErrorText] = useState("");
  const [textInput, setTextInput] = useState("");
  const busyRef = useRef(false);

  const { isSupported, isListening, transcript, interimTranscript, start, stop } =
    useSpeechRecognition();

  // Recognition can end on its own (silence timeout, browser cutoff, error)
  // without going through handleMicToggle — catch that drift and tear the
  // mic + UI state down instead of leaving a hot mic and a stale "Listening…".
  useEffect(() => {
    if (!isListening && state === "listening") {
      audioEngine.disconnectMic();
      setState("idle");
    }
  }, [isListening, state]);

  // ---- Core loop: user text -> stub "reasoning" -> Piper TTS -> Orb reacts ----
  const respond = useCallback(async (userText: string) => {
    if (!userText.trim() || busyRef.current) return;
    busyRef.current = true;
    setErrorText("");
    try {
      setState("thinking");
      const reply = await getStubResponse(userText);
      setResponseText(reply);
      setState("speaking");
      await speak(reply);
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setState("idle");
      busyRef.current = false;
    }
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

      {view === "assistant" ? (
        <>
          <main className="hud-main">
            <Orb state={state} />

            <div className="transcript">
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
              className={`mic-button ${isListening ? "active" : ""}`}
              onClick={handleMicToggle}
              disabled={!isSupported || state === "thinking" || state === "speaking"}
              title={
                isSupported ? "Toggle voice input" : "Voice input not supported in this browser"
              }
            >
              {isListening ? "Stop" : "Speak"}
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
