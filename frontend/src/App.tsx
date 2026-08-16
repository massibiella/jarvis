import { useCallback, useRef, useState } from "react";
import { Orb } from "./components/Orb";
import { audioEngine } from "./lib/audioEngine";
import { speak } from "./lib/ttsClient";
import { getStubResponse } from "./lib/stubAssistant";
import { useSpeechRecognition } from "./hooks/useSpeechRecognition";
import type { AssistantState } from "./types";

const STATE_LABEL: Record<AssistantState, string> = {
  idle: "Standing by",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

export default function App() {
  const [state, setState] = useState<AssistantState>("idle");
  const [responseText, setResponseText] = useState("");
  const [errorText, setErrorText] = useState("");
  const [textInput, setTextInput] = useState("");
  const busyRef = useRef(false);

  const { isSupported, isListening, transcript, interimTranscript, start, stop } =
    useSpeechRecognition();

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

  const handleMicToggle = useCallback(async () => {
    if (isListening) {
      stop();
      audioEngine.disconnectMic();
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

  return (
    <div className="hud">
      <header className="hud-header">
        <span className="hud-title">JARVIS</span>
        <span className="hud-status">{STATE_LABEL[state]}</span>
      </header>

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
          title={isSupported ? "Toggle voice input" : "Voice input not supported in this browser"}
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
    </div>
  );
}
