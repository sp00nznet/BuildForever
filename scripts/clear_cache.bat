@echo off
REM BuildForever Cache Clearing Script for Windows
REM Clears Python bytecode, temporary files, and browser cache artifacts

setlocal enabledelayedexpansion

echo BuildForever Cache Clearing Utility
echo ====================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

echo Project directory: %PROJECT_DIR%
echo.

REM Clear Python bytecode cache
echo Clearing Python bytecode cache...
for /d /r "%PROJECT_DIR%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
for /r "%PROJECT_DIR%" %%f in (*.pyc) do @if exist "%%f" del /q "%%f" 2>nul
for /r "%PROJECT_DIR%" %%f in (*.pyo) do @if exist "%%f" del /q "%%f" 2>nul
for /d /r "%PROJECT_DIR%" %%d in (.pytest_cache) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo   Done.

REM Clear Flask cache
echo Clearing Flask cache...
if exist "%PROJECT_DIR%\gitlab-deployer\instance" rd /s /q "%PROJECT_DIR%\gitlab-deployer\instance" 2>nul
if exist "%PROJECT_DIR%\gitlab-deployer\.webassets-cache" rd /s /q "%PROJECT_DIR%\gitlab-deployer\.webassets-cache" 2>nul
echo   Done.

REM Clear temporary files
echo Clearing temporary files...
for /r "%PROJECT_DIR%" %%f in (*.tmp) do @if exist "%%f" del /q "%%f" 2>nul
for /r "%PROJECT_DIR%" %%f in (*.bak) do @if exist "%%f" del /q "%%f" 2>nul
if exist "%PROJECT_DIR%\tmp" rd /s /q "%PROJECT_DIR%\tmp" 2>nul
if exist "%PROJECT_DIR%\temp" rd /s /q "%PROJECT_DIR%\temp" 2>nul
echo   Done.

REM Clear Ansible cache
echo Clearing Ansible cache...
if exist "%PROJECT_DIR%\ansible\.ansible" rd /s /q "%PROJECT_DIR%\ansible\.ansible" 2>nul
for /r "%PROJECT_DIR%\ansible" %%f in (*.retry) do @if exist "%%f" del /q "%%f" 2>nul
echo   Done.

REM Check for optional flags
if "%1"=="--include-logs" (
    echo Clearing log files...
    if exist "%PROJECT_DIR%\logs\*.log" del /q "%PROJECT_DIR%\logs\*.log" 2>nul
    echo   Done.
)

if "%1"=="--include-terraform" (
    echo Clearing Terraform cache...
    if exist "%PROJECT_DIR%\terraform\.terraform" rd /s /q "%PROJECT_DIR%\terraform\.terraform" 2>nul
    if exist "%PROJECT_DIR%\terraform\.terraform.lock.hcl" del /q "%PROJECT_DIR%\terraform\.terraform.lock.hcl" 2>nul
    echo   Done.
    echo   Note: You will need to run 'terraform init' again.
)

echo.
echo Cache cleared successfully!
echo.
echo Options:
echo   --include-logs      Also clear log files
echo   --include-terraform Also clear Terraform cache (requires re-init)
echo.

endlocal
