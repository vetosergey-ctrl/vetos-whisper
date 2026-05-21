"""Voice input daemon entry point: pythonw -m voice_app"""
import json
import os
import sys
import threading
import time
from pathlib import Path

import keyboard
import pyperclip

from voice_app.audio import adaptive_audio_ctx, audio_rms, is_silent, normalize_peak
from voice_app.models import list_models, resolve_active_model, switch_model
from voice_app.recorder import Recorder, detect_mic
from voice_app.state import State, StateMachine, auto_stop_if_recording
from voice_app.transcriber import transcribe
from voice_app.ui import MicWindow

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "voice.log"
PID_FILE = ROOT / "voice.pid"

# (label, rms threshold). Lower = accepts quieter speech; higher = rejects more
# background so noisy rooms don't transcribe ambient sound.
SILENCE_PRESETS = [
    ("Шёпот (0.002)", 0.002),
    ("Тихая речь (0.004)", 0.004),
    ("Обычная речь (0.006)", 0.006),
    ("Обычно, фон (0.010)", 0.010),
    ("Громкое помещение (0.015)", 0.015),
    ("Очень шумно (0.025)", 0.025),
]


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _process_alive(pid: int) -> bool:
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def acquire_lock() -> None:
    if PID_FILE.exists():
        try:
            old = int(PID_FILE.read_text(encoding="utf-8").strip())
            if _process_alive(old) and old != os.getpid():
                log(f"Already running as PID {old}; exiting")
                sys.exit(0)
        except (ValueError, OSError):
            pass
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_lock() -> None:
    try:
        if PID_FILE.exists():
            content = PID_FILE.read_text(encoding="utf-8").strip()
            if content == str(os.getpid()):
                PID_FILE.unlink()
    except OSError:
        pass


CONFIG_PATH = ROOT / "config.json"


