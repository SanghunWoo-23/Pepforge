@echo off
cd /d "%~dp0"
echo Starting SPPS Planner native Tk UI from source...
python main_launcher.py --tool spps
if errorlevel 1 (
  echo.
  echo Failed to start with "python". Trying py launcher...
  py main_launcher.py --tool spps
)
pause
