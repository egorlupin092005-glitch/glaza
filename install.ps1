$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$envPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $envPath)) {
    $runtimePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $runtimePython) {
        & $runtimePython -m venv .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv
    } else {
        throw 'Install Python 3.12 (64-bit) from python.org, then run this installer again.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment. Install Python 3.12 (64-bit).' }
}
& $envPath -m pip install -r requirements.txt -c requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check your Internet connection.' }
& $envPath download_model.py
if ($LASTEXITCODE -ne 0) { throw 'Hand model download failed.' }
& $envPath -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
Write-Host 'Glaza is ready. Open Start.cmd.' -ForegroundColor Green
