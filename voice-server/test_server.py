"""Unit tests for the Piper TTS HTTP wrapper (server.py).

Fakes out the `piper` package and the on-disk voice model so these tests run
fast, without a downloaded model or the heavy onnxruntime/piper-tts install.
"""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _fake_synthesize_wav(_text, wav_file):
    """Stands in for Piper's real inference: writes a tiny valid WAV."""
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(b"\x00\x00" * 100)


@pytest.fixture
def client():
    """Import server.py fresh with `piper` mocked and the model path faked present."""
    fake_piper_module = MagicMock()
    fake_piper_module.PiperVoice.load.return_value.synthesize_wav.side_effect = (
        _fake_synthesize_wav
    )

    sys.modules.pop("server", None)
    with patch.dict(sys.modules, {"piper": fake_piper_module}):
        with patch.object(Path, "exists", return_value=True):
            import server

    with server.app.test_client() as test_client:
        yield test_client

    sys.modules.pop("server", None)


def test_health_reports_ok_and_the_loaded_voice(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "voice": "en_GB-alan-medium"}


def test_speak_returns_a_playable_wav(client):
    res = client.post("/speak", json={"text": "hello there"})
    assert res.status_code == 200
    assert res.mimetype == "audio/wav"
    with wave.open(io.BytesIO(res.data)) as wav_file:
        assert wav_file.getnframes() > 0


def test_speak_requires_text_in_the_body(client):
    res = client.post("/speak", json={})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_speak_rejects_blank_text(client):
    res = client.post("/speak", json={"text": "   "})
    assert res.status_code == 400
