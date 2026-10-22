"""Streaming, cached conversion of media files to 16 kHz mono PCM WAV."""

from __future__ import annotations

import hashlib
import json
import os
import wave
from pathlib import Path
from typing import Callable


ProgressCallback = Callable[[float, str], None]
AUDIO_CACHE_VERSION = 1


def _sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class AudioExtractor:
    def __init__(
        self, cache_dir: Path, progress: ProgressCallback | None = None
    ) -> None:
        self.cache_dir = cache_dir
        self.progress = progress

    def extract(self, media_path: Path, force: bool = False) -> Path:
        media_path = media_path.resolve()
        if self.progress:
            self.progress(0.0, "Hashing input")
        source_hash = _sha256_file(media_path)
        identity = hashlib.sha256(
            f"{source_hash}:pcm-s16le:16000:mono:v{AUDIO_CACHE_VERSION}".encode()
        ).hexdigest()
        audio_dir = self.cache_dir / "audio"
        output_path = audio_dir / f"{identity}.wav"
        metadata_path = audio_dir / f"{identity}.json"
        if output_path.exists() and metadata_path.exists() and not force:
            if self.progress:
                self.progress(1.0, "Loaded cached audio")
            return output_path

        try:
            import av
        except ImportError as exc:  # pragma: no cover - depends on local installation
            raise RuntimeError(
                "PyAV is not installed. Run: pip install -r requirements.txt"
            ) from exc

        audio_dir.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(".wav.tmp")
        container = None
        try:
            container = av.open(str(media_path), mode="r", metadata_errors="ignore")
            if not container.streams.audio:
                raise RuntimeError(f"No audio stream found in: {media_path}")
            stream = container.streams.audio[0]
            total_seconds = float(container.duration / av.time_base) if container.duration else 0
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16_000)
            if self.progress:
                self.progress(0.0, "Extracting 16 kHz mono audio")

            last_percent = -1
            with wave.open(str(temporary), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16_000)
                for frame in container.decode(stream):
                    for converted in resampler.resample(frame):
                        wav_file.writeframesraw(converted.to_ndarray().tobytes())
                    if self.progress and total_seconds and frame.time is not None:
                        percent = min(99, int(float(frame.time) / total_seconds * 100))
                        if percent >= last_percent + 5:
                            last_percent = percent
                            self.progress(percent / 100, "Extracting 16 kHz mono audio")
                for converted in resampler.resample(None):
                    wav_file.writeframesraw(converted.to_ndarray().tobytes())

            os.replace(temporary, output_path)
            metadata = {
                "cache_version": AUDIO_CACHE_VERSION,
                "source_sha256": source_hash,
                "source_name": media_path.name,
                "sample_rate": 16_000,
                "channels": 1,
                "format": "pcm_s16le",
            }
            metadata_temporary = metadata_path.with_suffix(".json.tmp")
            metadata_temporary.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(metadata_temporary, metadata_path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
        finally:
            if container is not None:
                container.close()

        if self.progress:
            self.progress(1.0, "Audio extraction complete")
        return output_path
