"""Audio energy gate to suppress Whisper hallucinations on silence."""
import math
import struct
import wave
from pathlib import Path

import pytest

from voice_app.audio import adaptive_audio_ctx, audio_rms, is_silent


def _write_wav(path: Path, samples: list[int],
               sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def _silent_samples(seconds: float, sr: int = 16000) -> list[int]:
    return [0] * int(seconds * sr)


def _sine_samples(seconds: float, sr: int = 16000,
                  freq: int = 440, amplitude: float = 0.3) -> list[int]:
    n = int(seconds * sr)
    peak = int(32767 * amplitude)
    return [int(peak * math.sin(2 * math.pi * freq * i / sr))
            for i in range(n)]


def test_audio_rms_zero_for_silent_wav(tmp_path):
    wav = tmp_path / "silent.wav"
    _write_wav(wav, _silent_samples(1.0))
    assert audio_rms(wav) == pytest.approx(0.0, abs=1e-6)


def test_audio_rms_around_amplitude_for_sine(tmp_path):
    wav = tmp_path / "sine.wav"
    _write_wav(wav, _sine_samples(1.0, amplitude=0.3))
    # RMS of a sine with peak amplitude A is A/sqrt(2) ≈ 0.707·A
    rms = audio_rms(wav)
    assert rms == pytest.approx(0.3 / math.sqrt(2), abs=0.01)


def test_is_silent_true_for_zero_audio(tmp_path):
    wav = tmp_path / "silent.wav"
    _write_wav(wav, _silent_samples(1.0))
    assert is_silent(wav) is True


def test_is_silent_true_for_extremely_low_noise(tmp_path):
    """Even very quiet ambient noise should count as silent."""
    wav = tmp_path / "noise.wav"
    # peaks at ~0.2% of full scale — ambient room noise
    _write_wav(wav, _sine_samples(1.0, amplitude=0.002))
    assert is_silent(wav) is True


def test_is_silent_false_for_normal_speech_loudness(tmp_path):
    """A 30%-amplitude sine simulates moderate speech loudness."""
    wav = tmp_path / "sine.wav"
    _write_wav(wav, _sine_samples(1.0, amplitude=0.3))
    assert is_silent(wav) is False


def test_is_silent_returns_true_for_missing_file(tmp_path):
    assert is_silent(tmp_path / "does-not-exist.wav") is True


def test_is_silent_returns_true_for_corrupt_wav(tmp_path):
    wav = tmp_path / "corrupt.wav"
    wav.write_bytes(b"not a wav file at all")
    assert is_silent(wav) is True


def test_is_silent_threshold_is_configurable(tmp_path):
    wav = tmp_path / "sine.wav"
    _write_wav(wav, _sine_samples(1.0, amplitude=0.05))
    rms = audio_rms(wav)  # ~0.035
    assert is_silent(wav, threshold=rms - 0.01) is False
    assert is_silent(wav, threshold=rms + 0.01) is True


def test_adaptive_audio_ctx_short_audio_returns_base():
    """Audio shorter than what `base` covers → use base (fast path)."""
    assert adaptive_audio_ctx(duration=3.0, base=768) == 768


def test_adaptive_audio_ctx_medium_audio_returns_base():
    """10s of audio still fits in base 768 (with headroom)."""
    assert adaptive_audio_ctx(duration=10.0, base=768) == 768


def test_adaptive_audio_ctx_long_audio_grows_above_base():
    """15s of audio exceeds base → grow to fit."""
    # 15s * 50 frames + 256 headroom = 1006
    assert adaptive_audio_ctx(duration=15.0, base=768) == 1006


def test_adaptive_audio_ctx_very_long_audio_capped_at_max():
    """26s of audio would need 1556 — cap at 1500 (whisper max)."""
    assert adaptive_audio_ctx(duration=26.0, base=768) == 1500


def test_adaptive_audio_ctx_zero_duration_returns_base():
    assert adaptive_audio_ctx(duration=0.0, base=768) == 768


def test_adaptive_audio_ctx_respects_explicit_max():
    """Caller can shrink the cap below 1500."""
    assert adaptive_audio_ctx(duration=30.0, base=768, max_ctx=1024) == 1024
