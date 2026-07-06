@echo off
chcp 65001 >nul
cd /d %~dp0

echo ========================================
echo   LeadMakingMachine
echo ========================================
echo.

python main.py run --count 50

echo.
echo Pipeline complete! Press any key to exit...
pause >nul