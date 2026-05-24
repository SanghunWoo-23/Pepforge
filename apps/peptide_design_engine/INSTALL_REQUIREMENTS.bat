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
echo [ERROR] Python 3.8+ not found.
pause
exit /b 1

:FOUND_PY
%PDE_PY% -m pip install --upgrade pip
%PDE_PY% -m pip install -r Python\requirements.txt
pause
