# Documentación del TP

| Archivo | Qué es |
|---|---|
| [`informe-tp.docx`](informe-tp.docx) | Informe del trabajo: cómo funciona, cómo scrapea, herramientas, indicadores, tablero, resultados, ética y limitaciones. |
| [`presentacion-tp.pptx`](presentacion-tp.pptx) | Presentación para la clase (25 diapositivas, con notas del orador). |

Antes de entregar hay que completar los **integrantes** y los **docentes** en la portada de ambos documentos.

## Regenerar con cifras actualizadas

Los documentos se generan con scripts en [`_fuentes/`](_fuentes/):

```
cd docs/_fuentes
npm install
node informe.js         # cifras en la constante CIFRAS del script
node presentacion.js    # datos de los gráficos en datos.json, capturas en img/
```

`datos.json` sale de consultas a la base publicada (ver el anexo del informe). Para el tema de la
presentación, `presentacion.js` usa `apply_theme.js` de la skill de PowerPoint (variable `APPLY_THEME`);
si no está disponible, el archivo se genera igual pero con la paleta estándar de Office.
