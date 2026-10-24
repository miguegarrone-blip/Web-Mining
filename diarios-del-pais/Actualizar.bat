@echo off
cd /d "%~dp0"
echo Bajando titulares de los medios, esto tarda unos segundos...
py -3 archivar.py
if errorlevel 1 (
  echo.
  echo Hubo un error. Mira el detalle en archivar.log
  pause
  exit /b 1
)
echo Listo. Abriendo el tablero...
start "" "%~dp0rosario.html"