def _write_config_atomic(config: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


class App:
    def __init__(self, config: dict):
        self.config = config
        self.recorder = Recorder(
            mic=config["mic"],
            max_seconds=int(config.get("max_record_seconds", 120)),
        )
        self.sm = StateMachine(
            on_start=self._on_start,
            on_stop_and_transcribe=self._on_stop_and_transcribe,
        )
        self.window = MicWindow(self.sm, on_close=self.shutdown)
        self._unhook = None
        self._auto_stop_after_id: str | None = None

    def _on_start(self) -> None:
        path = self.recorder.start()
        log(f"Recording → {path.name}")
        self._schedule_auto_stop()

    def _on_stop_and_transcribe(self) -> None:
        self._cancel_auto_stop()
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _schedule_auto_stop(self) -> None:
        self._cancel_auto_stop()
        ms = int(self.recorder.max_seconds) * 1000
        self._auto_stop_after_id = self.window.root.after(ms, self._auto_stop)

    def _cancel_auto_stop(self) -> None:
        if self._auto_stop_after_id:
            try:
                self.window.root.after_cancel(self._auto_stop_after_id)
            except Exception:
                pass
            self._auto_stop_after_id = None

    def _auto_stop(self) -> None:
        self._auto_stop_after_id = None
        if self.sm.state == State.RECORDING:
            log(f"Auto-stop: max duration {self.recorder.max_seconds}s reached")
            auto_stop_if_recording(self.sm)
            self.window.refresh()

    def _transcribe_worker(self) -> None:
        path, duration = self.recorder.stop()
        if not path:
            log(f"No audio captured (duration {duration:.1f}s)")
            self.window.schedule(self._after_transcribe_no_op)
            return

        min_duration = float(self.config.get("min_record_seconds", 0.5))
        silence_threshold = float(self.config.get("silence_rms_threshold", 0.01))
        if duration < min_duration:
            log(f"Skipped: too short ({duration:.2f}s < {min_duration}s)")
            try:
                path.unlink()
            except OSError:
                pass
            self.window.schedule(self._after_transcribe_no_op)
            return
        if is_silent(path, threshold=silence_threshold):
            log(f"Skipped: silent (rms={audio_rms(path):.4f} < {silence_threshold})")
            try:
                path.unlink()
            except OSError:
                pass
            self.window.schedule(self._after_transcribe_no_op)
            return

        rms = audio_rms(path)
        gain = normalize_peak(path)
        norm_rms = audio_rms(path)
        active_model = resolve_active_model(self.config)
        ac = adaptive_audio_ctx(
            duration=duration,
            base=int(self.config.get("audio_ctx", 768)),
        )
        log(f"Transcribing {path.name} ({path.stat().st_size//1024} KB, recorded {duration:.1f}s, rms={rms:.4f}->{norm_rms:.4f} (gain {gain:.1f}x), model={self.config['active_model']}, ac={ac})")
        t0 = time.time()
        text = ""
        try:
            vad_path = self.config.get("vad_model")
            text = transcribe(
                cli=Path(self.config["whisper_cli"]),
                model=active_model,
                audio=path,
                language=self.config.get("language", "ru"),
                threads=int(self.config.get("threads", 10)),
                beam_size=int(self.config.get("beam_size", 1)),
                audio_ctx=ac,
                no_fallback=bool(self.config.get("no_fallback", True)),
                timeout=max(30, int(duration * 1.5)),
                vad_model=Path(vad_path) if vad_path else None,
            )
        except Exception as e:
            log(f"Transcribe failed: {e}")
            try:
                debug_dir = ROOT / "logs" / "failed"
                debug_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                dst = debug_dir / path.name
                shutil.copy2(path, dst)
                log(f"Saved failed audio: {dst}")
            except OSError as oe:
                log(f"Could not save failed audio: {oe}")
        dt = time.time() - t0
        rt = (dt / duration) if duration else 0
        log(f"Transcribed in {dt:.1f}s ({rt:.2f}x rt): {text[:120]}")
        try:
            path.unlink()
        except OSError:
            pass

        def deliver():
            self.sm.transcription_done()
            self.window.refresh()
            if text:
                pyperclip.copy(text)
                time.sleep(0.05)
                keyboard.send("ctrl+v")
                log(f"Pasted {len(text)} chars")

        self.window.schedule(deliver)

    def _after_transcribe_no_op(self) -> None:
        self.sm.transcription_done()
        self.window.refresh()

    def _hotkey_pressed(self) -> None:
        # Called from keyboard's hook thread — marshal to Tk thread.
        self.window.trigger_click()

    def install_hotkey(self) -> None:
        hotkey = self.config.get("hotkey", "windows+h")
        keyboard.add_hotkey(hotkey, self._hotkey_pressed, suppress=True)
        log(f"Hotkey installed: {hotkey}")

    def shutdown(self) -> None:
        log("Shutting down")
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.recorder.kill()
        release_lock()

    def _refresh_menu(self) -> None:
        self.window.populate_menu(
            list_models(self.config),
            self.config["active_model"],
            self._select_model,
            SILENCE_PRESETS,
            float(self.config.get("silence_rms_threshold", 0.004)),
            self._select_threshold,
        )

    def _select_model(self, name: str) -> None:
        if name == self.config["active_model"]:
            return
        log(f"Switching model: {self.config['active_model']} -> {name}")
        self.config = switch_model(self.config, name)
        _write_config_atomic(self.config)
        self._refresh_menu()

    def _select_threshold(self, value: float) -> None:
        if abs(value - float(self.config.get("silence_rms_threshold", 0.004))) < 1e-9:
            return
        log(f"Silence threshold: {self.config.get('silence_rms_threshold')} -> {value}")
        self.config["silence_rms_threshold"] = value
        _write_config_atomic(self.config)
        self._refresh_menu()

    def run(self) -> None:
        self.install_hotkey()
        self._refresh_menu()
        try:
            self.window.run()
        finally:
            self.shutdown()


def main() -> None:
    acquire_lock()
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        whisper_cli = Path(config["whisper_cli"])
        if not whisper_cli.exists():
            log(f"whisper-cli not found: {whisper_cli}")
            return
        try:
            model = resolve_active_model(config)
        except ValueError as e:
            log(f"Model config invalid: {e}")
            return
        if not model.exists():
            log(f"model not found: {model}")
            return

        mic = config.get("mic_device") or detect_mic()
        if not mic:
            log("No microphone detected")
            return
        config["mic"] = mic

        log(f"Started. mic={mic}, model={config['active_model']} ({model.name})")
        App(config).run()
    finally:
        release_lock()


if __name__ == "__main__":
    main()
