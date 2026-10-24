# Monitor de medios

Baja titulares de ~46 medios argentinos (RSS y Google News por sitio), los valida,
los clasifica (tema, tono, entidades), los acumula en SQLite y publica un tablero web.

- `build.py`: pipeline completo. `topics.py` y `nlp.py`: clasificacion. `tpl2.html`: plantilla del tablero.
- `enriquecer.py`: entra a cada nota (resuelve las URLs de Google News) y extrae la bajada y el JSON-LD
  `NewsArticle` (autor, seccion, palabras clave, largo). Respeta robots.txt y limita pedidos por dominio.
- `nlp.py`: tono (regresion logistica), entidades y puntaje de "cebo" (clickbait) de cada titulo.
- `tono_entrenar.py`: entrena y evalua el modelo de tono con las notas etiquetadas a mano.
- `tono_bert_eval.py`: compara modelos de tono y exporta el combinado (rasgos + XLM-RoBERTa) a `modelo_tono_bert.json`.
- `tono_activo.py`: aprendizaje activo (elige los titulares mas dudosos para etiquetar y suma las etiquetas a `labels_activo.json`).
- Local: `Actualizar.bat` o `python archivar.py` (deja `historico.db`, `historico.csv` y `rosario.html` en esta carpeta).

## Aprendizaje activo del tono

En vez de etiquetar titulares al azar, se etiquetan los que el modelo combinado tiene mas dudosos
(menor margen entre las dos clases mas probables): cada etiqueta aporta mas informacion.

1. `python tono_activo.py seleccionar --n 60`: entrena el modelo con todo lo etiquetado y elige de `historico.db`
   los 60 titulares de menor margen, sin repetir los ya etiquetados ni casi duplicados (Jaccard de palabras >= 0,5)
   y con hasta 4 por medio. Genera `muestra_activa.xlsx` (para completar) y `muestra_activa.json` (prediccion,
   probabilidades, margen y entropia). La planilla no muestra la prediccion del modelo, para no sesgar.
2. Completar la columna «Tu tono» de `muestra_activa.xlsx` (criterio en la hoja Instrucciones).
3. `python tono_activo.py ingestar muestra_activa.xlsx`: valida y agrega las etiquetas a `labels_activo.json`
   (acumulativo entre rondas); informa el acuerdo modelo-humano y la matriz de confusion en esos casos.
4. `python tono_bert_eval.py`: reentrena sumando `labels_activo.json` y compara el modelo **antes** (sin las etiquetas
   nuevas) y **despues** con los mismos pliegues del conjunto ampliado, y tambien sobre los 340 originales.
   Las filas `6a`/`6b` quedan en `tono_comparacion.json`. Despues se puede volver al paso 1 para otra ronda.

## Tablas de la base (`historico.db`)

- `items`: una fila por nota. Ademas de titulo, medio, fecha, temas, entidades y tono: `url_real`, `bajada`,
  `tono_bajada`, `cebo`, `autor`, `firmada`, `seccion`, `claves`, `largo`, `tema_fuente` (reglas o modelo).
- `salud`: estado de cada feed en cada corrida. `scraping`: resultado del scraping de notas por medio.
- `cuarentena`: notas descartadas por validacion (7 dias). `meta`: huellas de los modelos vigentes.

## En la nube (GitHub Actions + GitHub Pages)

El workflow `.github/workflows/diarios-del-pais.yml` (en la raiz del repo) corre cada hora:

1. Trae la base `historico.db.gz` de la rama `data-diarios`.
2. Corre `build.py` (agrega las notas nuevas, recalcula agregados).
3. Guarda la base actualizada otra vez en `data-diarios` (un solo commit, sin historia).
4. Publica en GitHub Pages el tablero (`index.html`), la base (`historico.db`) y el CSV.

Desde el tablero, el boton **Explorar la base (SQL)** abre la base en
[Datasette Lite](https://lite.datasette.io/), que corre SQLite en el navegador: no hay que instalar nada.

### Activacion (una sola vez, la hace quien administra el repo)

1. Settings → General → Danger zone → **Change visibility → Public** (Pages y Actions sin limite requieren repo publico).
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write permissions**.
4. Actions → "Diarios del país - monitor de medios" → **Run workflow** para la primera corrida.

El tablero queda en `https://<usuario>.github.io/<repo>/`.

### Consultar la base en local

```
pip install datasette
datasette historico.db
```
