@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo Peptide Design Engine - Conda Install and Run
echo =========================================================
echo.

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH.
    echo Open Anaconda Prompt and run this file again.
    pause
    exit /b 1
)

echo [INFO] Creating/updating conda environment...
conda env update -f environment.yml --prune
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Conda setup failed.
    pause
    exit /b 1
)

echo.
choice /C YN /M "Create a desktop shortcut for Conda Peptide Design Engine?"
if errorlevel 2 goto :SKIP_SHORTCUT

echo [INFO] Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Peptide Design Engine Conda.lnk'); $s.TargetPath='%~dp0RUN_GUI_CONDA.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,70'; $s.Save()"
if %ERRORLEVEL% equ 0 (
    echo [INFO] Desktop shortcut created.
) else (
    echo [WARN] Failed to create shortcut. You can still run RUN_GUI_CONDA.bat manually.
)

:SKIP_SHORTCUT
echo.
echo [INFO] Starting GUI in conda env...
conda run -n peptide_engine python Python\desktop_gui.py
pause
