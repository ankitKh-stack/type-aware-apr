@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run setup.bat first.
    exit /b 1
)
if not exist ".env" (
    echo ERROR: .env not found. Run setup.bat, then paste your DeepSeek API key into .env.
    exit /b 1
)
echo Running the demo experiment: requests-3179, conditions C0-C4, 1 trial each (a few cents at most).
".venv\Scripts\python.exe" -m src.experiment --bugs requests-3179 --trials 1 %*
if errorlevel 1 (
    echo FAILED - see the messages above.
    exit /b 1
)
".venv\Scripts\python.exe" -m src.summarize latest
echo DONE - results are in results\experiments.