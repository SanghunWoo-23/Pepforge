@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1

rem SPPS Planner V8.0.0 - one entry point: tools, EXE, Installer, verification.
rem Use --no-pause for unattended build. This builds an installer; it does not install SPPS Planner.
set "NO_PAUSE=0"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
set "APP_VERSION=V8.0.0"
set "SETUP_EXE=installer\output\SPPS_Planner_Setup_V8.0.0.exe"
set "SPPS_PLANNER_SELFTEST_OUTPUT=%CD%\dist\SPPS_Planner\runtime_selftest.json"

echo ============================================================
echo SPPS Planner %APP_VERSION% - install build tools and build
 echo Python 3.11/3.12 x64 - EXE - Installer - verification
 echo ============================================================

if not exist "main_launcher.py" goto :missing
if not exist "SPPS_Planner.spec" goto :missing
if not exist "apps\spps_planner_app\spps_planner\engine.py" goto :missing
if not exist "assets\SPPS_Planner_Icon.ico" goto :missing
if not exist "installer\SPPS_Planner_Setup.iss" goto :missing

call :find_python
if defined PY_CMD goto :python_ready
where winget.exe >nul 2>nul
if errorlevel 1 goto :no_winget
echo [TOOLS] Installing 64-bit Python 3.12 (current user)...
winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :fail
call :find_python
if not defined PY_CMD goto :python_not_found

:python_ready
echo [TOOLS] Python runtime:
%PY_CMD% --version
if errorlevel 1 goto :fail
echo [TOOLS] Updating pip/build requirements...
%PY_CMD% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
%PY_CMD% -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto :fail

call :find_iscc
if defined ISCC goto :iscc_ready
where winget.exe >nul 2>nul
if errorlevel 1 goto :no_winget
echo [TOOLS] Installing Inno Setup...
winget install --id JRSoftware.InnoSetup --exact --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo [WARN] User-scope Inno Setup install failed; trying default scope...
  winget install --id JRSoftware.InnoSetup --exact --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :fail
)
call :find_iscc
if not defined ISCC goto :iscc_not_found

:iscc_ready
echo [1/9] Compiling source...
%PY_CMD% -m compileall -q main_launcher.py suite_gui peptiforg_core apps\spps_planner_app\spps_planner
if errorlevel 1 goto :fail_compile

echo [2/9] Checking V8.0.0 release contract...
%PY_CMD% tools\verify_windows_release.py
if errorlevel 1 goto :fail_contract

echo [3/9] Running source functional self-test...
%PY_CMD% -c "import sys; sys.path.insert(0, r'apps\spps_planner_app'); from suite_gui.runtime_selftest import run; import json; r=run(); print(json.dumps(r, ensure_ascii=False, indent=2)); raise SystemExit(0 if r.get('ok') else 1)"
if errorlevel 1 goto :fail_source_selftest

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo [4/9] Building packaged EXE...
%PY_CMD% -m PyInstaller --clean --noconfirm SPPS_Planner.spec
if errorlevel 1 goto :fail_pyinstaller
if not exist "dist\SPPS_Planner\SPPS_Planner.exe" goto :missing_exe

echo [5/9] Checking packaged EXE...
%PY_CMD% tools\verify_windows_release.py --check-exe
if errorlevel 1 goto :fail_exe_contract

if exist "%SPPS_PLANNER_SELFTEST_OUTPUT%" del /q "%SPPS_PLANNER_SELFTEST_OUTPUT%"
echo [6/9] Running packaged EXE self-test...
"%CD%\dist\SPPS_Planner\SPPS_Planner.exe" --self-test
if errorlevel 1 goto :fail_selftest
if not exist "%SPPS_PLANNER_SELFTEST_OUTPUT%" goto :selftest_missing

echo [7/9] Validating packaged self-test report...
%PY_CMD% tools\verify_packaged_runtime.py "%SPPS_PLANNER_SELFTEST_OUTPUT%"
if errorlevel 1 goto :fail_selftest_report

