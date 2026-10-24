# Web-Mining · Monitor de medios argentinos

Trabajo práctico de Web Mining (Maestría en Ciencia de Datos). Todo el proyecto vive en
[`diarios-del-pais/`](diarios-del-pais/): baja cada hora los titulares de 46 medios argentinos,
entra a cada nota para extraer su bajada y sus datos estructurados, clasifica tema, tono
(palabras clave + BERT) y entidades, mide cómo titula cada medio y publica un tablero web.

- **Tablero:** https://miguegarrone-blip.github.io/Web-Mining/
- **Base SQLite:** se puede consultar con SQL desde el botón "Explorar la base (SQL)" del tablero.
- **Documentación del TP:** [`docs/`](docs/).
- **Automatización:** [`.github/workflows/diarios-del-pais.yml`](.github/workflows/diarios-del-pais.yml) (GitHub Actions, cada hora).

## Qué no está en el repo
La base (`historico.db`) y las salidas generadas no se versionan en `main`: la base vive comprimida
en la rama `data-diarios` y el tablero se publica en GitHub Pages.
