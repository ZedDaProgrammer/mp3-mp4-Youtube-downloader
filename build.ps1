# build.ps1
# Script to compile Koinloader into a standalone high-performance executable using Nuitka.

Write-Host "[Koinloader] Checking for Nuitka installation..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe -m pip show nuitka > $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Koinloader] Nuitka not found in virtualenv. Installing Nuitka..." -ForegroundColor Yellow
    & .\venv\Scripts\python.exe -m pip install nuitka
}

Write-Host "[Koinloader] Compiling gui.py to single executable..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe -m nuitka `
    --standalone `
    --onefile `
    --windows-console-mode=disable `
    --enable-plugin=tk-inter `
    --include-data-dir=venv/Lib/site-packages/customtkinter=customtkinter `
    --output-dir=dist `
    gui.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "[Koinloader] Compilation successful! Executable is located in dist/gui.exe" -ForegroundColor Green
} else {
    Write-Host "[Koinloader] Compilation failed. Please inspect build logs." -ForegroundColor Red
}
