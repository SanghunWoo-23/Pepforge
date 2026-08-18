@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "VENV=%ROOT%\.build_venv"
set "BUILD_PY=%VENV%\Scripts\python.exe"

echo ============================================================
echo Pepforge One-Click Build

echo ============================================================
echo Builds Pepforge in an isolated build environment.
echo Your global Python packages are not modified.
echo.

set "BASE_PY="
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "BASE_PY=py -3.11"
if "%BASE_PY%"=="" (
  py -3.12 --version >nul 2>&1
  if not errorlevel 1 set "BASE_PY=py -3.12"
)
if "%BASE_PY%"=="" (
  python --version >nul 2>&1
  if not errorlevel 1 set "BASE_PY=python"
)
if "%BASE_PY%"=="" goto :nopython

echo [INFO] Project root: %ROOT%
echo [INFO] Base Python: %BASE_PY%
%BASE_PY% --version

echo.
echo ============================================================
echo [1/5] Preparing isolated build environment

echo ============================================================
if not exist "%BUILD_PY%" (
  %BASE_PY% -m venv "%VENV%"
  if errorlevel 1 goto :venvfail
)
"%BUILD_PY%" -m pip install --upgrade pip wheel "setuptools<82"
if errorlevel 1 goto :pipfail
"%BUILD_PY%" -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :pipfail
"%BUILD_PY%" -m pip install pyinstaller pyinstaller-hooks-contrib
if errorlevel 1 goto :pipfail
"%BUILD_PY%" -c "import pandas,numpy,openpyxl,joblib,yaml,PIL,rdkit; print('Core runtime modules OK')"
if errorlevel 1 goto :pipfail

if not exist "%ROOT%\main_launcher.py" (
  echo [ERROR] main_launcher.py is missing from project root:
  echo %ROOT%
  pause
  exit /b 1
)
if not exist "%ROOT%\installer\Pepforge.spec" (
  echo [ERROR] installer\Pepforge.spec is missing.
  pause
  exit /b 1
)
if exist "%ROOT%\Pepforge.spec" del /q "%ROOT%\Pepforge.spec" >nul 2>&1

echo.
echo ============================================================
echo [2/5] Validating source before packaging

echo ============================================================
"%BUILD_PY%" -m compileall -q "%ROOT%\main_launcher.py" "%ROOT%\suite_gui" "%ROOT%\peptiforg_core" "%ROOT%\apps"
if errorlevel 1 (
  echo [ERROR] Python source validation failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo [3/5] Building lightweight Pepforge EXE

echo ============================================================
echo [INFO] Build spec: %ROOT%\installer\Pepforge.spec
"%BUILD_PY%" -m PyInstaller --clean --noconfirm "%ROOT%\installer\Pepforge.spec"
if errorlevel 1 (
  echo [ERROR] PyInstaller EXE build failed.
  pause
  exit /b 1
)
if not exist "%ROOT%\dist\Pepforge\Pepforge.exe" (
  echo [ERROR] EXE was not created at dist\Pepforge\Pepforge.exe
  pause
  exit /b 1
)

echo.
echo ============================================================
echo [4/5] Checking or installing Inno Setup

echo ============================================================
set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
  winget --version >nul 2>&1
  if errorlevel 1 goto :noinno
  winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :noinno
)
set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" goto :noinno

echo [INFO] Inno compiler: %ISCC%

echo.
echo ============================================================
echo [5/5] Building installer wizard

echo ============================================================
"%ISCC%" "%ROOT%\installer\Pepforge_Setup.iss"
if errorlevel 1 (
  echo [ERROR] Installer build failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo DONE
echo Installer: installer\output\Pepforge_Setup_v3.0.0.exe
echo EXE:       dist\Pepforge\Pepforge.exe
echo ============================================================
pause
exit /b 0

:nopython
echo [ERROR] Python 3.11 or 3.12 was not found.
pause
exit /b 1
:venvfail
echo [ERROR] Could not create isolated build environment.
pause
exit /b 1
:pipfail
echo [ERROR] Build/runtime package installation failed inside .build_venv.
pause
exit /b 1
:noinno
echo [ERROR] Inno Setup 7/6 was not found and could not be installed automatically.
pause
exit /b 2
