"""whisper-cli subprocess wrapper. CREATE_NO_WINDOW so no console flashes."""
import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
HIGH_PRIORITY_CLASS = 0x00000080


def _boost(pid: int) -> None:
    """Pull whisper-cli onto performance cores at full clock for the run.

    The daemon is a background pythonw process, so Windows 11 applies EcoQoS
    power throttling to it and its children — parking whisper-cli on efficiency
    cores at ~700MHz. Opting the child out of execution-speed throttling (and
    raising its priority) lets it use performance cores. Self-reverts when the
    process exits. Best-effort: failures here just leave default scheduling.
    """
    PROCESS_SET_INFORMATION = 0x0200
    ProcessPowerThrottling = 4
    PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
    PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1

    class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [
            ("Version", wintypes.ULONG),
            ("ControlMask", wintypes.ULONG),
            ("StateMask", wintypes.ULONG),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    h = k32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not h:
        return
    try:
        k32.SetPriorityClass(h, HIGH_PRIORITY_CLASS)
        state = PROCESS_POWER_THROTTLING_STATE()
        state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
        state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        state.StateMask = 0  # 0 = opt OUT of throttling -> run at full speed
        k32.SetProcessInformation(
            h, ProcessPowerThrottling, ctypes.byref(state), ctypes.sizeof(state)
        )
    finally:
        k32.CloseHandle(h)


def transcribe(
    cli: Path, model: Path, audio: Path,
    language: str = "ru",
    threads: int = 10,
    beam_size: int = 1,
    audio_ctx: int = 768,
    no_fallback: bool = True,
    timeout: int = 30,
    vad_model: Path | None = None,
) -> str:
    cmd = [
        str(cli),
        "-m", str(model),
        "-f", str(audio),
        "-l", language,
        "-t", str(threads),
        "-bs", str(beam_size),
        "-bo", str(beam_size),
        "-ac", str(audio_ctx),
        "-nt",
    ]
    if no_fallback:
        cmd.append("-nf")
    if vad_model is not None:
        cmd.extend(["--vad", "-vm", str(vad_model)])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW | HIGH_PRIORITY_CLASS,
    )
    try:
        _boost(proc.pid)
    except Exception:
        pass
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise RuntimeError(
            f"whisper-cli TIMEOUT after {timeout}s. "
            f"stdout_tail={(stdout or '')[-400:]!r} stderr_tail={(stderr or '')[-1200:]!r}"
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"whisper-cli rc={proc.returncode}: "
            f"stderr={(stderr or '')[-1200:]!r} stdout={(stdout or '')[-400:]!r}"
        )
    return (stdout or "").strip()
