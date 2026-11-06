@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run setup.bat first.
    exit /b 1
)
".venv\Scripts\python.exe" -m harness.run --bug requests-3179 --condition C1 --trials 3 %*
if errorlevel 1 (
    echo FAILED - see the messages above.
    exit /b 1
)
echo DONE - results are in the results folder.