@echo off
REM === Configuracion del Radar (opcional) ===
REM Para recibir alertas por Telegram, completa estas dos lineas. Si las dejas vacias,
REM las alertas igual aparecen en el panel.
set TELEGRAM_BOT_TOKEN=
set TELEGRAM_CHAT_ID=

REM Alcance de la busqueda (cada combinacion = 1 busqueda en Google Flights)
set FARES_ORIGINS=EZE,COR,ROS
set FARES_DESTINATIONS=MIA,MAD,BCN,JFK,FCO,GRU,SCL,CUN,PUJ,BRC
set FARES_CABINS=ECONOMY
set FARES_N_DATES=3
