@echo off
cd /d "%~dp0"
call config.bat
echo [%date% %time%] Barrido iniciado >> monitor.log
python error_fare_monitor.py --export >> monitor.log 2>&1
