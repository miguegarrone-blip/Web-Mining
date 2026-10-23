@echo off
cd /d "%~dp0"
echo Instalando dependencias de Python...
python -m pip install --upgrade httpx "pandas>=2.1.1,<3.0" numpy fast-flights
if errorlevel 1 (
  echo.
  echo No se pudo instalar. Revisa que Python este instalado y en el PATH.
  pause
  exit /b 1
)
echo.
echo Creando tarea programada: un barrido cada 6 horas...
schtasks /Create /TN "Radar Error Fares" /SC HOURLY /MO 6 /TR "\"%~dp02_buscar_ahora.bat\"" /F
echo.
echo Listo. Para abrir el panel, hace doble clic en 3_abrir_panel.bat
pause
