# Jarvis voice server (Piper TTS)

Small local HTTP wrapper around [Piper](https://github.com/OHF-Voice/piper1-gpl),
an open-source, fully-offline neural text-to-speech engine. This gives the
HUD prototype a voice without depending on any cloud TTS provider.

This is a temporary standalone service for the front-end prototype. Once
the real agent core exists it will likely call Piper directly (or this
server becomes a proper module of it) rather than being invoked over HTTP
by the browser.

## Setup

```sh
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

Download a voice model into `models/` (not checked into git — see
`.gitignore`). The default server expects `en_GB-alan-medium`:

```sh
mkdir -p models
curl -sL -o models/en_GB-alan-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx"
curl -sL -o models/en_GB-alan-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json"
```

Browse other voices/languages at the
[Piper voice samples page](https://rhasspy.github.io/piper-samples/). To
switch voices, download a different model and update `MODEL_PATH` in
`server.py`.

## Run

```sh
./.venv/Scripts/python server.py
```

Serves on `http://localhost:8765`:

- `GET /health` — sanity check
- `POST /speak` — body `{ "text": "..." }`, returns a `audio/wav` response

The frontend's `VITE_TTS_ENDPOINT` (see `frontend/.env.example`) points at
`/speak` by default.
