"""UI presentation pure logic — what the button shows for each state."""
from voice_app.state import State
from voice_app.ui_logic import (
    button_label_for,
    button_color_for,
    compute_tray_corner_position,
)


def test_idle_label_is_microphone():
    assert button_label_for(State.IDLE) == "\U0001F3A4"  # 🎤


def test_recording_label_is_stop():
    assert button_label_for(State.RECORDING) == "⏹"  # ⏹


def test_transcribing_label_is_hourglass():
    assert button_label_for(State.TRANSCRIBING) == "⏳"  # ⏳


def test_idle_color_is_neutral():
    assert button_color_for(State.IDLE) == "#2b2b2b"


def test_recording_color_is_red():
    assert button_color_for(State.RECORDING) == "#c0392b"


def test_transcribing_color_is_amber():
    assert button_color_for(State.TRANSCRIBING) == "#d49a2b"


def test_tray_corner_position_for_typical_fullhd_with_taskbar():
    # work_area=(left, top, right, bottom). Bottom is taskbar's top edge.
    work_area = (0, 0, 1920, 1040)  # 1080 - 40px taskbar
    pos = compute_tray_corner_position(work_area, window_size=(80, 60), margin=16)
    assert pos == (1920 - 80 - 16, 1040 - 60 - 16)


def test_tray_corner_position_with_offset_work_area():
    """Work area can have non-zero left/top (e.g. multi-monitor)."""
    work_area = (-1920, 0, 0, 1040)
    pos = compute_tray_corner_position(work_area, window_size=(80, 60), margin=16)
    assert pos == (0 - 80 - 16, 1040 - 60 - 16)


def test_tray_corner_position_default_margin_is_16():
    work_area = (0, 0, 1000, 1000)
    pos = compute_tray_corner_position(work_area, window_size=(100, 100))
    assert pos == (884, 884)


def test_tray_corner_position_clamps_to_work_area():
    """Window larger than work area shouldn't produce negative positions
    that go off-screen on the left/top side; clamp to work_area top-left."""
    work_area = (0, 0, 100, 100)
    pos = compute_tray_corner_position(work_area, window_size=(200, 200), margin=16)
    assert pos == (0, 0)
