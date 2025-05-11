@echo off
echo === PolyAgent Launcher for Windows ===
echo Setting up environment...

REM Set the Python path
set PYTHONPATH=.

REM Enable async mode which is compatible with Windows
set USE_ASYNC=true

REM Check if DRY_RUN is set by user in .env
findstr /C:"DRY_RUN=false" .env >nul
if %errorlevel% equ 0 (
    echo DRY_RUN is set to FALSE - LIVE MODE ENABLED
    echo REAL TRANSACTIONS WILL BE EXECUTED!
    echo.
    set DRY_RUN=false
) else (
    echo DRY_RUN is set to TRUE - SIMULATION MODE ENABLED
    echo No real transactions will occur.
    echo.
    set DRY_RUN=true
)

echo Starting PolyAgent...
echo.

python -m agents.application.trade

echo.
echo PolyAgent has stopped running.
pause 