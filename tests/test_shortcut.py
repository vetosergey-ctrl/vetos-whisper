"""Tests for the .lnk creator."""
import subprocess
from pathlib import Path

from voice_app.shortcut import create_shortcut, read_shortcut_target_and_args


def _read_back(lnk: Path) -> tuple[str, str]:
    """Read TargetPath and Arguments from a .lnk via WScript.Shell."""
    return read_shortcut_target_and_args(lnk)


def test_create_shortcut_writes_lnk_file(tmp_path):
    target = tmp_path / "tgt.exe"
    target.write_text("")
    lnk = tmp_path / "TestStart.lnk"

    create_shortcut(target=target, args="", lnk_path=lnk)

    assert lnk.exists()
    assert lnk.stat().st_size > 0


def test_shortcut_target_matches_input(tmp_path):
    target = tmp_path / "myapp.exe"
    target.write_text("")
    lnk = tmp_path / "Test.lnk"

    create_shortcut(target=target, args="", lnk_path=lnk)

    target_path, _ = _read_back(lnk)
    assert Path(target_path) == target


def test_shortcut_arguments_match_input(tmp_path):
    target = tmp_path / "x.exe"
    target.write_text("")
    lnk = tmp_path / "T.lnk"

    create_shortcut(target=target, args='--foo "bar baz"', lnk_path=lnk)

    _, args = _read_back(lnk)
    assert "--foo" in args
    assert "bar baz" in args


def test_shortcut_overwrites_existing(tmp_path):
    target1 = tmp_path / "first.exe"
    target1.write_text("")
    target2 = tmp_path / "second.exe"
    target2.write_text("")
    lnk = tmp_path / "T.lnk"

    create_shortcut(target=target1, args="", lnk_path=lnk)
    create_shortcut(target=target2, args="", lnk_path=lnk)

    target_path, _ = _read_back(lnk)
    assert Path(target_path) == target2
