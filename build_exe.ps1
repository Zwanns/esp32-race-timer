$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$distAppDir = Join-Path $projectRoot "dist\HotWheelsTimer"
$runtimeCarsPath = Join-Path $distAppDir "cars.json"
$runtimeImagesPath = Join-Path $distAppDir "car_images"
$runtimeBackupRoot = Join-Path $projectRoot ".runtime-data-backup"
$runtimeCarsBackupPath = Join-Path $runtimeBackupRoot "cars.json"
$runtimeImagesBackupPath = Join-Path $runtimeBackupRoot "car_images"

function Assert-AppNotRunning {
  $runningProcesses = Get-CimInstance Win32_Process |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like "$distAppDir\HotWheelsTimer.exe" }

  if ($runningProcesses) {
    Write-Host ""
    Write-Host "HotWheelsTimer.exe is currently running from dist\HotWheelsTimer."
    Write-Host "Close the app before building so Windows releases EXE/DLL file locks."
    Write-Host "Runtime cars.json and car_images were not modified."
    exit 1
  }
}

function Backup-RuntimeData {
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $runtimeBackupRoot
  New-Item -ItemType Directory -Force -Path $runtimeBackupRoot | Out-Null

  $hasRuntimeData = $false
  if (Test-Path -LiteralPath $runtimeCarsPath) {
    Copy-Item -LiteralPath $runtimeCarsPath -Destination $runtimeCarsBackupPath -Force
    $hasRuntimeData = $true
  }

  if (Test-Path -LiteralPath $runtimeImagesPath) {
    Copy-Item -LiteralPath $runtimeImagesPath -Destination $runtimeImagesBackupPath -Recurse -Force
    $hasRuntimeData = $true
  }

  if ($hasRuntimeData) {
    Write-Host "Runtime car database/images backed up before rebuild."
  }
}

function Restore-RuntimeData {
  if (Test-Path -LiteralPath $runtimeCarsBackupPath) {
    Copy-Item -LiteralPath $runtimeCarsBackupPath -Destination $runtimeCarsPath -Force
    Write-Host "Restored runtime cars.json from previous dist."
  }

  if (Test-Path -LiteralPath $runtimeImagesBackupPath) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $runtimeImagesPath
    Copy-Item -LiteralPath $runtimeImagesBackupPath -Destination $runtimeImagesPath -Recurse -Force
    Write-Host "Restored runtime car_images from previous dist."
  }

  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $runtimeBackupRoot
}

Write-Host "Checking PyInstaller..."
python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "PyInstaller is not installed. Install it with:"
  Write-Host "python -m pip install pyinstaller"
  exit 1
}

Write-Host "Cleaning previous build..."
Assert-AppNotRunning
Backup-RuntimeData
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
  Restore-RuntimeData
  exit $LASTEXITCODE
}

Restore-RuntimeData

Write-Host ""
Write-Host "Done: dist\HotWheelsTimer\HotWheelsTimer.exe"
