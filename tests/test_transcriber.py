import wave

import pytest

from transcriber import Transcriber, transcript_text, validate_transcript_quality


def test_antigravity_transcription_is_cached(tmp_path, monkeypatch):
    media = tmp_path / "meeting.wav"
    with wave.open(str(media), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 80_000)

    transcriber = Transcriber(
        "gemini-test-flash", "my", tmp_path / "cache", executable="agy-test"
    )
    transcriber._model_checked = True
    calls = 0

    def fake_invoke(_path, duration):
        nonlocal calls
        calls += 1
        assert duration == 5.0
        return {
            "segments": [
                {"start": 0.2, "end": 2.4, "speaker": "Speaker 1", "text": "Hello"},
                {"start": 3.0, "end": 4.5, "speaker": "Speaker 2", "text": "မင်္ဂလာပါ"},
            ]
        }

    monkeypatch.setattr(transcriber, "_invoke_chunk", fake_invoke)

    first = transcriber.transcribe(media)
    second = transcriber.transcribe(media)

    assert first == second
    assert calls == 1
    assert first["provider"] == "antigravity"
    assert first["segments"][1]["speaker"] == "Speaker 2"
    rendered = transcript_text(second)
    assert "[00:00:00 - 00:00:02] Speaker 1: Hello" in rendered
    assert "Speaker 2: မင်္ဂလာပါ" in rendered


def test_quality_gate_rejects_placeholder_transcript():
    with pytest.raises(RuntimeError, match="placeholder"):
        validate_transcript_quality(
            {
                "language": "my",
                "duration": 60,
                "segments": [{"start": 0, "end": 5, "text": "spoken text"}],
            }
        )
