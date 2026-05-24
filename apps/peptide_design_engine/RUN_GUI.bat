@echo off
setlocal
cd /d "%~dp0"

set PDE_PY=

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
    if %ERRORLEVEL%==0 (
        set PDE_PY=py -3
        goto :FOUND_PY
    )
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
    if %ERRORLEVEL%==0 (
        set PDE_PY=python
        goto :FOUND_PY
    )
)

where python3 >nul 2>nul
if %ERRORLEVEL%==0 (
    python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
    if %ERRORLEVEL%==0 (
        set PDE_PY=python3
        goto :FOUND_PY
    )
)

echo.
echo [ERROR] Python 3.8+ was not found.
echo Use RUN_GUI_CONDA.bat if you prefer conda, or install Python 3.10/3.11.
echo.
pause
exit /b 1

:FOUND_PY
echo.
echo [INFO] Using Python:
%PDE_PY% -c "import sys; print(sys.executable); print(sys.version)"
echo.

echo [INFO] Checking required packages...
%PDE_PY% -c "import numpy, pandas" >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [INFO] Core packages already installed.
    goto :RUN
)

echo [INFO] Installing required packages...
%PDE_PY% -m pip install --upgrade pip
%PDE_PY% -m pip install -r Python\requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Failed to install requirements.
    echo Try INSTALL_REQUIREMENTS.bat or use conda.
    echo.
    pause
    exit /b 1
)

:RUN
echo.
echo [INFO] Starting GUI...
%PDE_PY% Python\desktop_gui.py
pause
