# MusicMixCode Desktop — full build pipeline
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build_all.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
$env:TEMP = "$env:USERPROFILE\AppData\Local\Temp\pyinstaller"

Write-Host "=== 1. Run tests ===" -ForegroundColor Cyan
Push-Location $root
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
Pop-Location

Write-Host "=== 2. PyInstaller backend ===" -ForegroundColor Cyan
Push-Location $root
Remove-Item dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean build_backend.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Pop-Location

Write-Host "=== 3. Copy to Tauri binaries ===" -ForegroundColor Cyan
$binDir = "$root\desktop\src-tauri\binaries"
Copy-Item "$root\dist\musicmixcode-backend\musicmixcode-backend.exe" "$binDir\musicmixcode-backend-x86_64-pc-windows-msvc.exe" -Force
Remove-Item "$binDir\_internal" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$root\dist\musicmixcode-backend\_internal" "$binDir\_internal" -Recurse -Force

Write-Host "=== 4. Tauri build (NSIS installer) ===" -ForegroundColor Cyan
Push-Location "$root\desktop"
Remove-Item src-tauri\target -Recurse -Force -ErrorAction SilentlyContinue
npm.cmd install
npm.cmd run tauri build -- --bundles nsis
Pop-Location

$installer = Get-ChildItem "$root\desktop\src-tauri\target\release\bundle\nsis\*.exe" | Select-Object -First 1
Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Installer: $($installer.FullName)"
Write-Host "Size: $([math]::Round($installer.Length/1MB,1)) MB"
