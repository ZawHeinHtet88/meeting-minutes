import wave

import pytest

from transcriber import (
    GeminiFilterBlockedError,
    Transcriber,
    transcript_text,
    validate_transcript_quality,
)


def _silent_wav(path, seconds):
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 16_000 * seconds)


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


def test_successful_chunks_resume_after_later_failure(tmp_path, monkeypatch):
    media = tmp_path / "long.wav"
    _silent_wav(media, 130)
    transcriber = Transcriber("gemini-test", "my", tmp_path / "cache")
    transcriber._model_checked = True

    def fail_second(path, duration):
        if path.name == "0001.wav":
            raise RuntimeError("temporary failure")
        return {
            "segments": [
                {"start": 0, "end": 2, "speaker": "Speaker 1", "text": "ပထမပိုင်း"}
            ]
        }

    monkeypatch.setattr(transcriber, "_invoke_chunk", fail_second)
    with pytest.raises(RuntimeError, match="temporary failure"):
        transcriber.transcribe(media)

    resumed_calls = []

    def succeed(path, duration):
        resumed_calls.append(path.name)
        return {
            "segments": [
                {"start": 0, "end": min(2, duration), "speaker": "Speaker 1", "text": "ဒုတိယပိုင်း"}
            ]
        }

    monkeypatch.setattr(transcriber, "_invoke_chunk", succeed)
    result = transcriber.transcribe(media)

    assert resumed_calls == ["0001.wav"]
    assert len(result["segments"]) == 2


def test_filter_blocked_chunk_is_split_and_combined(tmp_path, monkeypatch):
    media = tmp_path / "blocked.wav"
    _silent_wav(media, 60)
    transcriber = Transcriber("gemini-test", "my", tmp_path / "cache")
    durations = []

    def split_then_succeed(_path, duration):
        durations.append(duration)
        if duration > 30:
            raise GeminiFilterBlockedError("blocked")
        return {
            "segments": [
                {"start": 0, "end": duration, "speaker": "Speaker 1", "text": "စကား"}
            ]
        }

    monkeypatch.setattr(transcriber, "_invoke_chunk", split_then_succeed)
    result, loaded = transcriber._transcribe_chunk_cached(media, 60)

    assert loaded is False
    # The two silent halves are byte-identical, so the second half reuses the
    # first half's content-addressed chunk cache.
    assert durations == [60, 30.0]
    assert [segment["start"] for segment in result["segments"]] == [0.0, 30.0]
    assert result["segments"][-1]["end"] == 60.0
