"""Layout-independent hotkey: bound to physical scancodes.

The H key has scancode 35 on Windows regardless of the active keyboard layout
(English, Russian, etc.) — Win+H therefore fires on the same physical key
combination on any layout.
"""
import keyboard

H_SCANCODE_WINDOWS = 35


def parse_to_scancodes(hotkey: str) -> dict[str, list[int]]:
    """Map each part of the hotkey string to its accepted scancodes/virtual codes.

    For 'windows+h' returns {'windows': [...lwin/rwin codes...], 'h': [35]}.
    """
    names = [p.strip().lower() for p in hotkey.split("+")]
    steps = keyboard.parse_hotkey(hotkey)
    if len(steps) != 1:
        raise ValueError(f"Expected single-step hotkey, got {len(steps)} steps")
    step = steps[0]
    if len(step) != len(names):
        raise ValueError(
            f"Hotkey '{hotkey}' parsed into {len(step)} keys, "
            f"expected {len(names)}"
        )
    return {name: list(codes) for name, codes in zip(names, step)}
