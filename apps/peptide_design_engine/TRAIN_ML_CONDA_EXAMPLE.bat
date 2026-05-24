@echo off
setlocal
cd /d "%~dp0"

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH. Use Anaconda Prompt.
    pause
    exit /b 1
)

conda run -n peptide_engine python Python\peptide_cli.py --train-ml --training-db data\training_data_template.csv --ml-label experimental_binding --models-dir models --no-run
pause
