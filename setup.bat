@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found. Install Python for Windows and tick Add python.exe to PATH.
    exit /b 1
)
where docker >nul 2>nul
if errorlevel 1 (
    echo ERROR: docker was not found. Install Docker Desktop and start it.
    exit /b 1
)
docker image inspect pyter >nul 2>nul
if errorlevel 1 (
    echo ERROR: the pyter Docker image is missing or Docker Desktop is not running. See README.md.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: could not create .venv.
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env - open it and paste your DeepSeek API key after DEEPSEEK_API_KEY=
)
echo Setup finished.