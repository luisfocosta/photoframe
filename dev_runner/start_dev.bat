@echo off
echo Installing watchdog if not already installed...
pip install watchdog==3.0.0

echo Starting development server with auto-restart...
python dev_runner.py

pause