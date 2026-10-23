# Interfaz web de precios (Rosario)

Una página HTML (Tailwind CSS + JavaScript puro, sin build) que se abre **con doble clic, sin servidor ni puertos**,
igual que `rosario.html` de los titulares. Se abre desde `Precios Rosario.html` (carpeta `monitor_precios`).

- **Buscar**: caja de búsqueda y paleta de comandos (`Ctrl K`, `⌘ K` o `/`). Cada resultado es una tarjeta comparativa con todas las
  cadenas, de menor a mayor precio por kg o litro, la más barata resaltada, promos interpretadas (2x1, 70 % 2da, tarjeta…), aviso de
  posible error de precio e historial.
- **Catálogo**: categorías a la izquierda, filtros por supermercado, rango de precio, descuento mínimo y "solo posibles errores de
  precio", grilla con orden dinámico y detalle en un clic.

Estados cubiertos: esqueletos de carga, vacío con sugerencias, coincidencia parcial avisada, error con reintento.

## Cómo se actualiza

Una tarea del Programador de tareas de Windows (`MonitorPreciosRosario`) corre todos los días a las 3:00: relevamiento completo de las
5 cadenas, matching, alertas y regeneración de `data/`. A la mañana abrís el HTML y ya está al día. Si la PC estaba apagada, corre
al encenderse.

## Cómo funciona sin servidor

Los navegadores no permiten leer archivos con `fetch` desde un HTML abierto con doble clic, pero sí cargar scripts. Por eso los datos son scripts:

| Archivo | Contenido | Cuándo se carga |
|---|---|---|
| `data/index.js` | Índice liviano: una fila por producto (nombre, marca, categoría, precio en cada cadena…) | Una vez al abrir. Con esto se busca y filtra |
| `data/d/00.js` … `ff.js` | Detalle completo (ofertas, promos, historial) repartido en 256 archivos por hash del id | Solo los que hagan falta para mostrar un producto |

Con 25.000 productos el índice pesa 2,8 MB y el detalle 18 MB en total. El navegador solo lee unos pocos archivos de detalle por búsqueda.

## Archivos

| Archivo | Rol |
|---|---|
| `index.html` | Estructura y estilos (Tailwind por CDN) |
| `app.js` | Estado, tarjetas, paleta, filtros |
| `search.js` | **Buscador tolerante** con índice invertido, reutilizable y sin dependencias (documentado al inicio del archivo) |
| `search.test.js` | Pruebas del buscador: `node web/search.test.js` |
| `data/` | Generado por `python catalogo.py` (cada noche) |
| `mock/catalogo.mock.json` | Ejemplo chico del detalle de un producto |
| `API_CONTRATO.md` | Contrato de datos |

## El problema de "473 heineken lata"

1. Se separa en palabras y el **orden no importa**.
2. Se ignoran tildes, mayúsculas y signos; `473`, `473cc` y `473ml` son lo mismo, y `1 kg` equivale a `1000 g`.
3. Se toleran errores de tipeo (`cervesa`, `heneiken`) y se autocompleta la última palabra (`heine`).
4. Deben coincidir todas las palabras; si no hay ninguno, se muestran los que coinciden con dos tercios, avisando.
5. Si una palabra **no existe en ningún producto** (por ejemplo la marca), se dice que no está.

## Rendimiento

Con 25.000 productos reales: abrir el catálogo 41 ms, filtrar por categoría 11 ms, ordenar 28 ms. Prueba de escala con 120.000 productos:
índice en 0,9 s y búsquedas de 5 a 15 ms.

## Opcional: el panel (búsqueda en vivo y canasta)

`iniciar_panel.bat` (o el acceso directo `Precios Rosario.lnk`) abre un servidor local solo para dos cosas que un HTML solo no puede hacer:
**buscar en vivo** en las tiendas un producto que no esté en el catálogo, y **armar tu canasta** con el botón "+ canasta". Si lo abrís desde ahí,
aparecen el enlace "Mi canasta" y el botón "Buscar en vivo". No hace falta para usar el catálogo.

## Límites a tener en cuenta

- Tailwind y la tipografía se cargan de internet: sin conexión la página se ve sin estilos.
- Las categorías vienen de la que asigna cada tienda cuando se guardó; si no, de palabras del nombre (aproximado).
- El historial de precios necesita varios días de corridas para mostrar el gráfico.
