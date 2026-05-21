"""Create and inspect Windows .lnk shortcuts via WScript.Shell COM."""
import subprocess
from pathlib import Path


def _ps_quote(s: str) -> str:
    """Escape a string for embedding in a single-quoted PowerShell literal."""
    return s.replace("'", "''")


def create_shortcut(target: Path, args: str, lnk_path: Path,
                    working_dir: Path | None = None,
                    description: str = "") -> None:
    wd = str(working_dir) if working_dir else str(Path(target).parent)
    script = (
        "$shell = New-Object -ComObject WScript.Shell;"
        f"$lnk = $shell.CreateShortcut('{_ps_quote(str(lnk_path))}');"
        f"$lnk.TargetPath = '{_ps_quote(str(target))}';"
        f"$lnk.Arguments = '{_ps_quote(args)}';"
        f"$lnk.WorkingDirectory = '{_ps_quote(wd)}';"
        f"$lnk.Description = '{_ps_quote(description)}';"
        "$lnk.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True,
    )


def read_shortcut_target_and_args(lnk_path: Path) -> tuple[str, str]:
    script = (
        "$shell = New-Object -ComObject WScript.Shell;"
        f"$lnk = $shell.CreateShortcut('{_ps_quote(str(lnk_path))}');"
        "Write-Output $lnk.TargetPath;"
        "Write-Output '<<<ARGS>>>';"
        "Write-Output $lnk.Arguments"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    parts = result.stdout.split("<<<ARGS>>>")
    target = parts[0].strip()
    args = parts[1].strip() if len(parts) > 1 else ""
    return target, args
