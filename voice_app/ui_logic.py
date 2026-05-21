"""Pure UI presentation logic — what the mic button shows for each state."""
from voice_app.state import State

_LABELS = {
    State.IDLE: "\U0001F3A4",     # 🎤
    State.RECORDING: "⏹",          # stop
    State.TRANSCRIBING: "⏳",       # hourglass
}

_COLORS = {
    State.IDLE: "#2b2b2b",
    State.RECORDING: "#c0392b",
    State.TRANSCRIBING: "#d49a2b",
}


def button_label_for(state: State) -> str:
    return _LABELS[state]


def button_color_for(state: State) -> str:
    return _COLORS[state]


def compute_tray_corner_position(
    work_area: tuple[int, int, int, int],
    window_size: tuple[int, int],
    margin: int = 16,
) -> tuple[int, int]:
    """Place a window in the bottom-right of `work_area` with a `margin` gap.

    `work_area` is (left, top, right, bottom) in screen pixels — same shape
    as Windows' SPI_GETWORKAREA. Bottom is the taskbar's top edge.
    Falls back to top-left of work area if the window doesn't fit.
    """
    left, top, right, bottom = work_area
    w, h = window_size
    x = right - w - margin
    y = bottom - h - margin
    if x < left:
        x = left
    if y < top:
        y = top
    return (x, y)
