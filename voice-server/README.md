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
- `POST /speak` — body `{ "text": "..." }`, returns a `audio/wav` response.
  Piper's `voice.synthesize()` yields one audio chunk per sentence (it
  splits on `.`/`!`/`?` internally); `server.py` inserts `SENTENCE_PAUSE_SECONDS`
  of silence between consecutive chunks instead of concatenating them
  back-to-back, so a multi-sentence reply reads as separate thoughts rather
  than one continuous breath.

The frontend's `VITE_TTS_ENDPOINT` (see `frontend/.env.example`) points at
`/speak` by default.

## Tests

```sh
./.venv/Scripts/python -m pytest
```

`test_server.py` fakes out the `piper` package and the on-disk model file, so
tests run in well under a second and don't need a real voice model
downloaded or `onnxruntime` installed.
