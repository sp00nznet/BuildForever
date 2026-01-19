#!/usr/bin/env pwsh
# ==========================================
# BuildForever Win32 Build Script (PowerShell)
# Creates a standalone Windows executable
# ==========================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "BuildForever Win32 Build Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/5] Checking for Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
$pythonExitCode = $LASTEXITCODE

# Check if Python command failed or returned Windows Store alias message
if ($pythonExitCode -ne 0 -or $pythonVersion -match "was not found" -or $pythonVersion -match "not recognized") {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.8+ using one of these methods:" -ForegroundColor Yellow
    Write-Host "  1. Microsoft Store: Search for 'Python 3.11'" -ForegroundColor White
    Write-Host "  2. Download from: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "  3. Or add Python to your PATH if already installed" -ForegroundColor White
    Write-Host ""
    Write-Host "After installing, restart your terminal and try again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "Found: $pythonVersion" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] Installing build dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install pyinstaller pywebview

Write-Host ""
Write-Host "[3/5] Installing application dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/5] Cleaning previous build artifacts..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[5/5] Building Win32 executable with PyInstaller..." -ForegroundColor Yellow
python -m PyInstaller --clean --noconfirm buildforever.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    Write-Host "Check the error messages above for details." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Executable location: dist\BuildForever.exe" -ForegroundColor Green
Write-Host ""
Write-Host "The executable can run on any Windows 7+ system" -ForegroundColor White
Write-Host "without requiring Python to be installed." -ForegroundColor White
Write-Host ""
Write-Host "Size: Approximately 50-80 MB" -ForegroundColor White
Write-Host ""
