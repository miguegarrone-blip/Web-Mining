@echo off
cd /d "%~dp0"
set FARES_DB=demo.sqlite
echo Panel de PRUEBA con precios inventados (no se mezcla con los datos reales).
python error_fare_monitor.py --demo --serve --port 8766
pause
