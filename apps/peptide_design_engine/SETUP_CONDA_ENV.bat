@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo Peptide Design Engine - Conda research environment setup
echo =========================================================
echo.

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH.
    echo Please open this folder from Anaconda Prompt, then run this file again.
    echo.
    pause
    exit /b 1
)

echo [INFO] Creating/updating peptide_engine environment...
conda env update -f environment.yml --prune

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] conda env update failed.
    echo Try manually:
    echo   conda env create -f environment.yml
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Environment ready.
echo Run GUI with:
echo   RUN_GUI_CONDA.bat
echo.
pause
