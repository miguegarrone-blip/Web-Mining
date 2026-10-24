// Genera docs/presentacion-tp.pptx. Uso: cd docs/_fuentes && npm install && node presentacion.js
// Datos de los graficos: datos.json (consultas a la base publicada). Capturas del tablero: img/.
const path = require("path");
const fs = require("fs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const pptxgen = require("pptxgenjs");
const fa = require("react-icons/fa");

const APPLY_THEME = process.env.APPLY_THEME ||
  "C:/Users/SBI/.claude/skills/synced/f4dffbae-5dfb-49d8-819c-bcd5bbdb69f2_aed8e124-858a-4b29-a69c-3fa9ddd3cd98/pptx/scripts/apply_theme.js";
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "datos.json"), "utf-8"));
const IMG = (f) => path.join(__dirname, "img", f);

// ---------- tema: papel de diario, tinta y rojo de titular ----------
const HEX = { tinta: "1A1A1A", papel: "FFFFFF", gris: "6B6B6B", grisClaro: "F2F2F0", rojo: "C8102E", azul: "1F5F8B", verde: "3D8A5A", neutro: "9AA29C", linea: "D9D9D6" };
const THEME = {
  name: "Diario", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: HEX.tinta, lt1: HEX.papel, dk2: "2B2B2B", lt2: HEX.grisClaro, accent1: HEX.rojo, accent2: HEX.azul, accent3: HEX.gris,
            accent4: HEX.verde, accent5: "B5483A", accent6: "E0A100", hlink: HEX.azul, folHlink: "6D2E46" },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Monitor de medios argentinos";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "PORTADA", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 1.6, w: 9, h: 0.4, fontSize: 14, bold: true, color: C.accent1, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.1, w: 11, h: 2.0, fontSize: 54, bold: true, color: C.background1, fontFace: "Cambria", valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.3, w: 10, h: 1.0, fontSize: 20, color: C.background2, margin: 0, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENIDO", background: { color: C.background1 },
  margin: [0.5, M, 0.6, M],
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.4, w: 9, h: 0.35, fontSize: 12, bold: true, color: C.accent1, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.75, w: W - 2 * M, h: 1.15, fontSize: 32, bold: true, color: C.text1, fontFace: "Cambria", valign: "top", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Monitor de medios argentinos · Web Mining", options: { x: M, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent3, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: HEX.gris, align: "right" },
});

// ---------- ayudas ----------
async function icono(Icon, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Icon, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
const T = (s, txt, o) => s.addText(txt, { isTextBox: true, fontFace: "Calibri", color: HEX.tinta, margin: 0, valign: "top", ...o });
function contenido(sec, kicker, titulo, notas) {
  const s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: sec });
  s.addText(kicker, { placeholder: "kicker" });
  s.addText(titulo, { placeholder: "title" });
  if (notas) s.addNotes(notas);
  return s;
}
function tarjeta(s, x, y, w, h, objName) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: HEX.grisClaro }, line: { color: HEX.grisClaro }, objectName: objName });
}
function stat(s, x, y, w, numero, etiqueta, color = HEX.rojo) {
  T(s, numero, { x, y, w, h: 1.0, fontSize: 60, bold: true, fontFace: "Cambria", color });
  T(s, etiqueta, { x, y: y + 1.05, w, h: 0.8, fontSize: 15, color: HEX.gris });
}
const ejeComun = {
  catAxisLabelColor: HEX.tinta, valAxisLabelColor: HEX.gris, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: HEX.tinta,
  catGridLine: { style: "none" }, valAxisHidden: true, catAxisLineShow: false, showValue: true, showLegend: false,
};
function barras(s, filas, { x, y, w, h, color = HEX.azul, resaltar = [], sufijo = "%" }) {
  // barras horizontales de una serie; las categorias en `resaltar` van en rojo (dos series apiladas)
  const nombres = filas.map((f) => f[0]).reverse(), vals = filas.map((f) => f[1]).reverse();
  const a = vals.map((v, i) => (resaltar.includes(nombres[i]) ? 0 : v)), b = vals.map((v, i) => (resaltar.includes(nombres[i]) ? v : 0));
  s.addChart(pres.charts.BAR, [{ name: "medios", labels: nombres, values: a }, { name: "destacado", labels: nombres, values: b }], {
    x, y, w, h, barDir: "bar", barGrouping: "stacked", barGapWidthPct: 45, chartColors: [color, HEX.rojo],
    ...ejeComun, dataLabelPosition: "inEnd", dataLabelFormatCode: `0;;;`, dataLabelColor: HEX.papel, dataLabelFontBold: true,
    valGridLine: { style: "none" }, valAxisMaxVal: Math.max(...vals) * 1.05, objectName: "grafico",
  });
  void sufijo;
}

