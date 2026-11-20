@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run setup.bat first.
    exit /b 1
)
echo Analysis: summary of the most recent experiment.
echo The full statistical analysis is added in stage 7.
".venv\Scripts\python.exe" -m src.summarize latest %*
if errorlevel 1 (
    echo FAILED - see the messages above.
    exit /b 1
)
echo DONE.