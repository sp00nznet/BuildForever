@echo off
REM ==========================================
REM BuildForever Win32 Build Script
REM Creates a standalone Windows executable
REM ==========================================

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo BuildForever Win32 Build Script
echo ==========================================
echo.

REM Check for Python
echo [1/5] Checking for Python installation...
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found: !PYTHON_VERSION!
    set PYTHON_CMD=python
    goto :found_python
)

where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found: !PYTHON_VERSION!
    set PYTHON_CMD=python3
    goto :found_python
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('py --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found: !PYTHON_VERSION!
    set PYTHON_CMD=py
    goto :found_python
)

echo.
echo ERROR: Python is not installed or not in PATH
echo.
echo Please install Python 3.8+ using one of these methods:
echo   1. Microsoft Store: Search for "Python 3.11"
echo   2. Download from: https://www.python.org/downloads/
echo   3. Or add Python to your PATH if already installed
echo.
pause
exit /b 1

:found_python
echo.
echo [2/5] Installing build dependencies...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install pyinstaller pywebview
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Some dependencies may have failed to install.
    echo Continuing anyway...
)

echo.
echo [3/5] Installing application dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt
%PYTHON_CMD% -m pip install -r requirements-desktop.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install application dependencies
    pause
    exit /b 1
)

echo.
echo [4/5] Cleaning previous build artifacts...
if exist "build" rd /s /q build
if exist "dist" rd /s /q dist
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo.
echo [5/5] Building Win32 executable with PyInstaller...
%PYTHON_CMD% -m PyInstaller --clean --noconfirm buildforever.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above for details.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD SUCCESSFUL!
echo ==========================================
echo.
echo Executable location: dist\BuildForever.exe
echo.
echo The executable can run on any Windows 7+ system
echo without requiring Python to be installed.
echo.
echo Size: Approximately 50-80 MB
echo.
pause