(async () => {
  const ic = {
    question: await icono(fa.FaQuestion, HEX.papel), robot: await icono(fa.FaRobot, HEX.rojo), id: await icono(fa.FaIdBadge, HEX.rojo),
    gauge: await icono(fa.FaTachometerAlt, HEX.rojo), redo: await icono(fa.FaRedo, HEX.rojo), tags: await icono(fa.FaTags, HEX.azul),
    users: await icono(fa.FaUserTie, HEX.azul), smile: await icono(fa.FaBalanceScale, HEX.azul), rss: await icono(fa.FaRss, HEX.rojo),
    google: await icono(fa.FaGoogle, HEX.azul), arrow: await icono(fa.FaArrowRight, HEX.gris), check: await icono(fa.FaCheck, HEX.verde),
    warn: await icono(fa.FaExclamationTriangle, HEX.rojo),
  };

  // ===== 1. Portada =====
  pres.addSection({ title: "Apertura" });
  let s = pres.addSlide({ masterName: "PORTADA", sectionTitle: "Apertura" });
  s.addText("WEB MINING · MAESTRÍA EN CIENCIA DE DATOS", { placeholder: "kicker" });
  s.addText("¿Cómo nos cuentan las noticias?", { placeholder: "title" });
  s.addText("Un monitor automático de 46 medios argentinos: agenda, tono y estilo de titulación", { placeholder: "body" });
  T(s, "Integrantes: [completar]   ·   Octubre 2026", { x: M, y: 6.6, w: 10, h: 0.4, fontSize: 14, color: HEX.neutro });
  s.addNotes("Presentación. La pregunta del título es el hilo: cada día los medios cuentan los mismos hechos con énfasis distintos, y queremos medirlo de forma automática.");

  // ===== 2. Problema =====
  pres.addSection({ title: "Problema" });
  s = contenido("Problema", "EL PROBLEMA", "Un mismo día, contado de 46 maneras distintas",
    "Nadie puede leer 3.000 titulares por hora. Las preguntas interesantes no están en una nota sino en el conjunto. Estas cinco preguntas guían todo el trabajo.");
  const preguntas = ["¿De qué se habla hoy y qué crece respecto de lo habitual?", "¿Qué medios cubren un tema o una persona, y con qué tono?",
    "¿Qué noticias cubre todo el ecosistema y cuáles son exclusivas?", "¿Quién titula de forma más alarmista o con más clickbait?", "¿Cuánto contenido está firmado y cuánto sale como \"Redacción\"?"];
  preguntas.forEach((q, i) => {
    const y = 2.15 + i * 0.88;
    s.addShape(pres.shapes.OVAL, { x: M, y, w: 0.55, h: 0.55, fill: { color: HEX.rojo }, line: { color: HEX.rojo }, objectName: "pregunta-" + i });
    s.addImage({ data: ic.question, x: M + 0.15, y: y + 0.15, w: 0.25, h: 0.25 });
    T(s, q, { x: M + 0.8, y: y + 0.06, w: 6.6, h: 0.5, fontSize: 17, valign: "middle" });
  });
  tarjeta(s, 8.4, 2.15, 4.33, 4.3, "dato");
  T(s, "≈3.000", { x: 8.75, y: 2.6, w: 3.7, h: 1.1, fontSize: 66, bold: true, fontFace: "Cambria", color: HEX.rojo });
  T(s, "titulares por corrida, de 46 medios, cada hora", { x: 8.75, y: 3.75, w: 3.7, h: 0.9, fontSize: 17, color: HEX.tinta });
  T(s, "Leerlos a mano es inviable: hay que extraerlos, estructurarlos y medirlos de forma automática.", { x: 8.75, y: 4.8, w: 3.7, h: 1.3, fontSize: 14, color: HEX.gris });

  // ===== 3. Que construimos =====
  s = contenido("Problema", "LA SOLUCIÓN", "Un monitor que corre solo, cada hora, y publica todo",
    "Tres números para fijar la escala. Todo corre en GitHub Actions sin intervención; el tablero y la base son públicos.");
  stat(s, M, 2.4, 3.7, "46", "medios: diarios, portales, TV, radios y fuentes oficiales");
  stat(s, M + 4.2, 2.4, 3.7, `${D.tot[0].toLocaleString("es-AR")}`, "notas en la base, con tema, tono, entidades y estilo de título");
  stat(s, M + 8.4, 2.4, 3.7, "24/7", "GitHub Actions cada hora; tablero y base SQL publicados en GitHub Pages");
  tarjeta(s, M, 5.1, W - 2 * M, 1.4, "frase");
  T(s, [{ text: "Web mining de punta a punta: ", options: { bold: true } }, { text: "crawling de feeds, scraping de cada nota, procesamiento de lenguaje con BERT, base de datos histórica e indicadores comparables entre medios." }],
    { x: M + 0.35, y: 5.35, w: W - 2 * M - 0.7, h: 0.9, fontSize: 18, valign: "middle" });

  // ===== 4. Pipeline =====
  pres.addSection({ title: "Cómo funciona" });
  s = contenido("Cómo funciona", "ARQUITECTURA", "Seis etapas, de los feeds al tablero",
    "Recorrer el flujo de izquierda a derecha. Remarcar que el paso 3, entrar a cada nota, es lo que convierte esto en web mining real y no solo lectura de RSS.");
  const etapas = [["Feeds", "RSS y Google News de 46 medios, en paralelo"], ["Validación", "Descarta no-notas, fechas imposibles y duplicados"],
    ["Scraping", "Entra a cada nota: bajada y JSON-LD"], ["Lenguaje", "Tema, entidades, tono con BERT, cebo"],
    ["SQLite", "Histórico de 90 días, CSV exportable"], ["Tablero", "8 pestañas + SQL en el navegador"]];
  const bw = 1.75, gap = (W - 2 * M - 6 * bw) / 5;
  etapas.forEach(([t, d], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.5, w: bw, h: 2.6, rectRadius: 0.08, fill: { color: i === 2 ? HEX.rojo : HEX.grisClaro }, line: { color: i === 2 ? HEX.rojo : HEX.grisClaro }, objectName: "etapa-" + i });
    T(s, String(i + 1), { x: x + 0.2, y: 2.7, w: 1, h: 0.6, fontSize: 30, bold: true, fontFace: "Cambria", color: i === 2 ? HEX.papel : HEX.rojo });
    T(s, t, { x: x + 0.2, y: 3.35, w: bw - 0.3, h: 0.45, fontSize: 18, bold: true, color: i === 2 ? HEX.papel : HEX.tinta });
    T(s, d, { x: x + 0.2, y: 3.85, w: bw - 0.35, h: 1.2, fontSize: 13, color: i === 2 ? HEX.papel : HEX.gris });
    if (i < 5) s.addImage({ data: ic.arrow, x: x + bw + gap / 2 - 0.12, y: 3.68, w: 0.24, h: 0.24 });
  });
  T(s, [{ text: "Automatización: ", options: { bold: true } }, { text: "GitHub Actions corre el pipeline cada hora, guarda la base en una rama de datos y publica el tablero en GitHub Pages. La primera corrida con BERT tarda 10 minutos; las siguientes, 2." }],
    { x: M, y: 5.6, w: W - 2 * M, h: 0.9, fontSize: 16 });

  // ===== 5. Fuentes =====
  s = contenido("Cómo funciona", "FUENTES", "Dos vías para llegar a 46 medios sin claves ni costo",
    "Las APIs de noticias limitan pedidos y no cubren medios regionales. Un trabajo de 2025 terminó en NewsAPI. Nosotros combinamos RSS propio con Google News por sitio. El problema de Google News: da una URL de redirección y ninguna bajada; lo resolvemos en la etapa de scraping.");
  [[ic.rss, "RSS propio", "17 medios", ["Feed XML del medio: título, enlace, fecha y bajada", "La vía más limpia y estable", "Clarín, Infobae, La Nación, La Capital, TN…"]],
   [ic.google, "Google News por sitio", "29 medios", ["Búsqueda site:dominio de las últimas 48 h", "Cubre los medios sin RSS útil", "Pero devuelve una URL de Google y sin bajada"]]].forEach(([icn, t, n, items], i) => {
    const x = M + i * 6.2;
    tarjeta(s, x, 2.2, 5.9, 2.75, "fuente-" + i);
    s.addImage({ data: icn, x: x + 0.35, y: 2.5, w: 0.5, h: 0.5 });
    T(s, t, { x: x + 1.05, y: 2.5, w: 3.2, h: 0.5, fontSize: 22, bold: true, valign: "middle" });
    T(s, n, { x: x + 3.9, y: 2.5, w: 1.7, h: 0.5, fontSize: 18, bold: true, color: HEX.rojo, align: "right", valign: "middle" });
    T(s, items.map((it, k) => ({ text: it, options: { bullet: true, breakLine: k < items.length - 1 } })), { x: x + 0.35, y: 3.25, w: 5.2, h: 1.6, fontSize: 16, paraSpaceAfter: 8 });
  });
  T(s, [{ text: `${D.gn.toLocaleString("es-AR")} de ${D.tot[0].toLocaleString("es-AR")} notas `, options: { bold: true } }, { text: "llegaron por Google News: sin el paso siguiente, solo tendríamos su título." }],
    { x: M, y: 5.3, w: W - 2 * M, h: 0.5, fontSize: 18, color: HEX.gris });

  // ===== 6. Scraping de cada nota =====
  s = contenido("Cómo funciona", "SCRAPING", "Entramos a cada nota para leer lo que el RSS no trae",
    "Distinción de clase: páginas de listado y de detalle. Los feeds son listados; cada nota es una página de detalle. Decodificamos el enlace de Google News, bajamos el HTML y leemos dos cosas: la meta og:description (la bajada) y el bloque JSON-LD NewsArticle que los diarios incrustan para Google. 41 de 44 medios lo publican.");
  const pct = (a, b) => Math.round((100 * a) / b) + "%";
  stat(s, M, 2.3, 3.6, pct(D.tot[2], D.tot[0]), "de las notas analizadas entrando a su página");
  stat(s, M, 4.3, 3.6, pct(D.tot[3], D.tot[2]), "con bajada (el resumen del propio medio)", HEX.azul);
  tarjeta(s, 4.6, 2.3, 8.13, 4.2, "jsonld");
  T(s, "Del HTML de cada nota extraemos", { x: 4.95, y: 2.55, w: 7.4, h: 0.45, fontSize: 18, bold: true });
  const campos = [["URL real", "decodificando el enlace de Google News"], ["Bajada", "meta og:description o primer párrafo real"], ["Autor y firma", "persona o \"Redacción\", desde el JSON-LD"],
    ["Sección y palabras clave", "como las clasifica el propio medio"], ["Largo del cuerpo", "cantidad de palabras de la nota"]];
  campos.forEach(([a, b], i) => {
    s.addImage({ data: ic.check, x: 4.95, y: 3.2 + i * 0.62, w: 0.28, h: 0.28 });
    T(s, [{ text: a + ": ", options: { bold: true } }, { text: b }], { x: 5.4, y: 3.15 + i * 0.62, w: 7.0, h: 0.4, fontSize: 16, valign: "middle" });
  });

  // ===== 7. Crawler bien educado =====
  s = contenido("Cómo funciona", "ÉTICA DESDE EL DISEÑO", "Un crawler \"bien educado\", como pide la teoría",
    "Ninguno de los trabajos de 2025 trató este punto. Respetamos robots.txt (0 bloqueos en miles de pedidos), nos identificamos, limitamos la carga y no guardamos el texto completo de las notas: solo título, bajada y metadatos, siempre enlazando al original.");
  [[ic.robot, "robots.txt", `Se lee por dominio antes de pedir una nota. ${D.scrap[2]} bloqueos en ${D.scrap[0].toLocaleString("es-AR")} pedidos.`],
   [ic.id, "Nos identificamos", "User-Agent propio que enlaza al proyecto: monitor-de-medios/1.0"],
   [ic.gauge, "Carga acotada", "Máximo 2 pedidos a la vez por sitio y topes de notas y tiempo por corrida."],
   [ic.redo, "Sin insistir", "Reintentos con espera creciente; una nota que falla dos veces no se vuelve a pedir."]].forEach(([icn, t, d], i) => {
    const x = M + (i % 2) * 6.2, y = 2.2 + Math.floor(i / 2) * 2.1;
    tarjeta(s, x, y, 5.9, 1.85, "regla-" + i);
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.35, w: 0.8, h: 0.8, fill: { color: HEX.papel }, line: { color: HEX.papel }, objectName: "icono-" + i });
    s.addImage({ data: icn, x: x + 0.5, y: y + 0.55, w: 0.4, h: 0.4 });
    T(s, t, { x: x + 1.35, y: y + 0.3, w: 4.3, h: 0.45, fontSize: 20, bold: true });
    T(s, d, { x: x + 1.35, y: y + 0.8, w: 4.3, h: 0.9, fontSize: 15, color: HEX.gris });
  });
  T(s, "No guardamos el texto completo de las notas: solo título, bajada y metadatos, siempre con enlace al original.", { x: M, y: 6.45, w: W - 2 * M, h: 0.4, fontSize: 14, color: HEX.gris, italic: true });

  // ===== 8. Mantenimiento =====
  s = contenido("Cómo funciona", "MANTENER UN SCRAPER", "La web cambia: el scraper se vigila a sí mismo",
    "Mantener scrapers es costoso porque la web es dinámica (lo vimos en clase). Registramos salud por fuente, resultado del scraping y notas descartadas, y eso nos permitió detectar estos problemas reales. Cada corrección también limpia lo ya guardado.");
  const filasT = [["Síntoma", "Causa", "Solución"],
    ["Bajadas con código JavaScript", "El respaldo de \"primer párrafo\" tomaba <path o código de un carrusel", "Solo <p> reales, sin scripts; se descarta texto con forma de código"],
    ["\"&amp;quot;\" en el texto", "Sitios que escapan las entidades dos veces", "Doble decodificación de entidades HTML"],
    ["\"podrÃ¡\" en vez de \"podrá\"", "Páginas UTF-8 sin charset leídas como Latin-1", "Forzar UTF-8 y reparar los tramos rotos"],
    ["Medio caído o degradado", "Feed vacío o con menos de la mitad de lo habitual", "Tabla salud y alerta en el tablero"]];
  s.addTable(filasT.map((f, i) => f.map((c) => ({ text: c, options: i === 0 ? { bold: true, color: HEX.papel, fill: { color: HEX.tinta } } : { fill: { color: i % 2 ? HEX.papel : HEX.grisClaro } } }))),
    { x: M, y: 2.2, w: W - 2 * M, colW: [3.2, 4.4, 4.53], fontSize: 14, fontFace: "Calibri", color: HEX.tinta, border: { type: "solid", pt: 0.5, color: HEX.linea }, margin: [0.08, 0.12, 0.08, 0.12], rowH: 0.62 });

  // ===== 9. Procesamiento de texto =====
  s = contenido("Cómo funciona", "PROCESAMIENTO DE TEXTO", "Cada nota recibe tema, entidades, tono y cebo",
    "Bolsa de palabras y modelo vectorial como base. Temas: reglas sobre título y bajada más un Naive Bayes con supervisión débil, que aprende de lo que las reglas clasificaron y solo asigna tema si está seguro. Entidades: diccionario con alias. Tono: lo vemos en la próxima.");
  [[ic.tags, "Temas", "15 temas. Reglas sobre título + bajada, y un Naive Bayes que aprende de lo que las reglas ya clasificaron (supervisión débil).", "\"Otros\": 24% → menos del 5%"],
   [ic.users, "Entidades", "35 personas, instituciones y clubes con sus alias y reglas de desambiguación (\"Banco Central\" no es Rosario Central).", "Más mencionados: Milei, Messi, el papa"],
   [ic.smile, "Tono", "Si el hecho es bueno o malo para los involucrados. Palabras + probabilidades de BERT, sobre el título y sobre la bajada.", "77% de acierto con validación cruzada"]].forEach(([icn, t, d, dato], i) => {
    const x = M + i * 4.1;
    tarjeta(s, x, 2.2, 3.85, 4.3, "nlp-" + i);
    s.addImage({ data: icn, x: x + 0.35, y: 2.5, w: 0.55, h: 0.55 });
    T(s, t, { x: x + 0.35, y: 3.2, w: 3.2, h: 0.5, fontSize: 22, bold: true });
    T(s, d, { x: x + 0.35, y: 3.75, w: 3.2, h: 1.8, fontSize: 15, color: HEX.gris });
    T(s, dato, { x: x + 0.35, y: 5.65, w: 3.2, h: 0.6, fontSize: 15, bold: true, color: HEX.azul });
  });

  // ===== 10. Tono con BERT =====
  s = contenido("Cómo funciona", "TONO CON BERT", "Combinar palabras con BERT sube el acierto de 70% a 77%",
    "Comparamos 8 enfoques sobre 340 titulares etiquetados a mano, con validación cruzada de 5 pliegues. Un BERT entrenado con tuits (pysentimiento) rinde peor que el modelo simple: mide la emoción de quien escribe, no si el hecho es bueno o malo. La combinación de rasgos propios con XLM-RoBERTa gana, y sobre todo detecta muchas más noticias negativas.");
  const modelos = [["Palabras + XLM-RoBERTa", 76.8], ["Palabras + ambos BERT", 75.3], ["Palabras + pysentimiento", 75.0], ["XLM-RoBERTa solo", 74.1],
    ["Embeddings + reg. logística", 72.4], ["Solo probas BERT", 72.4], ["Modelo inicial (palabras)", 70.3], ["pysentimiento solo", 64.4]];
  barras(s, modelos, { x: M - 0.1, y: 2.05, w: 7.6, h: 4.7, resaltar: ["Palabras + XLM-RoBERTa"] });
  stat(s, 8.6, 2.3, 4.1, "77%", "de acierto (antes 70%), medido con notas que el modelo no vio");
  stat(s, 8.6, 4.4, 4.1, "84%", "de las notas negativas detectadas (antes 65%)", HEX.azul);

  // ===== Termometro y resumen del dia =====
  pres.addSection({ title: "Qué encontramos" });
  s = contenido("Qué encontramos", "EL DÍA EN UN NÚMERO", "Un termómetro y un resumen que se escriben solos",
    "El termómetro es el porcentaje estimado de notas negativas de las últimas 24 horas, de 0 a 100, con bandas y la comparación contra los días anteriores. El resumen lo arma el tablero con plantillas a partir de los datos: tema más cubierto, noticia más compartida y quién la publicó primero, figura más mencionada, medio más y menos negativo. No usa un modelo de lenguaje: es reproducible y gratis.");
  s.addImage({ path: IMG("termo.png"), x: M, y: 2.2, w: W - 2 * M, h: (W - 2 * M) * 450 / 1780, objectName: "termometro" });
  T(s, [{ text: "Termómetro: ", options: { bold: true } }, { text: "% de notas negativas de las últimas 24 h (calmo, moderado, tenso, muy tenso).", options: { breakLine: true } },
        { text: "Resumen: ", options: { bold: true } }, { text: "redactado con plantillas a partir de los datos del día; sin modelo de lenguaje, reproducible." }],
    { x: M, y: 5.6, w: W - 2 * M, h: 1.0, fontSize: 16, paraSpaceAfter: 6 });

  // ===== 11. Como titula =====
  s = contenido("Qué encontramos", "CÓMO TITULA CADA MEDIO", "Tres indicadores para medir el estilo, no solo el contenido",
    "Exageración: comparamos el tono del título con el de la bajada, que es el resumen escrito por el propio medio. Cebo: rasgos de clickbait. Transparencia: notas firmadas por una persona según el JSON-LD.");
  [["Exageración", "El título es negativo y la bajada del propio medio no lo es.", "\"El dramático relato…\" → bajada: datos del vuelo y los pasajeros"],
   ["Cebo (clickbait)", "Preguntas, exclamaciones, adjetivos exagerados, intriga, segunda persona, listas.", "\"¡Escándalo! Aseguran que…\" · \"El truco viral para…\""],
   ["Transparencia", "Notas firmadas por un periodista, según los datos estructurados de la nota.", "\"Redacción\" o el nombre del medio no cuentan como firma"]].forEach(([t, d, ej], i) => {
    const y = 2.2 + i * 1.5;
    T(s, String(i + 1), { x: M, y, w: 0.7, h: 1.0, fontSize: 48, bold: true, fontFace: "Cambria", color: HEX.rojo });
    T(s, t, { x: M + 0.9, y: y + 0.05, w: 3.4, h: 0.5, fontSize: 22, bold: true });
    T(s, d, { x: M + 0.9, y: y + 0.6, w: 3.6, h: 0.8, fontSize: 14, color: HEX.gris });
    tarjeta(s, 5.4, y, 7.33, 1.25, "ejemplo-" + i);
    T(s, ej, { x: 5.7, y: y + 0.15, w: 6.8, h: 0.95, fontSize: 16, italic: true, valign: "middle" });
  });

  // ===== 12. Cebo =====
  const [c1, c2] = D.cebo;
  s = contenido("Qué encontramos", "CEBO", `${c1[0]} y ${c2[0]} usan recursos de cebo en casi 1 de cada 5 títulos`,
    `Porcentaje de títulos con al menos un recurso de cebo. En el otro extremo, ${D.cebo.slice(-3).map((r) => r[0]).join(", ")} están por debajo del 3%.`);
  const cb = D.cebo.slice(0, 10).map((r) => [r[0], r[1]]);
  barras(s, cb, { x: M - 0.1, y: 2.05, w: 7.8, h: 4.75, resaltar: [c1[0], c2[0]] });
  tarjeta(s, 8.8, 2.2, 3.93, 4.3, "extremo");
  T(s, "En el otro extremo", { x: 9.1, y: 2.45, w: 3.4, h: 0.45, fontSize: 18, bold: true });
  T(s, D.cebo.slice(-4).reverse().map((r, k, arr) => ({ text: `${r[0]}: ${String(r[1]).replace(".", ",")}%`, options: { bullet: true, breakLine: k < arr.length - 1 } })),
    { x: 9.1, y: 3.05, w: 3.4, h: 2.0, fontSize: 16, paraSpaceAfter: 8 });
  T(s, "Porcentaje de títulos con al menos un recurso de cebo; medios con 40 notas o más.", { x: 9.1, y: 5.3, w: 3.4, h: 1.0, fontSize: 12, color: HEX.gris });

  // ===== 13. Mapa del sensacionalismo =====
  s = contenido("Qué encontramos", "SENSACIONALISMO", "El mapa: quién exagera y quién busca el clic",
    "Cada punto es un medio. Eje horizontal: cebo. Eje vertical: exageración respecto de la propia bajada. Las líneas son las medianas y dividen en cuatro estilos. A24, El Trece, Radio Mitre y TN quedan como sensacionalistas; Elonce y El Chubut como sobrios. Es una medición automática con error conocido: comparar medios, no juzgar uno.");
  s.addImage({ path: IMG("mapa-sensacionalismo.png"), x: M, y: 2.1, w: 9.0, h: 9.0 * 770 / 1720, objectName: "mapa" });
  tarjeta(s, 9.9, 2.1, 2.83, 4.0, "lectura");
  T(s, "Cómo leerlo", { x: 10.15, y: 2.35, w: 2.4, h: 0.45, fontSize: 17, bold: true });
  T(s, [{ text: "Arriba a la derecha: ", options: { bold: true } }, { text: "títulos con cebo que además exageran.", options: { breakLine: true } },
        { text: "Abajo a la izquierda: ", options: { bold: true } }, { text: "títulos sobrios y fieles a su bajada." }],
    { x: 10.15, y: 2.9, w: 2.4, h: 3.0, fontSize: 14, paraSpaceAfter: 10 });

  // ===== 14. Tono por medio =====
  s = contenido("Qué encontramos", "TONO", `En ${D.neg[0][0]}, 1 de cada 2 notas es negativa; en ${D.neg[D.neg.length - 1][0]}, 1 de cada 5`,
    "Proporción de notas con tono negativo según el modelo combinado, medios con 60 notas o más. Muestra los 5 más negativos y los 5 menos negativos. El tono mide el hecho, no la postura del medio: un medio con más policiales tiene más negativas.");
  const ng = [...D.neg.slice(0, 5), ...D.neg.slice(-5)].map((r) => [r[0], r[1]]);
  barras(s, ng, { x: M - 0.1, y: 2.05, w: 8.0, h: 4.75, resaltar: D.neg.slice(0, 5).map((r) => r[0]), color: HEX.gris });
  tarjeta(s, 9.0, 2.2, 3.73, 4.3, "tono-total");
  T(s, "En toda la base", { x: 9.3, y: 2.45, w: 3.2, h: 0.45, fontSize: 18, bold: true });
  const tt = D.tono.n + D.tono["0"] + D.tono.p;
  [["Negativo", D.tono.n, HEX.rojo], ["Neutro", D.tono["0"], HEX.gris], ["Positivo", D.tono.p, HEX.verde]].forEach(([l, v, c], i) => {
    T(s, pct(v, tt), { x: 9.3, y: 3.05 + i * 1.05, w: 1.6, h: 0.75, fontSize: 36, bold: true, fontFace: "Cambria", color: c });
    T(s, l, { x: 10.95, y: 3.25 + i * 1.05, w: 1.6, h: 0.45, fontSize: 16 });
  });

  // ===== 15. Transparencia =====
  const sinFirma = D.firm.filter((r) => r[1] === 0).map((r) => r[0]);
  s = contenido("Qué encontramos", "TRANSPARENCIA", `${D.firm[0][0]} firma el ${Math.round(D.firm[0][1])}% de sus notas; ${sinFirma.includes("Radio Mitre") ? "Radio Mitre y Rosario3" : sinFirma.slice(0, 2).join(" y ")}, ninguna`,
    "Proporción de notas firmadas por una persona, según el autor declarado en el JSON-LD de cada nota. Medios con 40 notas o más con datos estructurados.");
  const fi = D.firm.filter((r) => r[1] > 0).slice(0, 9).map((r) => [r[0], r[1]]);
  barras(s, fi, { x: M - 0.1, y: 2.05, w: 7.8, h: 4.75, resaltar: [D.firm[0][0]] });
  tarjeta(s, 8.8, 2.2, 3.93, 4.3, "sin-firma");
  T(s, "Sin ninguna nota firmada", { x: 9.1, y: 2.45, w: 3.4, h: 0.45, fontSize: 18, bold: true });
  const cero = D.firm.filter((r) => r[1] === 0).map((r) => r[0]);
  T(s, cero.slice(0, 7).map((m, k, arr) => ({ text: m, options: { bullet: true, breakLine: k < arr.length - 1 } })), { x: 9.1, y: 3.05, w: 3.4, h: 3.2, fontSize: 16, paraSpaceAfter: 6 });

  // ===== Encuadre y primicia =====
  s = contenido("Qué encontramos", "ENCUADRE", "Una noticia, muchos encuadres",
    "El sistema agrupa las notas que cuentan lo mismo (TF-IDF y similitud coseno) y muestra el título de cada medio en orden de publicación, con su tono y sus recursos de cebo. Ejemplo: el sobreseimiento de Milei en la causa Libra lo cubrieron 12 medios; la publicó primero El Cronista y el último llegó 8 horas después. Con eso también medimos quién llega primero.");
  s.addImage({ path: IMG("encuadre.png"), x: M, y: 2.05, w: 7.6, h: 7.6 * 1160 / 1780, objectName: "encuadre" });
  tarjeta(s, 8.6, 2.05, 4.13, 4.55, "primicia");
  T(s, "Quién llega primero", { x: 8.9, y: 2.3, w: 3.6, h: 0.45, fontSize: 18, bold: true });
  T(s, "Medio que más veces publicó primero una historia que después cubrieron otros:", { x: 8.9, y: 2.85, w: 3.6, h: 0.9, fontSize: 14, color: HEX.gris });
  T(s, "Eldoce", { x: 8.9, y: 3.8, w: 3.6, h: 0.8, fontSize: 40, bold: true, fontFace: "Cambria", color: HEX.rojo });
  T(s, "Cada tarjeta muestra el tono del título, sus recursos de cebo y los minutos de demora respecto del primero.", { x: 8.9, y: 4.75, w: 3.6, h: 1.6, fontSize: 14 });

  // ===== Tono por figura =====
  s = contenido("Qué encontramos", "TONO POR FIGURA", "Cómo trata cada medio a cada figura",
    "Matriz medio por figura: porcentaje de notas negativas cuando el medio menciona a esa figura. Rojo: más negativo que el promedio de los medios; verde: menos. Solo celdas con 3 notas o más. Con pocos días de datos los valores son ilustrativos: muestran el método.");
  s.addImage({ path: IMG("figuras.png"), x: M, y: 2.05, w: 9.2, h: 9.2 * 490 / 1780, objectName: "figuras" });
  tarjeta(s, 10.1, 2.05, 2.63, 3.9, "figuras-lectura");
  T(s, [{ text: "Rojo: ", options: { bold: true, color: HEX.rojo } }, { text: "más negativo que el promedio de los medios con esa figura.", options: { breakLine: true } },
        { text: "Verde: ", options: { bold: true, color: HEX.verde } }, { text: "menos negativo.", options: { breakLine: true } },
        { text: "Entre paréntesis, la cantidad de notas." }], { x: 10.35, y: 2.3, w: 2.2, h: 3.5, fontSize: 14, paraSpaceAfter: 8 });

  // ===== Mapa de medios =====
  s = contenido("Qué encontramos", "MINERÍA DE ESTRUCTURA", "El mapa de medios: quién comparte agenda con quién",
    "Grafo de medios: una arista une a dos medios que cubren las mismas historias, ponderada por historias compartidas sobre las del medio más chico; cada medio conserva sus 3 vínculos más fuertes. Las comunidades salen de propagación de etiquetas y el dibujo es una disposición por fuerzas. Es la rama de minería de estructura de la teoría, aplicada a la cobertura y no a los links.");
  s.addImage({ path: IMG("grafo.png"), x: M, y: 2.0, w: 7.3, h: 7.3 * 1090 / 1780, objectName: "grafo" });
  tarjeta(s, 8.3, 2.05, 4.43, 4.55, "grafo-lectura");
  T(s, "Cómo se arma", { x: 8.6, y: 2.3, w: 3.9, h: 0.45, fontSize: 18, bold: true });
  T(s, ["Nodos: medios; tamaño según historias compartidas", "Aristas: cubren las mismas historias", "Colores: comunidades detectadas por propagación de etiquetas", "Disposición por fuerzas, animada en el tablero"].map((it, k, arr) => ({ text: it, options: { bullet: true, breakLine: k < arr.length - 1 } })),
    { x: 8.6, y: 2.9, w: 3.95, h: 3.5, fontSize: 15, paraSpaceAfter: 8 });

  // ===== 16. Tablero =====
  pres.addSection({ title: "Cierre" });
  s = contenido("Cierre", "EL TABLERO", "Todo esto, en un tablero público que se actualiza solo",
    "Mostrar el tablero en vivo. Recorrer Resumen, Titulares (con buscador), Monitor (seguir una persona), Cómo titulan y Salud de datos. Es una página estática en GitHub Pages: funciona también en el celular.");
  s.addImage({ path: IMG("tablero-resumen.png"), x: M, y: 2.05, w: 7.2, h: 4.5, objectName: "captura" });
  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 2.05, w: 7.2, h: 4.5, fill: { type: "none" }, line: { color: HEX.linea, width: 1 }, objectName: "marco" });
  const pest = [["Resumen", "termómetro, resumen del día y noticias compartidas"], ["Titulares", "buscador y filtros por medio y tema"], ["Monitor", "seguir una persona o marca"],
    ["Análisis", "filtros, agenda, encuadre y mapa de medios"], ["Cómo titulan", "mapa, rankings y ejemplos"], ["Salud de datos", "fuentes y scraping"]];
  pest.forEach(([a, b], i) => T(s, [{ text: a, options: { bold: true, breakLine: true } }, { text: b, options: { color: HEX.gris } }], { x: 8.2, y: 2.1 + i * 0.64, w: 4.5, h: 0.62, fontSize: 14 }));

  // ===== 17. Demo SQL =====
  s = contenido("Cierre", "DEMO EN VIVO", "La base se consulta con SQL desde el navegador",
    "Abrir el tablero, tocar Explorar la base (SQL). Datasette Lite corre SQLite en el navegador con WebAssembly: no hay que instalar nada. Correr esta consulta y después una propuesta por la clase.");
  tarjeta(s, M, 2.2, 7.0, 4.3, "sql");
  T(s, ["SELECT medio,", "  ROUND(100*AVG(cebo>=1), 1) AS cebo,", "  ROUND(100*AVG(tono_auto='n'), 1) AS neg", "FROM items", "GROUP BY medio", "HAVING COUNT(*) >= 50", "ORDER BY cebo DESC;"].map((l, k, arr) => ({ text: l, options: { breakLine: k < arr.length - 1 } })),
    { x: M + 0.35, y: 2.55, w: 6.4, h: 3.7, fontSize: 18, fontFace: "Courier New" });
  const pasos = ["Abrir el tablero (QR al final)", "Tocar \"Explorar la base (SQL)\"", "Elegir la tabla items o escribir una consulta", "Descargar la base o el CSV si se quiere"];
  pasos.forEach((p, i) => {
    T(s, String(i + 1), { x: 8.1, y: 2.25 + i * 1.0, w: 0.6, h: 0.7, fontSize: 32, bold: true, fontFace: "Cambria", color: HEX.rojo });
    T(s, p, { x: 8.8, y: 2.4 + i * 1.0, w: 3.9, h: 0.6, fontSize: 17 });
  });

  // ===== 18. Herramientas =====
  s = contenido("Cierre", "HERRAMIENTAS", "Un stack simple, gratuito y reproducible",
    "Sin servidores ni costos: todo corre en GitHub. SQLite simplifica la operación y se puede abrir en el navegador.");
  const stack = [["Recolección", "requests · feedparser · googlenewsdecoder · urllib.robotparser"], ["Extracción", "expresiones regulares · JSON-LD (schema.org) · HTML"],
    ["Lenguaje", "bolsa de palabras · Naive Bayes · regresión logística · XLM-RoBERTa (PyTorch, transformers)"], ["Datos", "SQLite · CSV · Datasette Lite · notebook con pandas"],
    ["Automatización", "GitHub Actions (cada hora) · rama de datos"], ["Visualización", "HTML, CSS y JavaScript sin frameworks · GitHub Pages"]];
  stack.forEach(([a, b], i) => {
    const x = M + (i % 2) * 6.2, y = 2.2 + Math.floor(i / 2) * 1.45;
    tarjeta(s, x, y, 5.9, 1.25, "stack-" + i);
    T(s, a, { x: x + 0.3, y: y + 0.15, w: 5.3, h: 0.4, fontSize: 17, bold: true, color: HEX.rojo });
    T(s, b, { x: x + 0.3, y: y + 0.58, w: 5.4, h: 0.6, fontSize: 15 });
  });

  // ===== 19. Limitaciones y proximos pasos =====
  s = contenido("Cierre", "LO QUE SIGUE", "Limitaciones honestas y próximos pasos",
    "Ser claros con los límites: el tono es del título, 77% de acierto, 340 etiquetas de un criterio. El histórico es corto. Próximos pasos: NER con spaCy, evolución de comunidades, cruce con datos económicos y más etiquetas manuales.");
  [[ic.warn, "Limitaciones", ["Tono del título y la bajada, no de la nota completa", "77% de acierto con 340 etiquetas de un solo criterio", "Pocos días de histórico: los rankings se estabilizan con semanas", "Temas y entidades por diccionario requieren mantenimiento"]],
   [ic.check, "Próximos pasos", ["Entidades con spaCy (NER) para descubrir figuras nuevas", "Evolución de las comunidades a lo largo de las semanas", "Cruzar el termómetro con el dólar y otros datos", "Más etiquetas manuales, con varios anotadores"]]].forEach(([icn, t, items], i) => {
    const x = M + i * 6.2;
    tarjeta(s, x, 2.2, 5.9, 4.3, "cierre-" + i);
    s.addImage({ data: icn, x: x + 0.35, y: 2.5, w: 0.45, h: 0.45 });
    T(s, t, { x: x + 1.0, y: 2.5, w: 4.5, h: 0.45, fontSize: 22, bold: true, valign: "middle" });
    T(s, items.map((it, k) => ({ text: it, options: { bullet: true, breakLine: k < items.length - 1 } })), { x: x + 0.35, y: 3.25, w: 5.25, h: 3.0, fontSize: 16, paraSpaceAfter: 10 });
  });

  // ===== 20. Cierre =====
  s = pres.addSlide({ masterName: "PORTADA", sectionTitle: "Cierre" });
  s.addText("PROBALO AHORA", { placeholder: "kicker" });
  s.addText("Gracias", { placeholder: "title" });
  s.addText("Escaneá el código para abrir el tablero y consultar la base con SQL", { placeholder: "body" });
  s.addImage({ path: IMG("qr-tablero.png"), x: 9.6, y: 1.6, w: 3.0, h: 3.0, objectName: "qr" });
  T(s, "miguegarrone-blip.github.io/Web-Mining", { x: 8.6, y: 4.75, w: 5.0, h: 0.4, fontSize: 15, color: HEX.papel, align: "center" });
  T(s, "Código: github.com/miguegarrone-blip/Web-Mining", { x: M, y: 6.6, w: 10, h: 0.4, fontSize: 14, color: HEX.neutro });
  s.addNotes("Cierre con la invitación a probarlo en vivo. Preguntas.");

  const salida = path.join(__dirname, "..", "presentacion-tp.pptx");
  await pres.writeFile({ fileName: salida });
  try { const { applyTheme } = require(APPLY_THEME); await applyTheme(salida, THEME); }
  catch (e) { console.log("sin apply_theme.js: queda la paleta estandar de Office (" + e.message.slice(0, 80) + ")"); }
  console.log("generado", salida);
})();
