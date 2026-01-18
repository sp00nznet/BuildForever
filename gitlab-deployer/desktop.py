#!/usr/bin/env python3
"""
BuildForever Desktop Application

This module provides a native Windows desktop application wrapper
for the BuildForever Flask web interface using pywebview.

When run as an executable, it:
1. Starts the Flask server in the background
2. Opens a native Windows window with the web interface
3. Handles graceful shutdown

Usage:
    python desktop.py          # Development
    BuildForever.exe           # Compiled executable
"""

import sys
import os
import threading
import time
import socket
import webbrowser

# Add the current directory to path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

# Configuration
APP_NAME = "BuildForever - GitLab CI/CD Build Farm"
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WIDTH = 800
MIN_HEIGHT = 600


def find_free_port(start_port=5000, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find a free port in range {start_port}-{start_port + max_attempts}")


def wait_for_server(port, timeout=30):
    """Wait for the Flask server to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(('127.0.0.1', port))
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.1)
    return False


def run_flask_server(app, port):
    """Run Flask server in a separate thread."""
    from werkzeug.serving import make_server

    server = make_server('127.0.0.1', port, app, threaded=True)
    server.serve_forever()


def main():
    """Main entry point for desktop application."""
    try:
        import webview
        HAS_WEBVIEW = True
    except ImportError:
        HAS_WEBVIEW = False
        print("pywebview not installed. Falling back to browser mode.")

    # Import Flask app
    from app import create_app
    app = create_app()

    # Find available port
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    print(f"Starting BuildForever on {url}")

    # Start Flask server in background thread
    server_thread = threading.Thread(
        target=run_flask_server,
        args=(app, port),
        daemon=True
    )
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        print("ERROR: Flask server failed to start")
        sys.exit(1)

    print("Server ready!")

    if HAS_WEBVIEW:
        # Create native window with pywebview
        window = webview.create_window(
            APP_NAME,
            url,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_size=(MIN_WIDTH, MIN_HEIGHT),
            resizable=True,
            text_select=True,
        )

        # Start webview (blocks until window is closed)
        webview.start()
    else:
        # Fallback: open in default browser
        print(f"Opening {url} in your default browser...")
        webbrowser.open(url)

        # Keep running until interrupted
        print("Press Ctrl+C to stop the server...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")

    print("BuildForever closed.")


if __name__ == '__main__':
    main()
