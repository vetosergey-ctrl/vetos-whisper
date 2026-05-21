"""Mini mic window. Frameless, always-on-top, no-activate."""
import tkinter as tk
from typing import Callable, Iterable

from voice_app.state import State, StateMachine
from voice_app.ui_logic import (
    button_label_for,
    button_color_for,
    compute_tray_corner_position,
)


def _get_work_area() -> tuple[int, int, int, int]:
    """Return primary monitor's work area (left, top, right, bottom) excluding taskbar."""
    try:
        import ctypes
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        SPI_GETWORKAREA = 0x0030
        rect = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return (0, 0, 1920, 1040)  # safe fallback


class MicWindow:
    def __init__(self, state_machine: StateMachine, on_close: Callable[[], None]):
        self.sm = state_machine
        self._on_close = on_close
        self.root = tk.Tk()
        self.root.title("Whisper Voice")
        self.root.attributes("-topmost", True)
        self.root.attributes("-toolwindow", True)
        self.root.resizable(False, False)

        self.button = tk.Button(
            self.root,
            text=button_label_for(State.IDLE),
            bg=button_color_for(State.IDLE),
            fg="white",
            activebackground=button_color_for(State.IDLE),
            activeforeground="white",
            font=("Segoe UI Emoji", 22),
            width=2, height=1,
            relief="flat", borderwidth=0,
            cursor="hand2",
            command=self._on_click,
        )
        self.button.pack(padx=4, pady=4)

        self._menu = tk.Menu(self.root, tearoff=0)
        self.button.bind("<Button-3>", self._show_menu)

        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        self.root.update_idletasks()
        self._move_to_tray_corner()
        self._apply_no_activate()

    def _move_to_tray_corner(self) -> None:
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x, y = compute_tray_corner_position(_get_work_area(), (w, h), margin=48)
        self.root.geometry(f"+{x}+{y}")

    def _apply_no_activate(self) -> None:
        """Set WS_EX_NOACTIVATE so clicking the button doesn't steal focus."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            cur = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(
                hwnd, GWL_EXSTYLE,
                cur | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
            )
        except Exception:
            pass

    def _on_click(self) -> None:
        self.sm.click()
        self.refresh()

    def trigger_click(self) -> None:
        """Thread-safe entry: schedule a click on the Tk thread."""
        self.root.after(0, self._on_click)

    def schedule(self, fn: Callable[[], None]) -> None:
        """Run `fn` on the Tk thread soon."""
        self.root.after(0, fn)

    def refresh(self) -> None:
        color = button_color_for(self.sm.state)
        self.button.config(
            text=button_label_for(self.sm.state),
            bg=color,
            activebackground=color,
        )

    def populate_menu(
        self,
        models: Iterable[str], current_model: str,
        on_model: Callable[[str], None],
        thresholds: Iterable[tuple[str, float]], current_threshold: float,
        on_threshold: Callable[[float], None],
    ) -> None:
        self._menu.delete(0, "end")
        for name in models:
            label = ("● " if name == current_model else "    ") + name
            self._menu.add_command(label=label,
                                   command=lambda n=name: on_model(n))
        self._menu.add_separator()
        self._menu.add_command(label="Порог тишины", state="disabled")
        for plabel, value in thresholds:
            mark = "● " if abs(value - current_threshold) < 1e-9 else "    "
            self._menu.add_command(label=f"{mark}{plabel}",
                                   command=lambda v=value: on_threshold(v))

    def _show_menu(self, event) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _handle_close(self) -> None:
        self._on_close()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()
