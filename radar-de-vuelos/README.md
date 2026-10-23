# Radar de vuelos: detector de "error fares"

Busca precios de vuelos desde Argentina y marca los que están muy por debajo de lo normal para cada ruta. Corre en Windows con Python 3.

## Cómo decide
1. Consulta precios (Google Flights vía `fast-flights`, gratis) y feeds de ofertas (Promociones Aéreas, Fly4free); tiene un modo DEMO con datos sintéticos.
2. Normaliza a USD "todo incluido" comparable (equipaje estimado para low-cost, tasas, percepción de Argentina).
3. Compara contra un historial robusto por ruta, mes de salida y cabina.
4. Marca anomalías con doble regla (z-score robusto y caída frente al percentil 10) y filtros contra falsos positivos.
5. Muestra las alertas en un panel local y, si lo configurás, las envía por Telegram.

## Uso rápido
1. `1_instalar.bat` instala las dependencias una sola vez (`httpx`, `pandas`, `numpy`, `fast-flights`) y crea una tarea programada de Windows ("Radar Error Fares") que busca cada 6 horas.
2. `2_buscar_ahora.bat` hace una búsqueda manual; `3_abrir_panel.bat` abre el panel en `http://localhost:8765`.
3. `4_probar_con_datos_demo.bat` abre el panel con precios inventados, para probar.
4. `5_activar_segundo_plano.bat` deja el panel prendido sin ventana y busca cada 6 horas; `6_desactivar_segundo_plano.bat` lo deshace.

## Configuración
Editá `config.bat`: orígenes, destinos, cabina y cantidad de fechas por ruta (cada combinación es una búsqueda). Para alertas por Telegram completá
`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` **solo en tu copia local: nunca subas esos valores al repo.** Hay más detalle en `LEEME.txt`.

## Qué no está en el repo
`fares.sqlite` (historial de precios), `monitor.log`, `panel.log` y `dashboard_data/` se generan al correr.
