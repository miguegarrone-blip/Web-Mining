# Monitor de medios

Baja titulares de ~46 medios argentinos (RSS y Google News por sitio), los valida,
los clasifica (tema, tono, entidades), los acumula en SQLite y publica un tablero web.

- `build.py`: pipeline completo. `topics.py` y `nlp.py`: clasificacion. `tpl2.html`: plantilla del tablero.
- `tono_entrenar.py`: entrena y evalua el modelo de tono con las notas etiquetadas a mano.
- Local: `Actualizar.bat` o `python archivar.py` (deja `historico.db`, `historico.csv` y `rosario.html` en esta carpeta).

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
