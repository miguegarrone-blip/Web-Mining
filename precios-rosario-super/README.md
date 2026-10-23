# Precios Rosario: monitor de supermercados

Baja todos los días el catálogo de 5 cadenas, compara el mismo producto entre ellas (por precio por kg o por litro), detecta precios anómalos y
ofrece una página para buscar y comparar. Funciona sobre Windows con Python 3 y la librería `requests`; no necesita claves ni cuentas (las alertas por Telegram son opcionales y se configuran con variables de entorno).

## Cadenas y cómo se relevan
| Cadena | Método | Script |
|---|---|---|
| Carrefour, Jumbo | API pública de la tienda (VTEX), recorriendo el árbol de categorías | `vtex_full.py` |
| Coto | Listado en JSON de la tienda, por rubro | `coto_full.py` |
| La Gallega, DAR | Búsqueda amplia de la tienda (HTML), con la cookie que fija los productos por página | `asp_full.py` |

Los scripts `*_scraper.py` son el método anterior, por palabras de búsqueda; los usa la **búsqueda en vivo** del panel.

## Cómo funciona
1. `run_all.py` hace el recorrido completo: respaldo y limpieza de la base, relevamiento de las 5 cadenas, control de salud (avisa si una cadena trajo pocos productos),
   equivalencias entre cadenas (`matching.py`: por código de barras y, para DAR, por parecido de texto), alertas de precios anómalos (`anomalies.py`),
   catálogo de la página (`catalogo.py`) y costo de tu canasta (`canasta.py`).
2. Los datos se guardan en SQLite (`precios.db`, no incluida en el repo). `store.py` valida cada fila antes de guardarla.
3. La página `web/index.html` (abrir con `Precios Rosario.html`) lee `web/data/`, que genera `catalogo.py`. No necesita servidor. Ver [`web/README.md`](web/README.md).

## Uso
```
python run_all.py                  # corrida completa (45 a 60 minutos)
python asp_full.py                 # solo La Gallega y DAR (1 minuto)
python catalogo.py                 # regenera la página desde la base
node web/search.test.js            # pruebas del buscador (necesita Node)
```
- **Todos los días:** crear en el Programador de tareas de Windows una tarea `MonitorPreciosRosario` que ejecute `run_daily.bat`. `Actualizar precios.bat` la lanza con un doble clic.
- **Panel opcional** (`iniciar_panel.bat`): servidor local para la búsqueda en vivo y para armar la canasta con el botón "+ canasta".
- **Tu canasta:** `canasta.ejemplo.json` es el ejemplo; la primera vez se copia a `canasta.json`, que es personal y no se sube.
- Los `.bat` usan `C:\Python314\python.exe`; ajustá esa ruta si tu Python está en otro lugar.

## Límites conocidos
- La página muestra solo productos con stock; las tiendas devuelven también los agotados.
- Las categorías vienen de la que asigna cada tienda cuando se guardó; si no, de palabras del nombre (aproximado).
- Los precios son los de la tienda online; no se verificó que correspondan a una sucursal de Rosario en todas las cadenas.
- El matching por texto (DAR) tiene precisión media: en la muestra de control, 84 % de aciertos automáticos.
- Uso personal y a baja velocidad: los scripts esperan entre pedidos y reintentan ante errores del servidor. Respetá los términos de cada sitio.
