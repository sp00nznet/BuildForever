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

# Function to test if a Python path is valid
function Test-PythonPath {
    param([string]$PythonExe)
    if (Test-Path $PythonExe) {
        $output = & $PythonExe --version 2>&1
        return -not ($output -match "was not found" -or $output -match "not recognized")
    }
    return $false
}

# Try to find Python - first check PATH, then common install locations
$pythonCmd = "python"
$pythonVersion = python --version 2>&1
$pythonExitCode = $LASTEXITCODE

# Check if Python command failed or returned Windows Store alias message
if ($pythonExitCode -ne 0 -or $pythonVersion -match "was not found" -or $pythonVersion -match "not recognized") {
    Write-Host "Python not found in PATH, searching common locations..." -ForegroundColor Yellow

    # Common Python install locations on Windows
    $pythonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python38\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python39\python.exe",
        "C:\Python38\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )

    $foundPython = $false
    foreach ($path in $pythonPaths) {
        if (Test-Path $path) {
            $pythonCmd = $path
            $pythonVersion = & $path --version 2>&1
            $foundPython = $true
            Write-Host "Found Python at: $path" -ForegroundColor Green
            break
        }
    }

    if (-not $foundPython) {
        Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Python 3.8+ using one of these methods:" -ForegroundColor Yellow
        Write-Host "  1. Winget:          winget install Python.Python.3.11" -ForegroundColor White
        Write-Host "  2. Microsoft Store: Search for 'Python 3.11'" -ForegroundColor White
        Write-Host "  3. Download from:   https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "  4. Or add Python to your PATH if already installed" -ForegroundColor White
        Write-Host ""
        Write-Host "After installing, restart your terminal and try again." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
}

Write-Host "Found: $pythonVersion" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] Installing build dependencies..." -ForegroundColor Yellow
& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install pyinstaller pywebview

Write-Host ""
Write-Host "[3/5] Installing application dependencies..." -ForegroundColor Yellow
& $pythonCmd -m pip install -r requirements.txt
& $pythonCmd -m pip install -r requirements-desktop.txt

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
& $pythonCmd -m PyInstaller --clean --noconfirm buildforever.spec

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
