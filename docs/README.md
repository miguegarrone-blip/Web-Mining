# Documentación del TP

| Archivo | Qué es |
|---|---|
| [`informe-tp.pdf`](informe-tp.pdf) · [`.docx`](informe-tp.docx) | Informe del trabajo: cómo funciona, cómo scrapea, herramientas, indicadores, tablero, resultados, ética y limitaciones. |
| [`presentacion-tp.pdf`](presentacion-tp.pdf) · [`.pptx`](presentacion-tp.pptx) | **La Tapa**, la presentación para la clase con forma de diario (24 diapositivas, con notas del orador). |

## Regenerar con cifras actualizadas

Los documentos se generan con scripts en [`_fuentes/`](_fuentes/):

```
cd docs/_fuentes
npm install
python actualizar_datos.py   # baja la base publicada y reescribe datos.json (cifras y titulares reales)
node informe.js              # cifras en la constante CIFRAS del script
node presentacion.js         # arma presentacion-tp.pptx con datos.json, metricas.json e img/
powershell -ExecutionPolicy Bypass -File exportar_pdf.ps1   # PDF de los dos (Word y PowerPoint; correrlo desde PowerShell)
```

Para la presentación sola, antes de la clase: `python actualizar_datos.py`, `node presentacion.js` y
`exportar_pdf.ps1 -Solo presentacion`. Los PDF se ven directo en GitHub; los `.docx` y `.pptx` solo se descargan.

### Qué hace cada pieza de la presentación

- **`actualizar_datos.py`** (solo biblioteca estándar de Python) baja `explorar.db` (últimos 7 días) e
  `historico.db` (base completa) de GitHub Pages y escribe en `datos.json`: totales, scraping, tono total,
  rankings por medio (cebo, negatividad, firmadas, exageración; sin las fuentes oficiales), la historia
  compartida más cubierta (TF-IDF + coseno ≥ 0,5, como el tablero) con 6 recortes de medios distintos y sus horas,
  una historia con encuadres de tonos distintos, titulares reales con cebo (con la posición de cada recurso para
  marcarlo en rojo), ejemplos de «título negativo, bajada neutra», tono por figura, termómetro de las últimas
  24 horas, % negativo por día alineado con el dólar blue (y la correlación), y el resultado de la consulta SQL de
  la demo. Con `--local CARPETA` usa bases ya bajadas.
- **`presentacion.js`** genera el `.pptx` con tres diseños editables (Vista › Patrón de diapositivas: `TAPA`,
  `PAGINA`, `CONTRATAPA`) con marcadores de volanta, título, bajada y sección; las diapositivas están agrupadas en
  secciones (Apertura, Cómo funciona, Qué encontramos, Cierre). Las capturas del tablero se «entintan» a la paleta
  del diario en `img/*-tinta.png`. Usa `apply_theme.js` de la skill de PowerPoint (variable `APPLY_THEME`) para
  los colores del tema; si no está, se genera igual con la paleta estándar de Office.
- **`metricas.json`** (lo genera `metricas.py`) guarda el ancho de cada letra de las fuentes de los recortes: con
  eso el script corta los titulares en renglones y ubica la marca de birome roja sobre la palabra exacta.
- **`exportar_pdf.ps1`** vuelve a guardar la presentación con las **fuentes incrustadas** y exporta el PDF.

### Identidad visual

Papel `F3EEE3`, tinta `141210`, gris `5E5A54` y un solo acento, rojo de imprenta `C8102E` (tono: negativo
`C8102E`, positivo `2E6B3F`, neutro `9A948A`). Cabecera en **Old English Text MT**; titulares en
**Bodoni MT Condensed** (negrita); texto en **Cambria**; datos, horas y volantas en **Consolas**. Old English y
Bodoni son fuentes de Office que se bajan de la nube la primera vez que se usan; por eso el `.pptx` final las lleva
incrustadas y se ve igual en una PC sin conexión.
