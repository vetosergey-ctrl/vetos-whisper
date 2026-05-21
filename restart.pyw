"""Launcher target for the desktop shortcut.

Stops any running daemon, then spawns a fresh one detached. Run via pythonw
so no console window flashes.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / "voice.pid"
PYTHONW = ROOT / "venv" / "Scripts" / "pythonw.exe"
NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

if PID_FILE.exists():
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True, creationflags=NO_WINDOW,
        )
        time.sleep(0.3)
    except (ValueError, OSError):
        pass
    try:
        PID_FILE.unlink()
    except OSError:
        pass

subprocess.Popen(
    [str(PYTHONW), "-m", "voice_app"],
    cwd=str(ROOT),
    creationflags=NO_WINDOW | DETACHED_PROCESS,
    close_fds=True,
)
