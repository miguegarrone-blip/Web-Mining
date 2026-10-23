# Web-Mining

Proyectos de extracción y análisis de datos de la web, pensados para Rosario y Argentina. Cada carpeta es un proyecto independiente, con su propio README.

| Carpeta | Qué hace |
|---|---|
| [`precios-rosario-super/`](precios-rosario-super/) | Monitor de precios de supermercados (Carrefour, Jumbo, Coto, La Gallega, DAR): relevamiento diario completo, comparación entre cadenas, alertas de precios anómalos y una página para buscar y comparar. |
| [`diarios-del-pais/`](diarios-del-pais/) | Monitor de medios: baja titulares de unos 38 medios argentinos, los clasifica por tema, tono y entidades y genera un tablero. |
| [`radar-de-vuelos/`](radar-de-vuelos/) | Radar de "error fares": busca precios de vuelos desde Argentina y detecta tarifas anormalmente bajas. |

## Qué no está en el repo
Las bases de datos y las salidas generadas (por ejemplo `precios.db`, `historico.db`, `fares.sqlite`), los logs, los respaldos y las claves o tokens
(Telegram, APIs). Cada proyecto las crea al correr. Los `.gitignore` los dejan afuera para que no se suban por error.

## Requisitos generales
Python 3 y, según el proyecto, las librerías de su `requirements.txt` o de su README. Los lanzadores `.bat` están pensados para Windows.
