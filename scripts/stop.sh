#!/bin/bash
# BuildForever Stop Script
# Stops the Flask development server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Stopping BuildForever..."

# Find and kill Flask processes
pkill -f "python.*run.py" 2>/dev/null && echo "Flask server stopped." || echo "No Flask server running."

# Stop Docker containers if running via docker-compose
if command -v docker-compose &> /dev/null; then
    if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        cd "$PROJECT_DIR"
        docker-compose down 2>/dev/null && echo "Docker containers stopped." || true
    fi
fi

echo "Done."
