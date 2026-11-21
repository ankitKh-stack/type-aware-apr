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
echo Running the full experiment: every bug in config\experiment_config.json, conditions C0-C4, 3 trials.
echo This makes many API calls. It stops cleanly at the budget in config\experiment_config.json.
".venv\Scripts\python.exe" -m src.experiment %*
if errorlevel 1 (
    echo FAILED - see the messages above.
    exit /b 1
)
".venv\Scripts\python.exe" -m src.summarize latest
echo DONE - results are in results\experiments.