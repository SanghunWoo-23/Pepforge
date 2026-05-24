@echo off
setlocal
cd /d "%~dp0"

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH.
    echo Open Anaconda Prompt and run:
    echo   SETUP_CONDA_ENV.bat
    echo   RUN_GUI_CONDA.bat
    pause
    exit /b 1
)

echo [INFO] Checking conda environment...
conda run -n peptide_engine python -c "import sys, numpy, pandas; print(sys.executable); print(sys.version)" 
if %ERRORLEVEL% neq 0 (
    echo.
    echo [INFO] peptide_engine env is missing or incomplete.
    echo [INFO] Running setup now...
    conda env update -f environment.yml --prune
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create/update conda env.
        pause
        exit /b 1
    )
)

echo.
echo [INFO] Starting GUI in conda env...
conda run -n peptide_engine python Python\desktop_gui.py
pause
