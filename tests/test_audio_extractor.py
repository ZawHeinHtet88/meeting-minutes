import math
import struct
import wave

from audio_extractor import AudioExtractor


def test_extracts_and_caches_16khz_mono_wav(tmp_path):
    source = tmp_path / "input.wav"
    with wave.open(str(source), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(48_000)
        frames = bytearray()
        for index in range(4_800):
            sample = int(5_000 * math.sin(2 * math.pi * 440 * index / 48_000))
            frames.extend(struct.pack("<hh", sample, sample))
        target.writeframes(bytes(frames))

    extractor = AudioExtractor(tmp_path / "cache")
    first = extractor.extract(source)
    second = extractor.extract(source)

    assert first == second
    with wave.open(str(first), "rb") as extracted:
        assert extracted.getframerate() == 16_000
        assert extracted.getnchannels() == 1
        assert extracted.getsampwidth() == 2
        assert extracted.getnframes() > 0
