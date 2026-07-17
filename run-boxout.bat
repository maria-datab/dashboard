@echo off
REM Boxout backend + frontend. Does NOT start local Rhino Compute (uses BOXOUT_COMPUTE_* from backends\.env).
setlocal
cd /d "%~dp0"

set "BACK_DIR=%~dp0backends\boxout"
set "FRONT_DIR=%~dp0apps\boxout"

where wt >nul 2>&1
if errorlevel 1 (
  echo Windows Terminal ^(wt.exe^) not found. Install it from the Microsoft Store or winget.
  exit /b 1
)

if not exist "%BACK_DIR%" (
  echo [run-boxout.bat] ERROR: backend not found at "%BACK_DIR%"
  exit /b 1
)
if not exist "%FRONT_DIR%" (
  echo [run-boxout.bat] ERROR: frontend not found at "%FRONT_DIR%"
  exit /b 1
)

echo [run-boxout.bat] Remote Compute only — not starting rhino.compute.exe
wt new-tab --title "boxout-back" -d "%BACK_DIR%" cmd /k python -m pipenv run dev ; new-tab --title "boxout-front" -d "%FRONT_DIR%" cmd /k npm run dev

echo Launched boxout ^(no local Rhino Compute^).
endlocal
