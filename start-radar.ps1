$ollamaUrl = "http://localhost:11434/api/tags"
$maxAttempts = 60
$attempt = 0

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri $ollamaUrl -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
    }

    Start-Sleep -Seconds 2
    $attempt++
}

if ($attempt -ge $maxAttempts) {
    exit 1
}

# RADAR_PYTHON overrides the interpreter; the default is the uv-managed Python 3.11.
$radarPython = if ($env:RADAR_PYTHON) { $env:RADAR_PYTHON } else { Join-Path $env:APPDATA "uv\python\cpython-3.11-windows-x86_64-none\python.exe" }
$radarDir = $PSScriptRoot

Set-Location $radarDir

Start-Process `
    -FilePath $radarPython `
    -ArgumentList "serve.py" `
    -WorkingDirectory $radarDir `
    -WindowStyle Hidden
