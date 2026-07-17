@echo off
REM Dashboard stack: Flask backends + Vite fronts only.
REM Does NOT start local Rhino Compute — both apps use remote Compute from backends\.env
setlocal
cd /d "%~dp0"

set "BOXOUT_BACK=%~dp0backends\boxout"
set "SP_BACK=%~dp0backends\simple-parts"
set "BOXOUT_FRONT=%~dp0apps\boxout"
set "SP_FRONT=%~dp0apps\simple-parts"
set "DASH_FRONT=%~dp0apps\dashboard"

where wt >nul 2>&1
if errorlevel 1 (
  echo Windows Terminal ^(wt.exe^) not found. Install it from the Microsoft Store or winget.
  exit /b 1
)

if not exist "%BOXOUT_BACK%" (
  echo [run-dashboard.bat] ERROR: missing "%BOXOUT_BACK%"
  exit /b 1
)
if not exist "%SP_BACK%" (
  echo [run-dashboard.bat] ERROR: missing "%SP_BACK%"
  exit /b 1
)
if not exist "%BOXOUT_FRONT%" (
  echo [run-dashboard.bat] ERROR: missing "%BOXOUT_FRONT%"
  exit /b 1
)
if not exist "%SP_FRONT%" (
  echo [run-dashboard.bat] ERROR: missing "%SP_FRONT%"
  exit /b 1
)
if not exist "%DASH_FRONT%" (
  echo [run-dashboard.bat] ERROR: missing "%DASH_FRONT%"
  exit /b 1
)

echo [run-dashboard.bat] Remote Compute only — not starting rhino.compute.exe
wt new-tab --title "boxout-back" -d "%BOXOUT_BACK%" cmd /k python -m pipenv run dev ; new-tab --title "simple-parts-back" -d "%SP_BACK%" cmd /k python -m pipenv run serve ; new-tab --title "boxout-front" -d "%BOXOUT_FRONT%" cmd /k npm run dev ; new-tab --title "simple-parts-front" -d "%SP_FRONT%" cmd /k npm run dev ; new-tab --title "dashboard" -d "%DASH_FRONT%" cmd /k npm run dev

echo.
echo Launched dashboard stack ^(no local Rhino Compute^).
echo Open http://127.0.0.1:5173
echo   iframes: boxout :5174 , simple-parts :5175
endlocal
