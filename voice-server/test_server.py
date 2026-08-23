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


class FakeAudioChunk:
    """Stands in for piper.voice.AudioChunk -- one per sentence."""

    def __init__(self, num_samples=100, sample_rate=16000, sample_width=2, sample_channels=1):
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.sample_channels = sample_channels
        self.audio_int16_bytes = b"\x00\x00" * num_samples


def _import_server(chunks):
    """Imports server.py fresh with `piper` mocked so voice.synthesize()
    yields `chunks`, and the model path faked present."""
    fake_piper_module = MagicMock()
    fake_piper_module.PiperVoice.load.return_value.synthesize.side_effect = lambda _text, *a, **k: (
        iter(chunks)
    )

    sys.modules.pop("server", None)
    with patch.dict(sys.modules, {"piper": fake_piper_module}):
        with patch.object(Path, "exists", return_value=True):
            import server

    return server


@pytest.fixture
def client():
    server = _import_server([FakeAudioChunk()])
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


def test_speak_inserts_a_pause_between_sentences():
    """voice.synthesize() yields one AudioChunk per sentence -- the server
    should insert SENTENCE_PAUSE_SECONDS of silence between them instead of
    concatenating them back-to-back into one continuous breath."""
    sample_rate = 16000
    chunk_samples = 100
    server = _import_server(
        [FakeAudioChunk(num_samples=chunk_samples, sample_rate=sample_rate)] * 3
    )
    try:
        with server.app.test_client() as test_client:
            res = test_client.post("/speak", json={"text": "One. Two. Three."})
        assert res.status_code == 200
        with wave.open(io.BytesIO(res.data)) as wav_file:
            total_frames = wav_file.getnframes()
        pause_frames = int(sample_rate * server.SENTENCE_PAUSE_SECONDS)
        assert total_frames == chunk_samples * 3 + pause_frames * 2
    finally:
        sys.modules.pop("server", None)


def test_speak_adds_no_pause_for_a_single_sentence():
    """A one-sentence reply shouldn't grow any extra silence."""
    chunk_samples = 100
    server = _import_server([FakeAudioChunk(num_samples=chunk_samples)])
    try:
        with server.app.test_client() as test_client:
            res = test_client.post("/speak", json={"text": "Just one sentence."})
        with wave.open(io.BytesIO(res.data)) as wav_file:
            assert wav_file.getnframes() == chunk_samples
    finally:
        sys.modules.pop("server", None)
