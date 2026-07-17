@echo off
REM Simple-parts backend + frontend. Does NOT start local Rhino Compute when SIMPLE_PARTS_RUN_LOCALLY=false.
setlocal
cd /d "%~dp0"

set "BACK_DIR=%~dp0backends\simple-parts"
set "FRONT_DIR=%~dp0apps\simple-parts"
set "UNIFIED_ENV=%~dp0backends\.env"
set "RHINO_EXE=C:\Users\maria\Documents\dataB\compute\rhino.compute\rhino.compute.exe"

REM Default remote; only start local Compute if SIMPLE_PARTS_RUN_LOCALLY=true
set "USE_LOCAL_COMPUTE=false"
if exist "%UNIFIED_ENV%" (
  for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /i "SIMPLE_PARTS_RUN_LOCALLY=" "%UNIFIED_ENV%"`) do (
    if /i "%%b"=="true" set "USE_LOCAL_COMPUTE=true"
    if /i "%%b"=="1" set "USE_LOCAL_COMPUTE=true"
    if /i "%%b"=="false" set "USE_LOCAL_COMPUTE=false"
    if /i "%%b"=="0" set "USE_LOCAL_COMPUTE=false"
  )
)

where wt >nul 2>&1
if errorlevel 1 (
  echo Windows Terminal ^(wt.exe^) not found. Install it from the Microsoft Store or winget.
  exit /b 1
)

if not exist "%BACK_DIR%" (
  echo [run-simple-parts.bat] ERROR: backend not found at "%BACK_DIR%"
  exit /b 1
)
if not exist "%FRONT_DIR%" (
  echo [run-simple-parts.bat] ERROR: frontend not found at "%FRONT_DIR%"
  exit /b 1
)

if "%USE_LOCAL_COMPUTE%"=="true" (
  if not exist "%RHINO_EXE%" (
    echo [run-simple-parts.bat] ERROR: rhino.compute.exe not found at:
    echo   %RHINO_EXE%
    exit /b 1
  )
  echo [run-simple-parts.bat] LOCAL Compute on :5000 ^(SIMPLE_PARTS_RUN_LOCALLY=true^)
  wt new-tab --title "Rhino Compute" -- "%RHINO_EXE%" --port 5000 --childcount 2 --create-headless-doc true --spawn-on-startup ; new-tab --title "simple-parts-back" -d "%BACK_DIR%" cmd /k python -m pipenv run serve ; new-tab --title "simple-parts-front" -d "%FRONT_DIR%" cmd /k npm run dev
) else (
  echo [run-simple-parts.bat] REMOTE Compute — not starting rhino.compute.exe
  wt new-tab --title "simple-parts-back" -d "%BACK_DIR%" cmd /k python -m pipenv run serve ; new-tab --title "simple-parts-front" -d "%FRONT_DIR%" cmd /k npm run dev
)

echo Launched simple-parts.
endlocal
