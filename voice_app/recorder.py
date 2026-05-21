"""ffmpeg dshow microphone recorder. CREATE_NO_WINDOW so no console flashes."""
import re
import subprocess
import tempfile
import time
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


def detect_mic() -> str | None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-list_devices", "true",
             "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    devices: list[str] = []
    for line in result.stderr.splitlines():
        m = re.search(r'\[dshow[^\]]*\]\s*"([^"]+)"\s*\(audio\)', line)
        if m:
            devices.append(m.group(1))
    if not devices:
        return None
    for d in devices:
        low = d.lower()
        if any(k in low for k in ("array", "qualcomm", "internal", "intel smart sound")):
            return d
    return devices[0]


class Recorder:
    def __init__(self, mic: str, max_seconds: int = 120):
        self.mic = mic
        self.max_seconds = max_seconds
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._t_start: float = 0.0

    def start(self) -> Path:
        path = Path(tempfile.gettempdir()) / f"voice_{int(time.time()*1000)}.wav"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "dshow", "-i", f"audio={self.mic}",
            "-ac", "1", "-ar", "16000", "-y",
            "-t", str(self.max_seconds),
            str(path),
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        self._path = path
        self._t_start = time.time()
        return path

    def stop(self) -> tuple[Path | None, float]:
        proc = self._proc
        path = self._path
        duration = time.time() - self._t_start if self._t_start else 0.0
        self._proc = None
        self._path = None
        self._t_start = 0.0
        if not proc:
            return path, duration
        try:
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if path and path.exists() and path.stat().st_size >= 1000:
            return path, duration
        return None, duration

    def kill(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
