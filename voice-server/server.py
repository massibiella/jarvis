"""Minimal local TTS server for the Jarvis HUD prototype.

Wraps Piper (https://github.com/OHF-Voice/piper1-gpl), an open-source,
fully-offline neural TTS engine, behind a tiny HTTP API so the browser
frontend (which can't run Piper directly) can request synthesized speech.

Run:
    .venv/Scripts/python server.py

Then POST { "text": "..." } to http://localhost:8765/speak and you'll get
back a WAV file.
"""

import io
import wave
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from piper import PiperVoice

# ---- Setup: load the Piper voice model once at startup --------------------

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "en_GB-alan-medium.onnx"

app = Flask(__name__)
CORS(app)

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Voice model not found at {MODEL_PATH}. "
        "Download it into voice-server/models/ (see README.md)."
    )

voice = PiperVoice.load(str(MODEL_PATH))


# ---- Routes -----------------------------------------------------------------


@app.post("/speak")
def speak():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing 'text' in request body"}), 400

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    buffer.seek(0)

    return send_file(buffer, mimetype="audio/wav")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "voice": MODEL_PATH.stem})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765)