if exist "installer\output" rmdir /s /q "installer\output"
if not exist "installer\output" mkdir "installer\output"
echo [8/9] Building Installer with Inno Setup...
"%ISCC%" "installer\SPPS_Planner_Setup.iss"
if errorlevel 1 goto :fail_installer
if not exist "%SETUP_EXE%" goto :missing_installer

echo [9/9] Checking EXE and Installer...
%PY_CMD% tools\verify_windows_release.py --check-exe --check-installer
if errorlevel 1 goto :fail_final

echo.
echo [OK] SPPS Planner %APP_VERSION% build and static/binary checks completed.
echo [OK] EXE: %CD%\dist\SPPS_Planner\SPPS_Planner.exe
echo [OK] Installer: %CD%\%SETUP_EXE%
echo [INFO] GUI interaction, installation, upgrade and uninstall still require Windows acceptance testing.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:find_python
set "PY_CMD="
py -3.11 -c "import sys,struct; assert sys.version_info[:2]==(3,11) and struct.calcsize('P')==8" >nul 2>nul && set "PY_CMD=py -3.11"
if defined PY_CMD exit /b 0
py -3.12 -c "import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8" >nul 2>nul && set "PY_CMD=py -3.12"
if defined PY_CMD exit /b 0
python -c "import sys,struct; assert sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P')==8" >nul 2>nul && set "PY_CMD=python"
if defined PY_CMD exit /b 0
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8" >nul 2>nul && set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if defined PY_CMD exit /b 0
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -c "import sys,struct; assert sys.version_info[:2]==(3,11) and struct.calcsize('P')==8" >nul 2>nul && set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
exit /b 0

:find_iscc
set "ISCC="
for %%I in (ISCC.exe) do if not "%%~$PATH:I"=="" set "ISCC=%%~$PATH:I"
if defined ISCC exit /b 0
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if defined ISCC exit /b 0
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if defined ISCC exit /b 0
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC exit /b 0
if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if defined ISCC exit /b 0
if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if defined ISCC exit /b 0
if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
exit /b 0

:missing
echo [ERROR] Required source/build input is missing. Extract the complete ZIP before running this BAT.
goto :fail
:python_not_found
echo [ERROR] Python install completed but an x64 3.11/3.12 interpreter could not be found.
echo [INFO] Open a new Command Prompt after installing Python and retry.
goto :fail
:iscc_not_found
echo [ERROR] Inno Setup install completed but ISCC.exe was not found.
echo [INFO] Install Inno Setup 6/7 and retry; the current-user and Program Files paths are checked.
goto :fail
:no_winget
echo [ERROR] A required build tool is missing, and winget is unavailable.
echo [INFO] Install Python 3.11/3.12 x64 and Inno Setup 6/7 manually, then retry.
goto :fail
:fail_compile
echo [ERROR] Source compilation failed.
goto :fail
:fail_contract
echo [ERROR] V8 release contract check failed.
goto :fail
:fail_source_selftest
echo [ERROR] Source functional self-test failed.
goto :fail
:fail_pyinstaller
echo [ERROR] PyInstaller build failed.
goto :fail
:missing_exe
echo [ERROR] Packaged EXE is missing.
goto :fail
:fail_exe_contract
echo [ERROR] EXE release contract verification failed.
goto :fail
:fail_selftest
echo [ERROR] Packaged EXE self-test failed.
goto :fail
:selftest_missing
echo [ERROR] Packaged EXE did not write a runtime self-test report.
goto :fail
:fail_selftest_report
echo [ERROR] Packaged EXE self-test report validation failed.
goto :fail
:fail_installer
echo [ERROR] Inno Setup compilation failed.
goto :fail
:missing_installer
echo [ERROR] Inno Setup did not produce %SETUP_EXE%.
goto :fail
:fail_final
echo [ERROR] Final EXE/Installer verification failed.
goto :fail
:fail
echo [ERROR] Build stopped. Review the FIRST error above.
if "%NO_PAUSE%"=="0" pause
exit /b 1
