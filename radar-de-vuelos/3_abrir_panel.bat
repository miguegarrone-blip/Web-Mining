@echo off
cd /d "%~dp0"
call config.bat
echo Abriendo el panel en http://localhost:8765 ...
echo Deja esta ventana abierta mientras uses el panel. Cerrala para apagarlo.
python error_fare_monitor.py --serve
pause
