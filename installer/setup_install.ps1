param([string]$InstallDir)
$ErrorActionPreference = "Stop"

function Find-Uv {
    $candidates = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:LOCALAPPDATA\uv\bin\uv.exe",
        "$env:USERPROFILE\.cargo\bin\uv.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    $fromPath = Get-Command uv -ErrorAction SilentlyContinue
    if ($fromPath) { return $fromPath.Source }
    return $null
}

# Step 1: uv
Write-Host ""
Write-Host "[ 1 / 4 ]  Checking for uv package manager..." -ForegroundColor Cyan

$uv = Find-Uv
if ($uv) {
    Write-Host "           Found: $uv" -ForegroundColor Green
} else {
    Write-Host "           Not found - installing uv..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uv = Find-Uv
    if (-not $uv) {
        Write-Host "ERROR: Could not locate uv after installation." -ForegroundColor Red
        exit 1
    }
    Write-Host "           Installed: $uv" -ForegroundColor Green
}

# Step 2: Python venv
Write-Host ""
Write-Host "[ 2 / 4 ]  Creating Python 3.12 virtual environment..." -ForegroundColor Cyan

$venvDir = Join-Path $InstallDir "viro-env"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path $pythonExe) {
    Write-Host "           Already exists, skipping." -ForegroundColor Green
} else {
    & $uv venv $venvDir --python 3.12
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: venv creation failed." -ForegroundColor Red; exit 1 }
    Write-Host "           Done." -ForegroundColor Green
}

# Step 3: Dependencies
Write-Host ""
Write-Host "[ 3 / 4 ]  Installing dependencies (this may take a few minutes)..." -ForegroundColor Cyan

$reqFile = Join-Path $InstallDir "requirements.txt"
& $uv pip install --python $venvDir --system-certs -r $reqFile
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: dependency installation failed." -ForegroundColor Red; exit 1 }
Write-Host "           Done." -ForegroundColor Green

# Step 4: Playwright browser (~200 MB)
Write-Host ""
Write-Host "[ 4 / 4 ]  Installing Chromium browser (~200 MB)..." -ForegroundColor Cyan

$python = Join-Path $venvDir "Scripts\python.exe"
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Playwright install failed." -ForegroundColor Red; exit 1 }
Write-Host "           Done." -ForegroundColor Green

Write-Host ""
Write-Host "All done!" -ForegroundColor Green
