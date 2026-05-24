@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo Pepforge One-Click Build
echo ============================================================
echo This script installs required build/runtime packages, builds

echo Pepforge.exe, and creates the installer wizard.
echo.

REM ------------------------------------------------------------
REM Select Python: prefer 3.11, then 3.12, then default python
REM ------------------------------------------------------------
set "PY_CMD="
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3.11"
if "%PY_CMD%"=="" (
  py -3.12 --version >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3.12"
)
if "%PY_CMD%"=="" (
  python --version >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python"
)
if "%PY_CMD%"=="" (
  echo [ERROR] Python was not found.
  echo Install Python 3.11 or 3.12, then run this script again.
  pause
  exit /b 1
)

echo [INFO] Using Python command: %PY_CMD%
%PY_CMD% --version

echo.
echo ============================================================
echo [1/4] Installing Python packages
echo ============================================================
%PY_CMD% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :pipfail

if exist requirements.txt (
  %PY_CMD% -m pip install -r requirements.txt
  if errorlevel 1 goto :pipfail
)

if exist apps\hotspot_finder\requirements.txt (
  %PY_CMD% -m pip install -r apps\hotspot_finder\requirements.txt
  if errorlevel 1 goto :pipfail
)

if exist apps\peptide_design_engine\requirements.txt (
  %PY_CMD% -m pip install -r apps\peptide_design_engine\requirements.txt
  if errorlevel 1 goto :pipfail
)

if exist apps\peptide_design_engine\Python\requirements.txt (
  %PY_CMD% -m pip install -r apps\peptide_design_engine\Python\requirements.txt
  if errorlevel 1 goto :pipfail
)

if exist apps\spps_planner_app\requirements.txt (
  %PY_CMD% -m pip install -r apps\spps_planner_app\requirements.txt
  if errorlevel 1 goto :pipfail
)

%PY_CMD% -m pip install pyinstaller pyinstaller-hooks-contrib pandas numpy scikit-learn xgboost openpyxl joblib matplotlib pyyaml pillow
if errorlevel 1 goto :pipfail

%PY_CMD% -c "import pandas, numpy, sklearn, xgboost, openpyxl, joblib, webbrowser; print('Required modules OK')"
if errorlevel 1 (
  echo [ERROR] Required modules are still missing.
  echo If your default Python is 3.14, install Python 3.11 or 3.12 and run again.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo [2/4] Building hidden-console Pepforge EXE
echo ============================================================
%PY_CMD% -m PyInstaller --clean --noconfirm --onedir --windowed --name Pepforge ^
  --icon "assets\Pepforge_Icon.ico" ^
  --add-data "apps;apps" ^
  --add-data "suite_gui;suite_gui" ^
  --add-data "peptiforg_core;peptiforg_core" ^
  --add-data "docs;docs" ^
  --add-data "assets;assets" ^
  --collect-all pandas ^
  --collect-all numpy ^
  --collect-all sklearn ^
  --collect-all xgboost ^
  --collect-all openpyxl ^
  --collect-all joblib ^
  --collect-all matplotlib ^
  --collect-all yaml ^
  --hidden-import pandas ^
  --hidden-import numpy ^
  --hidden-import sklearn ^
  --hidden-import xgboost ^
  --hidden-import openpyxl ^
  --hidden-import joblib ^
  --hidden-import webbrowser ^
  --hidden-import json ^
  --hidden-import csv ^
  --hidden-import pathlib ^
  --hidden-import tkinter ^
  --hidden-import tkinter.scrolledtext ^
  --hidden-import tkinter.messagebox ^
  --hidden-import tkinter.filedialog ^
  --hidden-import tkinter.ttk ^
  --hidden-import tkinter.constants ^
  main_launcher.py

if errorlevel 1 (
  echo [ERROR] PyInstaller EXE build failed.
  pause
  exit /b 1
)

if not exist "dist\Pepforge\Pepforge.exe" (
  echo [ERROR] EXE was not created at dist\Pepforge\Pepforge.exe
  pause
  exit /b 1
)

echo.
echo ============================================================
echo [3/4] Checking or installing Inno Setup 7/6
echo ============================================================
set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
  echo [INFO] Inno Setup 7/6 was not found.
  echo [INFO] Trying to install it with winget...
  winget --version >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] winget is not available on this PC.
    echo Install Inno Setup 7 or 6 manually, then run this script again.
    echo Search: Inno Setup download
    pause
    exit /b 2
  )
  winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [ERROR] winget failed to install Inno Setup 6.
    echo Install Inno Setup 7 or 6 manually, then run this script again.
    pause
    exit /b 2
  )
)

set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
  echo [ERROR] Inno Setup still was not found.
  echo Reopen the terminal or install Inno Setup 6 manually.
  pause
  exit /b 2
)

echo [INFO] Inno compiler: %ISCC%

echo.
echo ============================================================
echo [4/4] Building installer wizard
echo ============================================================
"%ISCC%" "installer\Pepforge_Setup.iss"
if errorlevel 1 (
  echo [ERROR] Installer build failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo DONE
echo Installer created here:
echo installer\output\Pepforge_Setup_v0.1.0.exe
echo.
echo EXE folder is also available here:
echo dist\Pepforge\Pepforge.exe
echo ============================================================
pause
exit /b 0

:pipfail
echo.
echo [ERROR] Python package installation failed.
echo Recommended fix: install Python 3.11 or 3.12, then run again.
pause
exit /b 1
