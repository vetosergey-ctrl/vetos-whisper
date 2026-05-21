$root = "C:\Users\vetos\tools\whisper-voice"
$pidFile = Join-Path $root "voice.pid"

if (Test-Path $pidFile) {
    $pidValue = (Get-Content $pidFile -Raw).Trim()
    try {
        Stop-Process -Id ([int]$pidValue) -Force -ErrorAction Stop
        Write-Host "Stopped PID $pidValue"
    } catch {
        Write-Host "PID $pidValue not running"
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "No pid file. Killing any voice.py instances by command line."
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'voice\.py' } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host ("Stopped PID {0}" -f $_.ProcessId)
        }
}
