@echo off
chcp 65001 >nul
title Actualizar precios Rosario
echo.
for /f %%s in ('powershell -nologo -noprofile -command "(Get-ScheduledTask -TaskName MonitorPreciosRosario).State"') do set ESTADO=%%s

if /i "%ESTADO%"=="Running" (
    echo   Ya hay una actualizacion en curso. No hace falta hacer nada:
    echo   cuando termine, abri "Precios Rosario.html" o apreta F5.
    goto fin
)

schtasks /run /tn "MonitorPreciosRosario" >nul 2>&1
if errorlevel 1 (
    echo   No se pudo iniciar la tarea "MonitorPreciosRosario".
    echo   Revisa que exista en el Programador de tareas de Windows.
    goto fin
)

echo   Actualizacion iniciada. Corre en segundo plano.
echo.
echo   - Tarda entre 45 y 60 minutos.
echo   - No apagues ni suspendas la PC mientras tanto.
echo   - Cuando termine, abri "Precios Rosario.html" o apreta F5.
echo   - Avance: carpeta "logs" ^> run_AAAA-MM-DD.log

:fin
echo.
timeout /t 20 >nul
