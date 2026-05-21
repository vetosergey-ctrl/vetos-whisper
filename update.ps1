#requires -Version 5.1
<#
Weekly updater for whisper.cpp engine.
Checks ggerganov/whisper.cpp for new tags, picks the latest tag whose commit
date is at least 7 days old, rebuilds, and replaces binaries.
#>

param(
    [int]$MinAgeDays = 7,
    [string]$Root = "C:\Users\vetos\tools\whisper-voice"
)

$ErrorActionPreference = "Stop"
$logFile = Join-Path $Root "logs\update.log"
$null = New-Item -ItemType Directory -Path (Split-Path $logFile) -Force

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

try {
    Log "=== Update run started ==="
    $repo = Join-Path $Root "whisper.cpp"
    if (-not (Test-Path $repo)) { throw "whisper.cpp repo missing: $repo" }

    Push-Location $repo
    try {
        $currentTag = (git describe --tags --exact-match HEAD 2>$null)
        if (-not $currentTag) { $currentTag = (git rev-parse --short HEAD) }
        Log "Current: $currentTag"

        git fetch --tags --quiet
        $cutoff = (Get-Date).AddDays(-$MinAgeDays)
        Log ("Cutoff date: {0:yyyy-MM-dd}" -f $cutoff)

        $candidate = $null
        $candidateDate = $null
        $tags = git tag --sort=-creatordate | Select-Object -First 20
        foreach ($tag in $tags) {
            $dateStr = git log -1 --format=%cI $tag 2>$null
            if (-not $dateStr) { continue }
            $tagDate = [DateTimeOffset]::Parse($dateStr).UtcDateTime
            if ($tagDate -le $cutoff) {
                $candidate = $tag
                $candidateDate = $tagDate
                break
            } else {
                Log ("Skip {0} ({1:yyyy-MM-dd}, too fresh)" -f $tag, $tagDate)
            }
        }

        if (-not $candidate) {
            Log "No eligible tag found"
            return
        }
        Log ("Candidate: {0} ({1:yyyy-MM-dd})" -f $candidate, $candidateDate)

        if ($candidate -eq $currentTag) {
            Log "Already on latest eligible tag"
            return
        }

        Log "Updating to $candidate"
        git checkout --quiet $candidate

        $build = Join-Path $repo "build"
        if (Test-Path $build) { Remove-Item -Recurse -Force $build }

        $cmake = "C:\Program Files\CMake\bin\cmake.exe"
        $vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsarm64.bat"
        if (-not (Test-Path $vcvars)) {
            throw "vcvarsarm64.bat not found at $vcvars"
        }

        Log "Configuring (Release, ARM64 NEON)"
        & cmd /c "`"$vcvars`" && `"$cmake`" -B `"$build`" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_TESTS=OFF" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

        Log "Building"
        & cmd /c "`"$vcvars`" && `"$cmake`" --build `"$build`" --config Release --target whisper-cli --parallel" 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) { throw "cmake build failed" }

        $newCli = Get-ChildItem -Path $build -Recurse -Filter "whisper-cli.exe" | Select-Object -First 1
        if (-not $newCli) { throw "whisper-cli.exe not produced" }

        $binDir = Join-Path $Root "bin"
        $null = New-Item -ItemType Directory -Path $binDir -Force
        Copy-Item $newCli.FullName (Join-Path $binDir "whisper-cli.exe") -Force
        # Copy DLLs adjacent to the cli (whisper.dll, ggml*.dll if shared) — harmless if absent
        Get-ChildItem -Path $newCli.DirectoryName -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item $_.FullName $binDir -Force
        }

        Log "Updated $currentTag -> $candidate, binary at $binDir\whisper-cli.exe"
    } finally {
        Pop-Location
    }

    Log "=== Update run finished OK ==="
} catch {
    Log ("ERROR: " + $_.Exception.Message)
    exit 1
}
