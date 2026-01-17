@echo off
REM BuildForever - Windows Startup Script

echo ================================================
echo BuildForever - GitLab Deployer
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or later
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt --quiet

REM Start the Flask application
echo.
echo Starting BuildForever web interface...
echo.
cd gitlab-deployer
python run.py

pause
