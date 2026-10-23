@echo off
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
echo Configurando el radar para que corra en segundo plano...
echo.
echo 1) Busquedas automaticas cada 6 horas, sin ventana
schtasks /Create /TN "Radar Error Fares" /SC HOURLY /MO 6 /TR "wscript.exe \"%~dp0oculto_buscar.vbs\"" /F
echo.
echo 2) Panel que arranca solo al iniciar Windows
> "%STARTUP%\Radar de vuelos.vbs" echo CreateObject("WScript.Shell").Run "wscript.exe ""%~dp0oculto_panel.vbs""", 0, False
echo    Listo.
echo.
echo 3) Acceso directo en el escritorio
> "%USERPROFILE%\Desktop\Radar de vuelos.url" echo [InternetShortcut]
>> "%USERPROFILE%\Desktop\Radar de vuelos.url" echo URL=http://localhost:8765/
echo    Listo: icono "Radar de vuelos" en el escritorio.
echo.
echo 4) Prendiendo el panel ahora
wscript.exe "%~dp0oculto_panel.vbs"
timeout /t 5 >nul
start "" "http://localhost:8765/"
echo.
echo Todo listo. Desde ahora abri el panel con el icono "Radar de vuelos" del escritorio.
pause
