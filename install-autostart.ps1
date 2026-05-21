<#
Hands-off install:
  1. Desktop shortcut for one-click start.
  2. Startup-folder shortcut for autostart at logon.
  3. Weekly Scheduled Task for whisper.cpp updates.
Re-runnable; overwrites existing entries.
#>

$root = "C:\Users\vetos\tools\whisper-voice"
$pythonw = Join-Path $root "venv\Scripts\pythonw.exe"

$shell = New-Object -ComObject WScript.Shell

function New-WhisperVoiceShortcut($lnkPath) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "`"$root\restart.pyw`""
    $lnk.WorkingDirectory = $root
    $lnk.WindowStyle = 7
    $lnk.Description = "WhisperVoice voice input daemon (restart-style launcher)"
    $lnk.Save()
}

# 1) Desktop shortcut
$desktop = [Environment]::GetFolderPath('Desktop')
$desktopLnk = Join-Path $desktop "WhisperVoice.lnk"
New-WhisperVoiceShortcut $desktopLnk
Write-Host "Desktop shortcut: $desktopLnk"

# 2) Startup-folder shortcut
$startup = [Environment]::GetFolderPath('Startup')
$startupLnk = Join-Path $startup "WhisperVoice.lnk"
New-WhisperVoiceShortcut $startupLnk
Write-Host "Startup shortcut: $startupLnk"

# 3) Weekly update Scheduled Task
$taskName = "WhisperVoice-WeeklyUpdate"
$updateScript = Join-Path $root "update.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updateScript`""

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 03:30

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Update whisper.cpp engine if a new tag is at least 7 days old." `
    -Force | Out-Null
Write-Host "Scheduled task: $taskName (Mon 03:30)"
