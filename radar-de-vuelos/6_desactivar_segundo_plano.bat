@echo off
cd /d "%~dp0"
echo Apagando el modo segundo plano del radar...
if exist panel.pid (
  for /f %%p in (panel.pid) do taskkill /PID %%p /F >nul 2>&1
  del panel.pid
)
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Radar de vuelos.vbs" >nul 2>&1
schtasks /Create /TN "Radar Error Fares" /SC HOURLY /MO 6 /TR "\"%~dp02_buscar_ahora.bat\"" /F >nul
echo Listo: el panel se apago y ya no arranca solo. Las busquedas cada 6 h siguen, con ventana.
pause
