@echo off
cd /d "%~dp0"
call config.bat
python error_fare_monitor.py --serve --no-browser >> panel.log 2>&1
