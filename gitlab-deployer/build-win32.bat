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

REM Check for Python - actually test if it works, not just if command exists
echo [1/5] Checking for Python installation...

REM Try python command
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
        echo %%i | findstr /i "Python" >nul
        if !ERRORLEVEL! EQU 0 (
            echo Found: %%i
            set PYTHON_CMD=python
            goto :found_python
        )
    )
)

REM Try python3 command
python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do (
        echo %%i | findstr /i "Python" >nul
        if !ERRORLEVEL! EQU 0 (
            echo Found: %%i
            set PYTHON_CMD=python3
            goto :found_python
        )
    )
)

REM Try py launcher
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('py --version 2^>^&1') do (
        echo %%i | findstr /i "Python" >nul
        if !ERRORLEVEL! EQU 0 (
            echo Found: %%i
            set PYTHON_CMD=py
            goto :found_python
        )
    )
)

REM Python not found
echo.
echo ==========================================
echo ERROR: Python is not installed
echo ==========================================
echo.
echo Please install Python 3.8 or higher using one of these methods:
echo.
echo   Option 1 - Microsoft Store (Recommended):
echo     1. Open Microsoft Store
echo     2. Search for "Python 3.11" or "Python 3.12"
echo     3. Click "Get" to install
echo.
echo   Option 2 - Download from python.org:
echo     1. Go to https://www.python.org/downloads/
echo     2. Download Python 3.11 or 3.12
echo     3. Run installer and CHECK "Add Python to PATH"
echo.
echo   Option 3 - Winget (if available):
echo     winget install Python.Python.3.11
echo.
echo After installation, close and reopen this window, then run again.
echo.
pause
exit /b 1

:found_python
echo.
echo [2/5] Installing build dependencies...
%PYTHON_CMD% -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pip upgrade failed, continuing...
)

%PYTHON_CMD% -m pip install pyinstaller pywebview
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to install PyInstaller and pywebview
    echo.
    echo Try running: %PYTHON_CMD% -m pip install pyinstaller pywebview
    echo.
    pause
    exit /b 1
)

echo.
echo [3/5] Installing application dependencies...
if exist "..\requirements.txt" (
    %PYTHON_CMD% -m pip install -r ..\requirements.txt
) else if exist "requirements.txt" (
    %PYTHON_CMD% -m pip install -r requirements.txt
)

if exist "requirements-desktop.txt" (
    %PYTHON_CMD% -m pip install -r requirements-desktop.txt
)

if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Some application dependencies may have failed to install.
    echo Continuing anyway...
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
    echo ==========================================
    echo ERROR: Build failed!
    echo ==========================================
    echo.
    echo Check the error messages above for details.
    echo Common issues:
    echo   - Missing dependencies
    echo   - Antivirus blocking PyInstaller
    echo   - Insufficient disk space
    echo.
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
