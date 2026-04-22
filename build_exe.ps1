$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Checking PyInstaller..."
python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "PyInstaller is not installed. Install it with:"
  Write-Host "python -m pip install pyinstaller"
  exit 1
}

Write-Host "Cleaning previous build..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue ".\build", ".\dist", ".\HotWheelsTimer.spec"

Write-Host "Building HotWheelsTimer.exe..."
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --contents-directory "." `
  --name "HotWheelsTimer" `
  --icon "timer.ico" `
  --add-data "timer.ico;." `
  --add-data "DS-DIGI.TTF;." `
  --add-data "DS-DIGII.TTF;." `
  --add-data "cars.json;." `
  --add-data "results_data.json;." `
  --add-data "sounds;sounds" `
  --add-data "car_images;car_images" `
  "timer_app.py"
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Done: dist\HotWheelsTimer\HotWheelsTimer.exe"
