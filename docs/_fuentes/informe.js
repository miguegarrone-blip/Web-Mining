// Genera docs/informe-tp.docx. Uso: cd docs/_fuentes && npm install && node informe.js
// Las cifras se actualizan a mano en CIFRAS (salen de la base publicada; ver consultas del anexo).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, TableOfContents, PageBreak, Footer, PageNumber,
  ExternalHyperlink,
} = require("docx");

const CIFRAS = {
  corte: "24 de octubre de 2026",
  notas: "5.302", medios: "45", corridas: "11",
  analizadas: "99,9%", conBajada: "4.613", conLd: "4.803", firmadas: "1.276",
  scrapIntentos: "5.548", scrapOk: "5.046", robots: "0",
  gn: "3.724",
  tono: { n: "39%", z: "49%", p: "13%" },
};
const AZUL = "1F5F8B", GRIS = "667069", TINTA = "1C2421";
const MARGEN = 1134;                 // 2 cm (en DXA)
const ANCHO = 11906 - 2 * MARGEN;    // ancho util de A4 (en DXA)

// ---------- ayudas ----------
// texto con **negrita** y `codigo`
function runs(txt, extra = {}) {
  const out = [];
  txt.split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach((p) => {
    if (!p) return;
    if (p.startsWith("**")) out.push(new TextRun({ text: p.slice(2, -2), bold: true, ...extra }));
    else if (p.startsWith("`")) out.push(new TextRun({ text: p.slice(1, -1), font: "Consolas", size: 19, ...extra }));
    else out.push(new TextRun({ text: p, ...extra }));
  });
  return out;
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 100, line: 276 }, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], spacing: { before: 300, after: 140 }, keepNext: true });
const H1c = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)], keepNext: true });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)], keepNext: true });
const B = (t, nivel = 0) => new Paragraph({ numbering: { reference: "viñetas", level: nivel }, children: runs(t), spacing: { after: 40, line: 264 } });
let LISTA = 0;
const NUEVA = () => { LISTA++; return []; };   // ...NUEVA() antes de cada lista numerada para reiniciar en 1
const N = (t) => new Paragraph({ numbering: { reference: "numeros", level: 0, instance: LISTA }, children: runs(t), spacing: { after: 40, line: 264 } });
const CODE = (lineas) => lineas.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l || " ", font: "Consolas", size: 18 })],
  shading: { type: ShadingType.CLEAR, fill: "F1F3EF" },
  spacing: { after: i === lineas.length - 1 ? 160 : 0 }, keepNext: i < lineas.length - 1, keepLines: true,
  indent: { left: 200, right: 200 },
}));
const NOTA = (t) => new Paragraph({
  children: runs(t, { color: TINTA, size: 20 }),
  shading: { type: ShadingType.CLEAR, fill: "E8F0F6" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: AZUL, space: 8 } },
  spacing: { before: 100, after: 140, line: 264 }, indent: { left: 200, right: 200 },
});
const borde = { style: BorderStyle.SINGLE, size: 4, color: "D9DCD5" };
function TABLA(filas, anchos0) {
  const f = ANCHO / anchos0.reduce((a, b) => a + b, 0), anchos = anchos0.map((a) => Math.round(a * f));
  anchos[anchos.length - 1] += ANCHO - anchos.reduce((a, b) => a + b, 0);
  const tot = ANCHO;
  return new Table({
    width: { size: tot, type: WidthType.DXA }, columnWidths: anchos,
    rows: filas.map((f, i) => new TableRow({
      tableHeader: i === 0,
      children: f.map((c, j) => new TableCell({
        width: { size: anchos[j], type: WidthType.DXA },
        borders: { top: borde, bottom: borde, left: borde, right: borde },
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: AZUL } : (i % 2 === 0 ? { type: ShadingType.CLEAR, fill: "F6F7F4" } : undefined),
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: runs(String(c), i === 0 ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 }) })],
      })),
    })),
  });
}
const ESP = () => new Paragraph({ children: [], spacing: { after: 120 } });
const LINK = (texto, url) => new Paragraph({ children: [new ExternalHyperlink({ link: url, children: [new TextRun({ text: texto, style: "Hyperlink" })] })], spacing: { after: 80 } });

// ---------- contenido ----------
const portada = [
  new Paragraph({ children: [], spacing: { before: 1800 } }),
  new Paragraph({ children: [new TextRun({ text: "MAESTRÍA EN CIENCIA DE DATOS · WEB MINING", color: GRIS, size: 20 })], spacing: { after: 240 } }),
  new Paragraph({ children: [new TextRun({ text: "Monitor de medios argentinos", bold: true, size: 56, color: TINTA })], spacing: { after: 120 } }),
  new Paragraph({ children: [new TextRun({ text: "Web mining, análisis de sentimiento y estilo de titulación en 46 medios", size: 30, color: AZUL })], spacing: { after: 600 } }),
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AZUL, space: 4 } }, children: [], spacing: { after: 300 } }),
  P("**Integrantes:** [completar]"),
  P("**Docentes:** [completar]"),
  P("**Fecha:** octubre de 2026"),
  P("**Tablero en línea:** https://miguegarrone-blip.github.io/Web-Mining/"),
  P("**Repositorio:** https://github.com/miguegarrone-blip/Web-Mining"),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ children: [new TextRun({ text: "Contenido", bold: true, size: 32, color: AZUL })], spacing: { after: 200 } }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
];

