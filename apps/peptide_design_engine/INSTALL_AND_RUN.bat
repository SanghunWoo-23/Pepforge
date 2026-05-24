@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo Peptide Design Engine - Install and Run
echo =========================================================
echo.

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

echo [ERROR] Python 3.8+ was not found.
echo Install Python 3.10/3.11 or use SETUP_CONDA_ENV.bat + RUN_GUI_CONDA.bat.
pause
exit /b 1

:FOUND_PY
echo [INFO] Python selected:
%PDE_PY% -c "import sys; print(sys.executable); print(sys.version)"
echo.

echo [INFO] Checking packages...
%PDE_PY% -c "import numpy, pandas" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing requirements...
    %PDE_PY% -m pip install --upgrade pip
    %PDE_PY% -m pip install -r Python\requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Requirements install failed.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Required packages already installed.
)

echo.
choice /C YN /M "Create a desktop shortcut for Peptide Design Engine?"
if errorlevel 2 goto :SKIP_SHORTCUT

echo [INFO] Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Peptide Design Engine.lnk'); $s.TargetPath='%~dp0RUN_GUI.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,70'; $s.Save()"
if %ERRORLEVEL% equ 0 (
    echo [INFO] Desktop shortcut created.
) else (
    echo [WARN] Failed to create shortcut. You can still run RUN_GUI.bat manually.
)

:SKIP_SHORTCUT
echo.
echo [INFO] Starting GUI...
%PDE_PY% Python\desktop_gui.py
pause
