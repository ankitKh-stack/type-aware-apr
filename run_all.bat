@echo off
setlocal
cd /d "%~dp0"

echo === 1 of 3: one end-to-end sample (run.bat) ===
call run.bat
if errorlevel 1 exit /b 1

echo === 2 of 3: demo experiment (run_experiment_demo.bat) ===
call run_experiment_demo.bat
if errorlevel 1 exit /b 1

echo === 3 of 3: analysis (run_analysis.bat) ===
call run_analysis.bat
if errorlevel 1 exit /b 1

echo === ALL DONE ===
echo The full experiment is not part of run_all. Run run_experiment.bat for that.