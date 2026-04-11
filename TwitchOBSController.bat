@echo off
:: Navigate to the folder where the script lives
cd /d "%~dp0"

:: Run the script using the Python executable inside the virtual environment
start "" ".venv\Scripts\pythonw.exe" "script.py"

exit