@echo off
cd /d "%~dp0"
echo Starting Pepforge v3.0.0 from source...
python main_launcher.py
if errorlevel 1 (
  echo.
  echo Failed to start with "python". Trying py launcher...
  py main_launcher.py
)
pause
