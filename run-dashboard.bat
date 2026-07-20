@echo off
REM Dashboard stack: sibling backends + 1 Vite shell (in-process tool mounts).
REM Expects workspace layout:
REM   dashboardTest/
REM     dashboard/                      (this repo — GitHub: dashboard-front)
REM     dashboard-back/
REM     dashboard-boxout-back/
REM     dashboard-simple-parts-back/
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0.."
set "BOXOUT_BACK=%ROOT%\dashboard-boxout-back"
set "SP_BACK=%ROOT%\dashboard-simple-parts-back"
set "DASH_FRONT=%~dp0apps\dashboard"

where wt >nul 2>&1
if errorlevel 1 (
  echo Windows Terminal ^(wt.exe^) not found. Install it from the Microsoft Store or winget.
  exit /b 1
)

if not exist "%BOXOUT_BACK%\app.py" (
  echo [run-dashboard.bat] ERROR: missing "%BOXOUT_BACK%"
  echo Clone https://github.com/maria-datab/dashboard-boxout-back as a sibling folder.
  exit /b 1
)
if not exist "%SP_BACK%\app.py" (
  echo [run-dashboard.bat] ERROR: missing "%SP_BACK%"
  echo Clone https://github.com/maria-datab/dashboard-simple-parts-back as a sibling folder.
  exit /b 1
)
if not exist "%DASH_FRONT%" (
  echo [run-dashboard.bat] ERROR: missing "%DASH_FRONT%"
  exit /b 1
)

echo [run-dashboard.bat] Remote Compute only — not starting rhino.compute.exe
wt new-tab --title "boxout-back" -d "%BOXOUT_BACK%" cmd /k python -m pipenv run dev ; new-tab --title "simple-parts-back" -d "%SP_BACK%" cmd /k python -m pipenv run serve ; new-tab --title "dashboard-front" -d "%DASH_FRONT%" cmd /k npm run dev

echo.
echo Launched dashboard stack ^(no local Rhino Compute^).
echo Open http://127.0.0.1:5173
echo   routes: /boxout , /simple-parts
endlocal