const cuerpo = [
  H1("1. Resumen"),
  P(`El trabajo construye un **monitor de medios** que cada 30 minutos recolecta los titulares de 46 medios argentinos (diarios, portales digitales, canales de TV, radios y dos fuentes oficiales), **entra a cada nota** para extraer su bajada y sus datos estructurados, y clasifica cada pieza por **tema**, **tono** y **entidades** mencionadas. Con eso mide qué agenda tiene cada medio, con qué tono cubre cada tema y persona, y **cómo titula**: cuánto exagera el título respecto de su propia bajada, cuántos recursos de clickbait usa y qué proporción de sus notas está firmada por un periodista.`),
  P(`Todo corre solo cada 30 minutos en **GitHub Actions**, guarda el histórico en **SQLite** y publica un **tablero web** en GitHub Pages, desde donde también se puede consultar la base con SQL en el navegador. Al ${CIFRAS.corte} la base tenía **${CIFRAS.notas} notas de ${CIFRAS.medios} medios**; el ${CIFRAS.analizadas} ya había sido enriquecido entrando a la página de la nota. El tablero suma comparaciones entre medios: el encuadre de una misma noticia, quién la publica primero, cómo trata cada medio a cada figura y un mapa de las comunidades de medios que comparten agenda.`),
  P(`El modelo de tono combina una regresión logística sobre palabras con las probabilidades de **XLM-RoBERTa** (BERT multilingüe): sobre 340 titulares clasificados a mano llega a **77% de acierto** con validación cruzada (el modelo inicial tenía 70%) y detecta el **84% de las notas negativas** (antes, 65%).`),

  H1("2. Problema y motivación"),
  P("Leer las noticias de un día implica recorrer decenas de portadas que cuentan los mismos hechos con énfasis distintos. Para un lector, un equipo de comunicación o un investigador, las preguntas interesantes no están en una nota aislada sino en el conjunto:"),
  B("¿De qué se habla hoy y qué temas crecen respecto de lo habitual?"),
  B("¿Qué medios cubren más un tema, una persona o una institución, y con qué tono?"),
  B("¿Qué noticias cubre casi todo el ecosistema y cuáles son exclusivas de un medio?"),
  B("¿Qué medios titulan de forma más alarmista o con más recursos de clickbait?"),
  B("¿Cuánto del contenido está firmado y cuánto sale como \"Redacción\"?"),
  P("Responderlas a mano es inviable: el sistema procesa unas 3.000 notas por corrida. La web es, además, un ambiente dinámico: los sitios cambian de estructura, algunos no publican RSS y otros cambian de codificación o de plantilla, lo que obliga a pensar el scraping como un sistema que se monitorea y se mantiene, no como un script que se corre una vez."),

  H1("3. Objetivos"),
  H2("Objetivo general"),
  P("Construir un sistema automático y reproducible que extraiga información de medios argentinos desde la web, la estructure en una base consultable y la convierta en indicadores de agenda, tono y estilo de titulación publicados en un tablero de acceso público."),
  H2("Objetivos específicos"),
  ...NUEVA(),
  N("Recolectar titulares de 46 medios combinando RSS propios y búsquedas de Google News por sitio, con validación y deduplicación."),
  N("Enriquecer cada nota con datos que el RSS no trae: URL real, bajada, autor, sección, palabras clave y largo, extraídos del HTML y del JSON-LD de la página."),
  N("Clasificar tema, tono y entidades, y evaluar el modelo de tono contra etiquetas manuales con validación cruzada."),
  N("Definir indicadores comparables entre medios (agenda, tono, exageración, cebo, transparencia) y publicarlos en un tablero."),
  N("Automatizar la recolección y la publicación, respetando buenas prácticas de crawling (robots.txt, identificación, límite de pedidos)."),

  H1("4. Fuentes de datos"),
  P("Se monitorean 46 medios, clasificados por **alcance** (Rosario, nacional, interior) y **tipo** (diario, digital, TV, radio, oficial). La lista y sus feeds están en el diccionario `F` de `build.py`."),
  TABLA([
    ["Alcance", "Medios", "Ejemplos"],
    ["Rosario", "7", "La Capital, Rosario3, El Ciudadano, Conclusión, Rosarioplus, Rosario Nuestro, Municipalidad de Rosario"],
    ["Nacional", "20", "Clarín, La Nación, Infobae, Página/12, Perfil, Ámbito, El Cronista, TN, C5N, A24, Radio Mitre, Cadena 3"],
    ["Interior", "19", "La Voz, Los Andes, La Gaceta, El Litoral, Río Negro, El Día, Misiones Online, Gobierno de Santa Fe"],
  ], [1600, 1100, 6326]),
  ESP(),
  H2("Dos vías de acceso"),
  B("**RSS propio** (17 medios, 3 de ellos complementados con Google News): el medio publica un feed XML con título, enlace, fecha y, en general, una bajada. Es la vía más limpia."),
  B("**Google News por sitio** (29 medios): para los medios sin RSS útil se consulta el feed de búsqueda de Google News con `site:dominio when:2d`. Devuelve hasta 100 notas recientes por medio, pero con un enlace de redirección de Google en lugar de la URL del medio y sin bajada."),
  P(`En la base, ${CIFRAS.gn} de las ${CIFRAS.notas} notas llegaron por Google News. Sin un paso adicional, esas notas solo tendrían el título: por eso el sistema decodifica cada enlace y entra a la página real (sección 6.3).`),
  NOTA("Por qué no se usa una API de noticias: NewsAPI y similares limitan la cantidad de pedidos y la cobertura de medios regionales; Google Custom Search limita las búsquedas diarias. Uno de los trabajos de 2025 terminó en NewsAPI después de que fallara el scraping directo. Combinar RSS con Google News por sitio da cobertura de 46 medios sin claves ni costo."),

  H1("5. Arquitectura y pipeline"),
  P("El sistema es un pipeline por lotes que corre cada 30 minutos. Todo está en `diarios-del-pais/`; `build.py` orquesta las etapas:"),
  TABLA([
    ["Etapa", "Qué hace", "Módulo"],
    ["1. Crawling de feeds", "Descarga en paralelo los feeds RSS y de Google News de los 46 medios (10 hilos, reintentos con espera creciente).", "build.py"],
    ["2. Validación", "Descarta títulos demasiado cortos o largos, \"no notas\" (\"Videos mobile\", avisos fúnebres), URLs inválidas y fechas imposibles; los descartes van a la tabla cuarentena.", "build.py"],
    ["3. Deduplicación", "Normaliza la URL (sin parámetros de tracking, minúsculas, sin barra final) y el título; una nota se identifica por el hash de su URL canónica.", "build.py"],
    ["4. Scraping de notas", "Decodifica los enlaces de Google News, descarga la página y extrae bajada y JSON-LD (autor, sección, claves, largo).", "enriquecer.py"],
    ["5. Procesamiento de texto", "Temas (reglas + Naive Bayes), entidades (diccionario), tono (palabras + XLM-RoBERTa), puntaje de cebo.", "topics.py, nlp.py, bert.py"],
    ["6. Almacenamiento", "SQLite con retención de 90 días; exportación CSV para Excel o Power BI.", "build.py"],
    ["7. Agregados y tablero", "Calcula indicadores por medio, día, hora, tema y entidad, y genera el HTML del tablero.", "build.py, tpl2.html"],
    ["8. Publicación", "GitHub Actions guarda la base en la rama data-diarios y publica tablero, base y CSV en GitHub Pages.", "workflow"],
  ], [2000, 5326, 1700]),
  ESP(),
  H2("Automatización con GitHub Actions"),
  P("El workflow `.github/workflows/diarios-del-pais.yml` se ejecuta cada 30 minutos por autodisparo (ver más abajo), con un cron de respaldo (`23,53 * * * *`), a mano desde la pestaña Actions y con cada cambio de código. Cada corrida:"),
  ...NUEVA(),
  N("Restaura la base comprimida (`historico.db.gz`) desde la rama `data-diarios`."),
  N("Instala dependencias, incluido PyTorch para CPU, y recupera el modelo BERT de la caché."),
  N("Corre `build.py` con la zona horaria de Buenos Aires."),
  N("Guarda la base actualizada en `data-diarios` con un único commit sin historia, para que el repositorio no crezca."),
  N("Publica en GitHub Pages el tablero (`index.html`), la base (`historico.db`) y el CSV."),
  P("La primera corrida con BERT tarda unos 10 minutos (descarga el modelo y procesa el histórico); las siguientes, entre 3 y 6 minutos."),
  P("**Autodisparo cada 30 minutos:** el cron de GitHub resultó muy irregular en este repositorio (un día corrió 1 de cada 8 veces: GitHub demora y descarta corridas programadas en momentos de carga). Por eso cada corrida, al terminar, espera hasta completar 30 minutos desde su inicio y relanza el workflow con `workflow_dispatch`, que no pasa por el programador del cron. La corrida más nueva es la dueña de la cadena (si aparece otra mientras se espera, la vieja no lanza nada), la cadena sigue aunque el pipeline falle y el cron queda como respaldo."),
  P("**Pruebas automáticas:** `tests/` verifica las funciones de extracción y limpieza (bajadas con código, entidades HTML, caracteres mal decodificados, JSON-LD, robots.txt, firma, cebo, entidades, temas). Corren en paralelo en cada corrida y no frenan la recolección: si fallan, la corrida queda marcada para revisar el scraper."),

  H1("6. Cómo scrapea"),
  H2("6.1 Listados y detalle"),
  P("Siguiendo la distinción vista en clase, el sistema trabaja en dos niveles: las **páginas de listado** (los feeds, que enumeran notas con título, enlace y fecha) y las **páginas de detalle** (cada nota). Los listados se procesan con `feedparser`; el detalle se descarga con `requests` y se extrae con expresiones regulares sobre el HTML."),
  H2("6.2 Crawler \"bien educado\""),
  P("Las clases plantean que un crawler debe ser respetuoso con los sitios. El sistema lo implementa así:"),
  B("**robots.txt:** antes de descargar una nota se lee el robots.txt de su dominio (una vez por dominio y corrida) y se omite cualquier URL no permitida (`urllib.robotparser`). En las corridas registradas hubo 0 bloqueos."),
  B("**Identificación:** el User-Agent se declara como bot y enlaza al tablero: `monitor-de-medios/1.0 (+https://miguegarrone-blip.github.io/Web-Mining/)`."),
  B("**Límite por dominio:** como máximo 2 pedidos simultáneos a un mismo sitio (un semáforo por dominio), con 12 descargas en paralelo en total."),
  B("**Topes por corrida:** hasta 1.200 notas o 7 minutos; lo pendiente se procesa en la corrida siguiente."),
  B("**Reintentos acotados:** los feeds se reintentan ante errores 429 y 5xx con espera creciente; una nota que falla dos veces no se vuelve a pedir."),
  H2("6.3 Resolución de URLs de Google News"),
  P("Los enlaces de Google News (`news.google.com/rss/articles/CBMi…`) codifican la URL real. Se decodifican con la librería `googlenewsdecoder` y, a partir de ahí, se trabaja con la página del medio. La URL real se guarda en `url_real` y el tablero enlaza directo al medio."),
  H2("6.4 Qué se extrae de cada página"),
  B("**Bajada:** la meta `og:description` (o `description` / `twitter:description`). Si no existe, el primer párrafo `<p>` real, después de quitar scripts, estilos y SVG."),
  B("**Datos estructurados (JSON-LD):** casi todos los diarios incrustan un bloque `NewsArticle` en formato schema.org para los buscadores. Se parsea y se toman autor, sección, fecha de modificación, palabras clave y largo del cuerpo. 41 de 44 medios lo publican."),
  B("**Firma:** se distingue una nota firmada por una persona de una firmada como \"Redacción\", \"Newsroom Infobae\" o con el nombre del medio."),
  P(`Resultado acumulado: ${CIFRAS.scrapIntentos} intentos de scraping, ${CIFRAS.scrapOk} páginas descargadas, ${CIFRAS.conBajada} notas con bajada y ${CIFRAS.conLd} con JSON-LD.`),
  H2("6.5 Mantenimiento del scraper"),
  P("Como se vio en clase, mantener scrapers es costoso porque la web cambia. El sistema registra su propio estado para detectar problemas:"),
  B("Tabla **salud**: por corrida y por medio, código HTTP, notas recibidas, notas válidas, latencia y error. Un medio se marca **degradado** si trae menos de la mitad de su mediana y **caído** si no responde."),
  B("Tabla **scraping**: intentos, éxitos, bajadas, JSON-LD y bloqueos por robots.txt por medio."),
  B("Tabla **cuarentena**: cada nota descartada con su motivo (7 días)."),
  P("Esa instrumentación permitió detectar y corregir problemas reales durante el desarrollo:"),
  TABLA([
    ["Problema", "Causa", "Solución"],
    ["Bajadas con código JavaScript", "El respaldo de \"primer párrafo\" tomaba cualquier etiqueta que empezara con <p (por ejemplo, <path o código de un carrusel).", "Solo <p> reales, sin scripts ni estilos; se descarta texto con patrones de código o CSS."],
    ["Símbolos como &amp;quot;", "Sitios que escapan las entidades HTML dos veces.", "Doble decodificación de entidades."],
    ["Letras rotas (\"podrÃ¡\")", "Páginas UTF-8 sin charset declarado, que se leían como Latin-1.", "Decodificar como UTF-8 cuando no hay charset; reparar los tramos rotos ya guardados."],
    ["Descripciones genéricas", "Algunos sitios repiten la misma descripción en todas las notas.", "Se descarta una bajada repetida en más de 3 notas del mismo medio."],
    ["Títulos con \" - Medio\"", "Google News agrega el nombre del medio al título.", "Se corta el sufijo al ingresar."],
  ], [2200, 3413, 3413]),
  ESP(),
  P("Además, en cada corrida se vuelven a depurar las bajadas ya guardadas que presentan esos síntomas, de modo que una corrección del scraper también limpia el histórico."),

  H1("7. Procesamiento de texto"),
  H2("7.1 Preprocesamiento"),
  P("Se normaliza el texto (minúsculas, sin tildes vía descomposición Unicode), se tokeniza con expresiones regulares, se eliminan stopwords en español y números, y se generan bigramas. La representación es una **bolsa de palabras** binaria (presencia o ausencia), es decir, el modelo vectorial visto en clase con los términos tratados como independientes."),
  H2("7.2 Temas"),
  P("Cada nota recibe hasta dos temas entre 15 (política, economía y trabajo, seguridad y justicia, fútbol, espectáculos, internacional, etc.)."),
  B("**Reglas:** diccionarios de palabras, prefijos y frases por tema, aplicados sobre título más bajada. Sumar la bajada redujo la categoría \"Otros\" del 24% al 9%."),
  B("**Supervisión débil con Naive Bayes:** las notas que las reglas sí clasificaron se usan como conjunto de entrenamiento de un Naive Bayes multinomial que se reentrena en cada corrida y asigna tema a las notas \"Otros\" solo si la probabilidad supera 0,9. Sus predicciones nunca se usan para entrenar (columna `tema_fuente`)."),
  H2("7.3 Entidades"),
  P("**Diccionario:** unas 35 personas, instituciones, clubes y empresas con sus alias (por ejemplo, \"canalla\" → Rosario Central) y reglas de desambiguación (\"Banco Central\" no es Rosario Central). Las más mencionadas en el corte fueron Javier Milei, Lionel Messi y el papa León XIV."),
  P("**Reconocimiento de entidades (NER) con spaCy:** el modelo `es_core_news_md` detecta personas e instituciones en título y bajada aunque no estén en el diccionario. Se limpian cargos y artículos (\"el presidente Javier Milei\" → \"Javier Milei\"), nombres de medios, días y genéricos, y se unifican variantes con la forma más larga (\"Colapinto\" → \"Franco Colapinto\"). Una figura se marca como **nueva** si no está en el diccionario, aparece en al menos 4 notas de 3 medios en las últimas 24 horas y tuvo como mucho una mención en los 7 días anteriores. En el corte aparecieron, por ejemplo, la Fundación Faro, Marcelo Trepat y Gonzalo Belloso."),
  H2("7.4 Tono: de un diccionario a BERT"),
  P("El tono mide si **el hecho** es bueno o malo para los involucrados, no la postura del medio. El criterio de etiquetado fue: negativo para un crimen, una crisis o una suba de precios; neutro para información de servicio o agenda; positivo para un logro o una celebración. El modelo evolucionó en tres etapas:"),
  ...NUEVA(),
  N("**Diccionario** de palabras negativas y positivas."),
  N("**Regresión logística** sobre la bolsa de palabras, bigramas y la salida del diccionario, entrenada con notas etiquetadas a mano."),
  N("**Modelo combinado:** los mismos rasgos más las probabilidades de negativo, neutro y positivo que da XLM-RoBERTa (`cardiffnlp/twitter-xlm-roberta-base-sentiment`)."),
  P("Se compararon 8 enfoques sobre **340 titulares etiquetados a mano** con validación cruzada estratificada de 5 pliegues (`tono_bert_eval.py`). Como la muestra se armó estratificada, también se reporta el acierto ponderado por la distribución real de la población:"),
  TABLA([
    ["Modelo", "Acierto", "Ponderado", "F1 macro", "Recall neg."],
    ["Regresión logística (modelo inicial)", "70%", "70%", "0,68", "65%"],
    ["pysentimiento, sin entrenar", "64%", "66%", "0,62", "66%"],
    ["XLM-RoBERTa, sin entrenar", "74%", "76%", "0,72", "77%"],
    ["Embeddings RoBERTuito + reg. logística", "72%", "72%", "0,71", "80%"],
    ["Palabras + pysentimiento", "75%", "76%", "0,73", "88%"],
    ["**Palabras + XLM-RoBERTa (elegido)**", "**77%**", "**78%**", "**0,75**", "**84%**"],
    ["Palabras + ambos BERT", "75%", "76%", "0,73", "85%"],
    ["Solo probabilidades de ambos BERT", "72%", "73%", "0,71", "81%"],
  ], [3826, 1300, 1300, 1300, 1300]),
  ESP(),
  P("Dos hallazgos: un BERT entrenado con tuits (pysentimiento) rinde peor que el modelo simple sobre titulares, porque mide la emoción de quien escribe y no si el hecho es bueno o malo; y la combinación de rasgos propios con BERT supera a cada parte por separado."),
  P("**Aprendizaje activo:** para ampliar las etiquetas donde más rinden, `tono_activo.py` elige los titulares en los que el modelo está más inseguro (menor margen entre las dos clases más probables), descartando casi duplicados y con un máximo de 4 por medio, y arma una planilla para etiquetarlos a mano. Las etiquetas nuevas se suman al entrenamiento y `tono_bert_eval.py` compara el modelo antes y después con los mismos pliegues de validación cruzada, sobre el conjunto ampliado y sobre los 340 originales. Es el esquema de aprendizaje activo visto en clase: el modelo pide ayuda donde duda."),
  P("**Primera ronda (60 titulares):** el modelo coincidía con la etiqueta humana solo en el 42% de esos casos, y al reentrenar con ellos el acierto sobre la muestra representativa se mantuvo en 76% (recall de negativas 84% → 85%). En los 60 casos difíciles el acierto quedó en 37%, casi el azar entre tres clases: son titulares genuinamente ambiguos, donde el tono depende de la interpretación. La ronda no mejoró el modelo, pero delimitó la frontera de ambigüedad del criterio. El acierto y la calibración se siguen midiendo solo sobre los 340 originales, porque los casos activos no son representativos."),
  P("**Calibración:** los porcentajes del tablero no cuentan la etiqueta predicha sino el reparto esperado, corregido según los errores conocidos del modelo (la probabilidad de que una nota sea realmente negativa dado lo que predijo), con un intervalo aproximado. Las etiquetas manuales, cuando existen, reemplazan a la predicción."),
  H2("7.5 Cómo titula cada medio"),
  B("**Exageración:** se calcula el tono del título y el de la bajada por separado. Un título **exagera** cuando es negativo y su bajada, el resumen del propio medio, no lo es. El indicador por medio es la proporción de títulos negativos con bajada que tienen una bajada neutra o positiva."),
  B("**Cebo (clickbait):** se suma un punto por cada rasgo presente en el título: pregunta, exclamación, adjetivo exagerado (\"impactante\", \"insólito\", \"bomba\"), frase de intriga (\"lo que nadie…\", \"el truco\", \"por qué\"), segunda persona (\"tenés\", \"mirá\") o lista (\"5 claves\")."),
  B("**Transparencia:** proporción de notas firmadas por una persona, según el JSON-LD."),
  H2("7.6 Búsqueda por significado"),
  P("Cada nota se representa con un **embedding de oración** (vector de 384 dimensiones) calculado con `paraphrase-multilingual-MiniLM-L12-v2`, que se guarda en la base para las notas de los últimos 7 días. Con la similitud coseno entre embeddings:"),
  B("**Notas parecidas:** cada titular muestra hasta 5 notas de otros medios que cuentan lo mismo (similitud ≥ 0,70), aunque no compartan palabras: por ejemplo, \"Murió una joven embarazada tras ser atacada por su pareja\" (Eldoce) y \"Murió una joven embarazada que había sido quemada por su pareja en Santa Fe\" (La Voz), con similitud 0,85."),
  B("**Búsqueda por significado:** al activarla, el navegador descarga la versión cuantizada del mismo modelo (transformers.js) y los embeddings de las notas (`emb.bin`, 1,2 MB), y ordena las notas por parecido con la consulta. Se verificó que los vectores de Python y del navegador coinciden (coseno ≥ 0,99)."),
  P("Es el modelo vectorial de la clase llevado a un espacio denso: la similitud coseno sigue siendo la medida, pero los vectores capturan significado y no solo palabras compartidas."),
  H2("7.7 Análisis entre medios"),
  P("Además de clasificar cada nota, el sistema compara a los medios entre sí:"),
  B("**Historias compartidas:** las notas de las últimas 48 horas se agrupan cuando cuentan lo mismo, por similitud coseno entre sus vectores TF-IDF (umbral 0,5, comparando cada nota contra la nota semilla del grupo para no encadenar temas distintos)."),
  B("**Encuadre:** para cada historia compartida, el tablero muestra el título de cada medio en orden de publicación, con su tono, sus recursos de cebo y la demora respecto del primero."),
  B("**Primicia:** cuenta cuántas veces cada medio publicó primero una historia que después cubrieron otros."),
  B("**Tono por figura:** matriz medio × figura con el porcentaje de notas negativas, comparado con el promedio de los medios para esa figura."),
  B("**Mapa de medios (minería de estructura):** un grafo cuyos nodos son medios y cuyas aristas unen a los que cubren las mismas historias. El peso de una arista es la cantidad de historias compartidas dividida por las historias del medio más chico, y cada medio conserva sus 3 vínculos más fuertes. Las comunidades se detectan con **propagación de etiquetas** ponderada y el grafo se dibuja con una disposición por fuerzas (Fruchterman-Reingold)."),
  B("**Termómetro de negatividad:** el porcentaje estimado de notas negativas de las últimas 24 horas, en escala de 0 a 100 y con bandas (calmo, moderado, tenso, muy tenso), comparado con el promedio de los días anteriores. El tablero lo acompaña con un **resumen del día** redactado con plantillas a partir de los datos."),

  H1("8. Almacenamiento"),
  P("La base es un archivo **SQLite** (`historico.db`) con retención de 30 días (la versión comprimida debe quedar por debajo del límite de 100 MB por archivo de GitHub; el workflow falla con un aviso si supera 90 MB). Elegirlo simplifica la operación: no requiere servidor, se versiona como un archivo y se puede abrir en el navegador."),
  TABLA([
    ["Tabla", "Contenido"],
    ["items", "Una fila por nota: medio, alcance, tipo, título, URL y URL real, fecha, bajada, temas y su fuente, entidades, tono del título y de la bajada, probabilidades BERT, tono manual, cebo, autor, firma, sección, palabras clave y largo."],
    ["salud", "Estado de cada feed en cada corrida (HTTP, notas, latencia, error)."],
    ["scraping", "Resultado del scraping de notas por medio y corrida."],
    ["cuarentena", "Notas descartadas por validación, con el motivo (7 días)."],
    ["dolar", "Cotización diaria del dólar blue y oficial (argentinadatos.com y dolarapi.com), para cruzar con el clima mediático."],
    ["meta", "Huellas de los modelos vigentes: si cambian, se reclasifica todo el histórico."],
  ], [1600, 7426]),
  ESP(),
  H2("Acceso a los datos"),
  B("**Desde el tablero:** el botón \"Explorar la base (SQL)\" abre la base en **Datasette Lite**, que corre SQLite en el navegador con WebAssembly. Permite navegar tablas, filtrar y escribir consultas SQL sin instalar nada (útil para mostrar en clase)."),
  B("**Descargas:** la base SQLite y un CSV para Excel o Power BI, desde el encabezado del tablero."),
  B("**Local:** `pip install datasette` y `datasette historico.db`."),
  B("**Notebook:** `diarios-del-pais/analisis.ipynb` reproduce con SQL y pandas los análisis principales (tono, agenda, sensacionalismo, transparencia, tono por figura, evolución diaria). Sirve de respaldo para la presentación si falla la conexión."),

  H1("9. Indicadores"),
  TABLA([
    ["Indicador", "Definición", "Dónde se ve"],
    ["Termómetro", "% estimado de notas negativas de las últimas 24 h, de 0 a 100, contra el promedio de los días anteriores.", "Resumen"],
    ["Volumen", "Notas por medio, tema, día y hora (por fecha de publicación, hora argentina).", "Resumen, Tendencias"],
    ["Agenda", "Parte de las notas de cada medio dedicada a cada tema, contra el promedio de los medios.", "Análisis"],
    ["% negativo", "Reparto esperado de tono negativo, calibrado, con intervalo.", "Resumen, Análisis, Monitor"],
    ["Share of voice", "Menciones de una entidad por medio y tipo de medio, con su tono.", "Monitor"],
    ["Cobertura cruzada y encuadre", "Noticias que cuentan varios medios a la vez (TF-IDF y similitud coseno ≥ 0,5), comparadas título por título.", "Resumen, Análisis"],
    ["Primicia", "Veces que un medio publica primero una historia compartida.", "Análisis"],
    ["Tono por figura", "% negativo de cada medio al mencionar a cada figura, contra el promedio.", "Análisis"],
    ["Comunidades", "Grupos de medios que comparten agenda (propagación de etiquetas sobre el grafo de historias compartidas).", "Análisis"],
    ["Alertas", "Temas o entidades con un volumen hoy superior a 2 desvíos de su media diaria.", "Tendencias"],
    ["Exageración", "Títulos negativos cuya bajada no es negativa, sobre los negativos con bajada.", "Cómo titulan"],
    ["Cebo", "% de títulos con al menos un recurso de clickbait.", "Cómo titulan"],
    ["Transparencia", "% de notas firmadas por un periodista.", "Cómo titulan"],
    ["Largo", "Palabras promedio del cuerpo de las notas.", "Cómo titulan"],
    ["Clima mediático y dólar", "% de notas negativas por día junto al dólar blue (dos gráficos con el mismo eje de días) y correlación de Pearson con la variación diaria del blue cuando hay al menos 8 días.", "Tendencias"],
    ["Salud de fuentes", "Estado de cada feed y tasa de éxito del scraping por medio.", "Salud de datos"],
  ], [1900, 5026, 2100]),

  H1("10. El tablero HTML"),
  P("El tablero es una página estática generada en cada corrida (`tpl2.html` con los datos incrustados como JSON). No necesita servidor: se publica en GitHub Pages y funciona igual en el celular. Tiene ocho pestañas:"),
  TABLA([
    ["Pestaña", "Qué muestra"],
    ["Resumen", "Termómetro de negatividad, resumen del día, indicadores, temas con su tono, entidades más mencionadas y las noticias que cubrieron más medios."],
    ["Titulares", "Lista de notas con bajada, buscador por texto o por significado, filtros por medio, alcance, tipo y tema, y notas parecidas de otros medios."],
    ["Por tema", "Volumen por tema y qué dice cada medio sobre el tema elegido."],
    ["Monitor", "Figuras nuevas en la agenda y otras figuras detectadas con NER; seguimiento de una persona, institución o marca (o un texto libre): menciones, medios, tono, temas asociados y últimas menciones."],
    ["Análisis", "Filtros por alcance, tipo, período (24 h a 30 días) y orden. Agenda de cada medio (mapa de calor), tono por medio (barras divergentes con reordenamiento animado), tono por figura, mapa de medios (grafo), temas día por día (carrera de barras), comparador de encuadre, primicia y palabras más repetidas. Al tocar un medio se abre su ficha."],
    ["Cómo titulan", "Filtros por alcance, tipo y orden; mapa del sensacionalismo (cebo contra exageración, con cuadrantes), rankings, ejemplos, transparencia, periodistas y largo de las notas. Cada medio abre su ficha."],
    ["Tendencias", "Alertas, notas por hora con detalle, notas por día con % negativo, mapa de calor de temas y clima mediático contra el dólar."],
    ["Salud de datos", "Estado de cada fuente, notas descartadas y scraping por medio."],
  ], [1900, 7126]),

  H1("11. Resultados preliminares"),
  NOTA(`Cifras al ${CIFRAS.corte}, con pocas horas de histórico. Son ilustrativas del funcionamiento; las conclusiones se consolidan a medida que se acumulan días. Para los indicadores por medio conviene comparar medios entre sí más que leer el valor absoluto.`),
  B(`**Volumen:** ${CIFRAS.notas} notas de ${CIFRAS.medios} medios en ${CIFRAS.corridas} corridas. Los temas más frecuentes fueron política, seguridad y justicia, fútbol, y economía y trabajo; las figuras más mencionadas, Javier Milei, Lionel Messi y el papa León XIV.`),
  B(`**Tono:** ${CIFRAS.tono.n} negativo, ${CIFRAS.tono.z} neutro y ${CIFRAS.tono.p} positivo según el modelo combinado. Los medios con mayor proporción de notas negativas fueron Diario Chaco, La Voz y Eldoce (alrededor del 50%); los de menor, El Chubut (19%), Río Negro y TN (27%).`),
  B("**Cebo:** A24 encabeza con 22% de títulos con recursos de clickbait, seguido por El Destape, Radio Mitre y Eldoce (18–19%). En el otro extremo, Perfil, El Chubut y Rosario Nuestro están por debajo del 3%."),
  B("**Exageración:** El Cronista, Canal 26, Uno Santa Fe y TN tienen la mayor proporción de títulos negativos con bajada no negativa (50–55%); Elonce (7%), El Chubut y Aire de Santa Fe (19–20%), la menor."),
  B(`**Transparencia:** Perfil (92%), Misiones Online (78%), El Cronista (70%) y TN (65%) firman la mayoría de sus notas; Elonce, Radio Mitre, Radio Continental, Rosario3, Rosario Nuestro y La Capital de Mar del Plata no firman ninguna. En total, ${CIFRAS.firmadas} notas firmadas sobre ${CIFRAS.conLd} con JSON-LD.`),
  B("**Encuadre y primicia:** la historia más compartida del corte (el sobreseimiento de Javier y Karina Milei en la causa $Libra) la cubrieron 12 medios; la publicó primero El Cronista y el último llegó 8 horas después. Eldoce fue el medio que más veces publicó primero una historia compartida."),
  B("**Comunidades:** el mapa de medios separa grupos que comparten agenda; por ejemplo, una comunidad reúne a C5N, Canal 26, Clarín, La Nación y La Voz, y otra a medios del interior y de Rosario."),
  B("**Largo:** Ámbito (1.187 palabras promedio) y La Nación (888) publican las notas más extensas."),

  H1("12. Herramientas"),
  TABLA([
    ["Herramienta", "Uso"],
    ["Python 3.12", "Lenguaje del pipeline."],
    ["requests + urllib3 Retry", "Descargas HTTP con reintentos."],
    ["feedparser", "Lectura de feeds RSS y Atom."],
    ["googlenewsdecoder", "Decodificación de enlaces de Google News."],
    ["re, json, urllib.robotparser", "Extracción por expresiones regulares, JSON-LD y robots.txt."],
    ["SQLite", "Base de datos del histórico."],
    ["PyTorch + Hugging Face transformers", "XLM-RoBERTa para el tono."],
    ["scikit-learn, pysentimiento", "Evaluación comparativa de modelos de tono."],
    ["pandas, matplotlib, Jupyter", "Notebook de análisis."],
    ["spaCy (es_core_news_md)", "Reconocimiento de entidades."],
    ["MiniLM multilingüe + transformers.js", "Embeddings de oraciones: notas parecidas y búsqueda por significado en el navegador."],
    ["HTML, CSS y JavaScript sin frameworks", "Tablero estático."],
    ["GitHub Actions", "Ejecución horaria del pipeline."],
    ["GitHub Pages", "Publicación del tablero, la base y el CSV."],
    ["Datasette Lite", "Consulta SQL de la base en el navegador."],
  ], [3200, 5826]),

  H1("13. Ética y aspectos legales"),
  P("Ninguno de los trabajos de referencia de 2025 trata este punto, que forma parte de la definición de un crawler \"bien educado\":"),
  B("**Se respeta robots.txt** de cada sitio y se identifica al bot con un User-Agent que enlaza al proyecto. No se usan técnicas para evadir bloqueos (rotación de IPs, saltos de Cloudflare)."),
  B("**Carga acotada:** como máximo 2 pedidos simultáneos por sitio y una corrida por hora; cada nota se descarga una vez."),
  B("**Derechos de autor:** no se guarda ni se publica el texto completo de las notas. Se almacenan el título, la bajada y metadatos (autor, sección, largo), y el tablero enlaza siempre a la nota original."),
  B("**Datos personales:** los únicos nombres de personas son los de periodistas que firman notas públicas y figuras públicas mencionadas en titulares."),
  B("**Interpretación responsable:** los indicadores de exageración y cebo son mediciones automáticas con error conocido y se publican con esa advertencia; no son un juicio sobre la calidad periodística de un medio."),

  H1("14. Limitaciones"),
  B("**Tono del título, no de la nota:** el modelo clasifica titulares y bajadas; la ironía y el contexto se le escapan. El acierto es de 77% y fue medido con 340 etiquetas de un solo criterio."),
  B("**Bajadas con un modelo de títulos:** el modelo de tono se entrenó con títulos y se aplica también a bajadas, que son más largas; por eso el indicador de exageración sirve para comparar medios más que como valor absoluto."),
  B("**Cobertura de Google News:** devuelve hasta 100 notas por medio y por consulta; en medios muy prolíficos puede perder notas."),
  B("**Temas por diccionario:** requieren mantenimiento; el NER descubre entidades nuevas, pero todavía mezcla algo de ruido (apodos, secciones de los sitios)."),
  B("**Histórico corto:** las alertas necesitan al menos 3 días completos, y los rankings se estabilizan con semanas de datos. La base guarda 30 días."),
  B("**Cron de GitHub:** las ejecuciones programadas se demoran o se saltean en horarios de mucha carga; un disparador externo (cron-job.org) lo resolvería."),
  B("**Historias compartidas:** el agrupamiento por TF-IDF solo mira los títulos; dos títulos muy distintos sobre la misma noticia pueden quedar en grupos separados."),

  H1("15. Trabajo futuro"),
  B("Seguir la evolución de las comunidades del mapa de medios a lo largo de las semanas."),
  B("Con semanas de datos, medir si el clima mediático acompaña al dólar y sumar otros indicadores (inflación, riesgo país)."),
  B("Resumen diario redactado con un modelo de lenguaje y enviado por correo o Telegram."),
  B("Ampliar las etiquetas manuales (con varios anotadores y acuerdo entre ellos) y ajustar un BERT en español con ellas."),

  H1("16. Cómo reproducirlo"),
  ...CODE([
    "git clone https://github.com/miguegarrone-blip/Web-Mining.git",
    "cd Web-Mining/diarios-del-pais",
    "pip install -r requirements.txt",
    "pip install -r requirements-bert.txt  # opcional: BERT",
    "python build.py                       # base, CSV y tablero",
    "python tono_bert_eval.py              # opcional: modelos de tono",
  ]),
  P("En la nube no hace falta nada: el workflow corre solo cada 30 minutos y se puede lanzar a mano desde la pestaña Actions del repositorio."),

  H1("Anexo: consultas SQL de ejemplo"),
  P("Se pueden ejecutar en Datasette Lite desde el botón del tablero."),
  H3("Tono por medio"),
  ...CODE([
    "SELECT medio, COUNT(*) AS notas,",
    "       ROUND(100.0 * AVG(tono_auto = 'n'), 1) AS pct_negativo",
    "FROM items GROUP BY medio HAVING notas >= 50 ORDER BY pct_negativo DESC;",
  ]),
  H3("Cómo titula cada medio"),
  ...CODE([
    "SELECT medio,",
    "       ROUND(100.0 * AVG(cebo >= 1), 1) AS pct_cebo,",
    "       ROUND(100.0 * SUM(firmada = 1) / SUM(ld = 1), 1) AS pct_firmadas",
    "FROM items GROUP BY medio HAVING SUM(ld = 1) >= 30 ORDER BY pct_cebo DESC;",
  ]),
  H3("Títulos negativos con bajada neutra (exageración)"),
  ...CODE([
    "SELECT medio, titulo, bajada FROM items",
    "WHERE tono_auto = 'n' AND tono_bajada = '0'",
    "ORDER BY pub_ms DESC LIMIT 20;",
  ]),
  H3("Menciones de una entidad por medio"),
  ...CODE([
    "SELECT medio, COUNT(*) AS menciones FROM items",
    "WHERE entidades LIKE '%Javier Milei%'",
    "GROUP BY medio ORDER BY menciones DESC;",
  ]),
];

const doc = new Document({
  creator: "Monitor de medios", title: "Monitor de medios argentinos - TP Web Mining",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: "Calibri", size: 22, color: TINTA } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, color: AZUL, font: "Calibri" }, paragraph: { spacing: { before: 120, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: TINTA, font: "Calibri" }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, color: AZUL, font: "Calibri" }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "viñetas", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
    { reference: "numeros", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: MARGEN, bottom: MARGEN, left: MARGEN, right: MARGEN, footer: 500 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: "Monitor de medios argentinos · ", color: GRIS, size: 18 }),
      new TextRun({ children: [PageNumber.CURRENT], color: GRIS, size: 18 })] })] }) },
    children: [...portada, ...cuerpo],
  }],
});

const salida = path.join(__dirname, "..", "informe-tp.docx");
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(salida, b); console.log("generado", salida); });
