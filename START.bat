@echo off
cd /d %~dp0
echo Starting Lead Making Machine...
start "API Server" cmd /k "cd %~dp0 && python dashboard/server_leads.py"
start "Pipeline" cmd /k "cd %~dp0 && python run_pipeline.py --count 50 --categories restaurant"
timeout /t 3
start http://localhost:8001
