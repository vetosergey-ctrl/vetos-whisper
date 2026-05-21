"""Audio energy gate — suppresses Whisper hallucinations on silent input."""
import struct
import wave
from pathlib import Path


def audio_rms(wav_path: Path) -> float:
    """Return RMS amplitude of a 16-bit PCM mono WAV, normalized to 0..1.

    Returns 0.0 if the file is missing, malformed, or has no samples.
    """
    try:
        with wave.open(str(wav_path), "rb") as f:
            n = f.getnframes()
            sw = f.getsampwidth()
            ch = f.getnchannels()
            if n == 0 or sw != 2 or ch != 1:
                return 0.0
            raw = f.readframes(n)
    except (FileNotFoundError, wave.Error, EOFError, struct.error, OSError):
        return 0.0

    samples = struct.unpack(f"<{n}h", raw)
    if not samples:
        return 0.0
    mean_sq = sum(s * s for s in samples) / len(samples)
    return (mean_sq ** 0.5) / 32768.0


def is_silent(wav_path: Path, threshold: float = 0.01) -> bool:
    """True if the audio's RMS is below `threshold` (normalized 0..1).

    Missing or corrupt files count as silent.
    """
    return audio_rms(wav_path) < threshold


def normalize_peak(wav_path: Path, target: float = 0.9, max_gain: float = 12.0) -> float:
    """Amplify a 16-bit PCM mono WAV in place so its peak reaches `target` of
    full scale, capped at `max_gain`.

    Quiet input (peak rms ~0.016) drives whisper medium-q5 into a decoder loop:
    it never emits EOT and runs to the full audio context, taking 10-30x longer
    and producing empty/looped output. Boosting gain before transcription keeps
    the signal in the range the model decodes cleanly. Returns the gain applied
    (1.0 if the file is missing, malformed, or already at/above target).
    """
    try:
        with wave.open(str(wav_path), "rb") as f:
            n = f.getnframes()
            sw = f.getsampwidth()
            ch = f.getnchannels()
            fr = f.getframerate()
            if n == 0 or sw != 2 or ch != 1:
                return 1.0
            raw = f.readframes(n)
    except (FileNotFoundError, wave.Error, EOFError, struct.error, OSError):
        return 1.0

    samples = list(struct.unpack(f"<{n}h", raw))
    peak = max((abs(s) for s in samples), default=0)
    if peak == 0:
        return 1.0
    gain = min(max_gain, target * 32768.0 / peak)
    if gain <= 1.0:
        return 1.0

    amplified = [max(-32768, min(32767, int(s * gain))) for s in samples]
    try:
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(ch)
            w.setsampwidth(sw)
            w.setframerate(fr)
            w.writeframes(struct.pack(f"<{len(amplified)}h", *amplified))
    except (wave.Error, OSError):
        return 1.0
    return gain


def adaptive_audio_ctx(
    duration: float,
    base: int = 768,
    max_ctx: int = 1500,
    headroom: int = 256,
    frames_per_sec: int = 50,
) -> int:
    """Pick whisper encoder audio context size based on actual audio duration.

    Whisper computes ~50 mel frames per second of audio. A fixed small `base`
    is fast for short utterances but truncates longer audio, causing the
    decoder to hallucinate looped repetitions. Grow the context just enough
    to cover the recording, capped at `max_ctx`.
    """
    needed = int(duration * frames_per_sec) + headroom
    return min(max_ctx, max(base, needed))
