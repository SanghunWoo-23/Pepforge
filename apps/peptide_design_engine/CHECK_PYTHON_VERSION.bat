@echo off
setlocal
echo Checking Python versions...
echo.

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [py -3]
    py -3 --version
    py -3 -c "import sys; print('Executable:', sys.executable); print('Version:', sys.version)"
    echo.
) else (
    echo py launcher not found.
    echo.
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [python]
    python --version
    python -c "import sys; print('Executable:', sys.executable); print('Version:', sys.version)"
    echo.
) else (
    echo python command not found.
    echo.
)

where python3 >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [python3]
    python3 --version
    python3 -c "import sys; print('Executable:', sys.executable); print('Version:', sys.version)"
    echo.
) else (
    echo python3 command not found.
    echo.
)

pause
