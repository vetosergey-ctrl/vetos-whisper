from enum import Enum


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class StateMachine:
    def __init__(self, on_start, on_stop_and_transcribe):
        self._on_start = on_start
        self._on_stop_and_transcribe = on_stop_and_transcribe
        self.state = State.IDLE

    def click(self):
        if self.state == State.IDLE:
            self.state = State.RECORDING
            self._on_start()
        elif self.state == State.RECORDING:
            self.state = State.TRANSCRIBING
            self._on_stop_and_transcribe()
        # TRANSCRIBING: ignore

    def transcription_done(self):
        if self.state == State.TRANSCRIBING:
            self.state = State.IDLE


def auto_stop_if_recording(sm: StateMachine) -> None:
    """If still RECORDING, behave like a manual click (stop and transcribe)."""
    if sm.state == State.RECORDING:
        sm.click()
