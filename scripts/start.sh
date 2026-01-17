#!/bin/bash
# BuildForever - Linux/macOS Startup Script

set -e

echo "================================================"
echo "BuildForever - GitLab Deployer"
echo "================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or later"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt --quiet

# Start the Flask application
echo ""
echo "Starting BuildForever web interface..."
echo ""
cd gitlab-deployer
python run.py
