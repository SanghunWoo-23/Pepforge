@echo off
setlocal
cd /d "%~dp0"

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH. Use Anaconda Prompt.
    pause
    exit /b 1
)

conda run -n peptide_engine python Python\peptide_cli.py --preset fast --target DELIKFVRWA --outdir outputs\conda_fast_test --no-use-optional-ml
pause
