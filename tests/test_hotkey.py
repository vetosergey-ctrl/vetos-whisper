"""Tests proving hotkey is bound to physical scancodes (layout-independent)."""
from voice_app.hotkey import parse_to_scancodes, H_SCANCODE_WINDOWS


def test_h_scancode_constant_is_35():
    assert H_SCANCODE_WINDOWS == 35


def test_windows_h_resolves_h_to_physical_scancode():
    """The H portion must resolve to scancode 35 (physical key position),
    not to any character. This is what makes Win+H work on Cyrillic layout."""
    parsed = parse_to_scancodes("windows+h")
    h_codes = parsed["h"]
    assert H_SCANCODE_WINDOWS in h_codes


def test_windows_h_has_two_keys():
    """The hotkey must include both Windows modifier and H key."""
    parsed = parse_to_scancodes("windows+h")
    assert "windows" in parsed
    assert "h" in parsed


def test_windows_part_accepts_left_or_right_win():
    """Windows key part must accept LWIN (91) or RWIN (92) virtual codes."""
    parsed = parse_to_scancodes("windows+h")
    win_codes = parsed["windows"]
    assert 91 in win_codes or 92 in win_codes
