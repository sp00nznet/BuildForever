@echo off
REM BuildForever Stop Script for Windows
REM Stops the Flask development server

echo Stopping BuildForever...

REM Find and kill Python/Flask processes
taskkill /F /IM python.exe /FI "WINDOWTITLE eq BuildForever*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *run.py*" 2>nul

REM Stop Docker containers if docker-compose is available
where docker-compose >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    if exist "%~dp0..\docker-compose.yml" (
        cd /d "%~dp0.."
        docker-compose down 2>nul
        echo Docker containers stopped.
    )
)

echo Done.
