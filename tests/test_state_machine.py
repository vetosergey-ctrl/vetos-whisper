"""Tests for the toggle state machine that drives the mic button."""
from voice_app.state import State, StateMachine, auto_stop_if_recording


def _noop():
    pass


def test_initial_state_is_idle():
    sm = StateMachine(on_start=_noop, on_stop_and_transcribe=_noop)
    assert sm.state == State.IDLE


def test_click_in_idle_transitions_to_recording_and_invokes_on_start():
    starts = []
    sm = StateMachine(on_start=lambda: starts.append(1),
                      on_stop_and_transcribe=_noop)
    sm.click()
    assert sm.state == State.RECORDING
    assert starts == [1]


def test_click_in_recording_transitions_to_transcribing_and_invokes_stop():
    stops = []
    sm = StateMachine(on_start=_noop,
                      on_stop_and_transcribe=lambda: stops.append(1))
    sm.click()  # idle -> recording
    sm.click()  # recording -> transcribing
    assert sm.state == State.TRANSCRIBING
    assert stops == [1]


def test_click_in_transcribing_is_ignored():
    starts, stops = [], []
    sm = StateMachine(on_start=lambda: starts.append(1),
                      on_stop_and_transcribe=lambda: stops.append(1))
    sm.click()
    sm.click()
    sm.click()  # should be ignored
    assert sm.state == State.TRANSCRIBING
    assert starts == [1]
    assert stops == [1]


def test_transcription_done_returns_to_idle():
    sm = StateMachine(on_start=_noop, on_stop_and_transcribe=_noop)
    sm.click()
    sm.click()
    sm.transcription_done()
    assert sm.state == State.IDLE


def test_transcription_done_in_idle_is_safe_noop():
    sm = StateMachine(on_start=_noop, on_stop_and_transcribe=_noop)
    sm.transcription_done()
    assert sm.state == State.IDLE


def test_full_cycle_can_repeat():
    starts, stops = [], []
    sm = StateMachine(on_start=lambda: starts.append(1),
                      on_stop_and_transcribe=lambda: stops.append(1))
    for _ in range(3):
        sm.click()
        sm.click()
        sm.transcription_done()
    assert starts == [1, 1, 1]
    assert stops == [1, 1, 1]
    assert sm.state == State.IDLE


def test_auto_stop_transitions_recording_to_transcribing():
    stops = []
    sm = StateMachine(on_start=_noop,
                      on_stop_and_transcribe=lambda: stops.append(1))
    sm.click()  # idle -> recording
    auto_stop_if_recording(sm)
    assert sm.state == State.TRANSCRIBING
    assert stops == [1]


def test_auto_stop_is_noop_when_idle():
    starts, stops = [], []
    sm = StateMachine(on_start=lambda: starts.append(1),
                      on_stop_and_transcribe=lambda: stops.append(1))
    auto_stop_if_recording(sm)
    assert sm.state == State.IDLE
    assert starts == []
    assert stops == []


def test_auto_stop_is_noop_when_transcribing():
    stops = []
    sm = StateMachine(on_start=_noop,
                      on_stop_and_transcribe=lambda: stops.append(1))
    sm.click()
    sm.click()  # now TRANSCRIBING
    auto_stop_if_recording(sm)
    assert sm.state == State.TRANSCRIBING
    assert stops == [1]  # stop callback fired only once (not duplicated)
