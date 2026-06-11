# Get the directory of the script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "[Koinloader] Virtual environment not found. Creating one..." -ForegroundColor Cyan
    Start-Process python -ArgumentList "-m venv venv" -Wait
}

# Check if virtual environment activation script exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[Koinloader] Activating virtual environment..." -ForegroundColor Cyan
    & .\venv\Scripts\Activate.ps1
    
    Write-Host "[Koinloader] Installing/checking dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt
    
    Write-Host "[Koinloader] Launching application..." -ForegroundColor Cyan
    python gui.py
} else {
    Write-Host "[Koinloader] Error: Virtual environment structure is invalid. Running using global python..." -ForegroundColor Yellow
    pip install -r requirements.txt
    python gui.py
}
