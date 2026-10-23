# Monitor de medios

Baja titulares de ~38 medios argentinos (RSS y Google News por sitio), los valida,
los clasifica (tema, tono, entidades) y genera `rosario.html`.

- `build.py`: pipeline completo. `topics.py` y `nlp.py`: clasificacion. `tpl2.html`: plantilla del tablero.
- Local: `Actualizar.bat` o `python archivar.py`.
- Nube: `.github/workflows/actualizar.yml` corre cada hora y guarda los datos en la rama `data`.

## Nota para este repositorio
Este proyecto nació como un repo propio y trae `.github/workflows/actualizar.yml`, que corre cada hora en la nube de GitHub y guarda los datos en la rama `data`.
**Dentro de esta carpeta esa automatización está inactiva**: GitHub solo ejecuta los workflows que están en `.github/workflows/` en la raíz del repo.
Para activarla habría que moverla allí y anteponer `diarios-del-pais/` a las rutas que usa (`requirements.txt`, `build.py`).
Los datos (`historico.db`, `historico.csv`) y los tableros generados (`rosario.html`) no se versionan en la rama principal.
