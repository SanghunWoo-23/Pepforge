@echo off
setlocal
cd /d "%~dp0"

where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] conda was not found in PATH. Use Anaconda Prompt.
    pause
    exit /b 1
)

echo [INFO] Parsing AF3 sample output...
conda run -n peptide_engine python Python\peptide_cli.py --parse-af3-folder data\sample_external_outputs\af3_output_example --candidate-map data\templates\candidate_mapping_template.csv --training-db data\training_data.csv --no-run

echo.
echo [INFO] Parsing PRODIGY sample output...
conda run -n peptide_engine python Python\peptide_cli.py --parse-prodigy data\sample_external_outputs\prodigy_output_example --candidate-map data\templates\candidate_mapping_template.csv --training-db data\training_data.csv --no-run

pause
