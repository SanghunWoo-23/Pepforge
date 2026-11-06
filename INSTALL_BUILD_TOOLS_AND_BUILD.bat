@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Single supported Windows setup entrypoint for Pepforge V6.0.0.
rem Science engines are installed into the default WSL2 Linux distribution,
rem not into the frozen Windows EXE or the Windows Python build environment.
if /I "%~1"=="--build" goto :build
if /I "%~1"=="--all" goto :all
if /I "%~1"=="--science" goto :science_install
if /I "%~1"=="--verify-science" goto :science_verify
if /I "%~1"=="--help" goto :help
if not "%~1"=="" goto :help_error

echo ============================================================
echo Pepforge V6.0.0 - Unified Setup
 echo [1] Build Windows EXE + installer (no science engines)
 echo [2] Build Windows EXE + installer, then install science engines in WSL2
 echo [3] Install / update science engines in WSL2 only
 echo [4] Verify science engines in WSL2 only
 echo [5] Exit
 echo ============================================================
choice /c 12345 /n /m "Select [1-5]: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto :science_verify
if errorlevel 3 goto :science_install
if errorlevel 2 goto :all
if errorlevel 1 goto :build
exit /b 1

:all
set "AFTER_BUILD_SCIENCE=1"
set "SCIENCE_ACTION=--install --bootstrap-wsl"
goto :build

:science_install
set "SCIENCE_ACTION=--install --bootstrap-wsl"
goto :science

:science_verify
set "SCIENCE_ACTION=--verify-only"
goto :science

:science
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
if not exist "%~dp0INSTALL_SCIENCE_ENGINES.py" (
  echo [ERROR] INSTALL_SCIENCE_ENGINES.py missing.
  exit /b 1
)
%BASE_PY% "%~dp0INSTALL_SCIENCE_ENGINES.py" %SCIENCE_ACTION% --via-wsl
if errorlevel 1 (
  echo [ERROR] Science engine setup has not completed.
  echo [ACTION] If Ubuntu was just installed, reboot Windows and launch Ubuntu once to set up your Linux user.
  echo [ACTION] Then rerun this BAT ^> menu 3 (Science only).
  echo [INFO] See SCIENCE_ENGINE_INSTALL_GUIDE_KO.md and the Linux installation log.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 2
)
echo [SUCCESS] WSL2 Ubuntu science-engine package checks passed.
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 0

:help_error
echo [ERROR] Unknown command-line option.
:help
echo Usage: INSTALL_BUILD_TOOLS_AND_BUILD.bat [--build ^| --all ^| --science ^| --verify-science ^| --help]
echo   no option: interactive menu
if /I "%~1"=="--help" exit /b 0
exit /b 1

:build
set "ROOT=%CD%"
set "VENV=%ROOT%\.build_venv"
set "BUILD_PY=%VENV%\Scripts\python.exe"

echo ============================================================
echo Pepforge V6.0.0 - Windows Build

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
echo [1/6] Preparing isolated build environment

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
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)
if not exist "%ROOT%\installer\Pepforge.spec" (
  echo [ERROR] installer\Pepforge.spec is missing.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)
if exist "%ROOT%\Pepforge.spec" del /q "%ROOT%\Pepforge.spec" >nul 2>&1

echo.
echo ============================================================
echo [2/6] Validating source before packaging

echo ============================================================
"%BUILD_PY%" -m compileall -q "%ROOT%\main_launcher.py" "%ROOT%\suite_gui" "%ROOT%\peptiforg_core" "%ROOT%\apps"
if errorlevel 1 (
  echo [ERROR] Python source validation failed.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)

echo.
echo ============================================================
echo [3/6] Building lightweight Pepforge EXE

echo ============================================================
echo [INFO] Build spec: %ROOT%\installer\Pepforge.spec
"%BUILD_PY%" -m PyInstaller --clean --noconfirm "%ROOT%\installer\Pepforge.spec"
if errorlevel 1 (
  echo [ERROR] PyInstaller EXE build failed.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)
if not exist "%ROOT%\dist\Pepforge\Pepforge.exe" (
  echo [ERROR] EXE was not created at dist\Pepforge\Pepforge.exe
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)

rem Ship SPPS Planner V8 as a separate frozen executable. Importing its
rem suite_gui modules inside Pepforge.exe would collide with older modules.
echo.
echo ============================================================
echo [4/6] Building standalone SPPS Planner V8 for the integrated installer
echo ============================================================
set "V8_ROOT=%ROOT%\vendor\spps_planner_v8"
if not exist "%V8_ROOT%\SPPS_Planner.spec" (
  echo [ERROR] Missing SPPS Planner V8 build specification.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)
"%BUILD_PY%" -m pip install -r "%V8_ROOT%\requirements.txt"
if errorlevel 1 goto :pipfail
"%BUILD_PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%\.spps_build_dist" --workpath "%ROOT%\.spps_build_work" "%V8_ROOT%\SPPS_Planner.spec"
if errorlevel 1 (
  echo [ERROR] SPPS Planner V8 EXE build failed. Installer not generated.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)
if not exist "%ROOT%\.spps_build_dist\SPPS_Planner\SPPS_Planner.exe" (
  echo [ERROR] SPPS Planner V8 EXE is missing.
  exit /b 1
)
xcopy "%ROOT%\.spps_build_dist\SPPS_Planner\*" "%ROOT%\dist\Pepforge\SPPS_Planner\" /E /I /Y >nul
if errorlevel 1 (
  echo [ERROR] Could not copy SPPS Planner V8 into Pepforge dist.
  exit /b 1
)
if not exist "%ROOT%\dist\Pepforge\SPPS_Planner\SPPS_Planner.exe" exit /b 1

echo.
echo ============================================================
echo [5/6] Checking or installing Inno Setup

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
echo [6/6] Building installer wizard

echo ============================================================
"%ISCC%" "%ROOT%\installer\Pepforge_Setup.iss"
if errorlevel 1 (
  echo [ERROR] Installer build failed.
  if not defined PEPFORGE_NONINTERACTIVE pause
  exit /b 1
)

echo.
echo ============================================================
echo Windows build stage complete.
echo Installer: installer\output\Pepforge_Setup_v6.0.0.exe
echo EXE:       dist\Pepforge\Pepforge.exe
echo ============================================================
if "%AFTER_BUILD_SCIENCE%"=="1" goto :science
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 0

:nopython
echo [ERROR] Python 3.11 or 3.12 was not found.
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 1
:venvfail
echo [ERROR] Could not create isolated build environment.
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 1
:pipfail
echo [ERROR] Build/runtime package installation failed inside .build_venv.
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 1
:noinno
echo [ERROR] Inno Setup 7/6 was not found and could not be installed automatically.
if not defined PEPFORGE_NONINTERACTIVE pause
exit /b 2
