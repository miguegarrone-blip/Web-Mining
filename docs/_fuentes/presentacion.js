// Genera docs/presentacion-tp.pptx: "La Tapa", la presentacion del TP con forma de diario.
// Uso: cd docs/_fuentes && python actualizar_datos.py && node presentacion.js   (ver docs/README.md)
//  - datos.json: cifras y titulares reales (actualizar_datos.py los baja de la base publicada)
//  - metricas.json: anchos de letra de las fuentes de los recortes (metricas.py), para cortar renglones y ubicar las marcas rojas
//  - img/: capturas del tablero; se "entintan" a la paleta del diario en img/*-tinta.png
// Identidad: papel F3EEE3, tinta 141210, un solo acento (rojo de imprenta C8102E). Cabecera en Old English Text MT,
// titulares en Bodoni MT Condensed, texto en Cambria, datos y volantas en Consolas.
const path = require("path");
const fs = require("fs");
const sharp = require("sharp");
const pptxgen = require("pptxgenjs");

const APPLY_THEME = process.env.APPLY_THEME ||
  "C:/Users/SBI/.claude/skills/synced/f4dffbae-5dfb-49d8-819c-bcd5bbdb69f2_aed8e124-858a-4b29-a69c-3fa9ddd3cd98/pptx/scripts/apply_theme.js";
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "datos.json"), "utf-8"));
const MET = JSON.parse(fs.readFileSync(path.join(__dirname, "metricas.json"), "utf-8"));
const IMG = (f) => path.join(__dirname, "img", f);

// ---------- identidad ----------
const HEX = { papel: "F3EEE3", papelClaro: "FAF7F0", tinta: "141210", gris: "5E5A54", rojo: "C8102E",
              pos: "2E6B3F", neutro: "9A948A", grisClaro: "D9D2C4" };
const F = { gotica: "Old English Text MT", titular: "Bodoni MT Condensed", cuerpo: "Cambria", mono: "Consolas" };
const THEME = {
  name: "La Tapa", headFontFace: F.titular, bodyFontFace: F.cuerpo,
  colors: { dk1: HEX.tinta, lt1: HEX.papelClaro, dk2: HEX.gris, lt2: HEX.papel, accent1: HEX.rojo, accent2: HEX.tinta, accent3: HEX.gris,
            accent4: HEX.pos, accent5: HEX.neutro, accent6: HEX.grisClaro, hlink: HEX.rojo, folHlink: HEX.gris },
};
const mezcla = (a, b, t) => [0, 2, 4].map((i) => Math.round(parseInt(a.substr(i, 2), 16) * t + parseInt(b.substr(i, 2), 16) * (1 - t))
  .toString(16).padStart(2, "0")).join("").toUpperCase();

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13,33 x 7,5 pulgadas
pres.title = "La Tapa: ¿Cómo nos cuentan las noticias?";
pres.author = "Grupo 3 - Ceriotti, Garrone, Tamplin, Terán";
pres.subject = "Web Mining - Maestría en Ciencia de Datos - Universidad Austral, Sede Rosario";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const W = 13.333, M = 0.6, CW = W - 2 * M;
const fmt = (n) => Number(n).toLocaleString("es-AR");
const dec = (n) => String(n).replace(".", ",");
const hoy = new Date();
const FECHA = hoy.toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).replace(",", "");
const FECHA_MAY = FECHA.toUpperCase();
const ddmm = (iso) => iso.slice(8, 10) + "/" + iso.slice(5, 7);
const diaSemana = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("es-AR", { weekday: "long", day: "numeric" });

// ---------- layouts (en PowerPoint: Vista > Patron de diapositivas) ----------
const dobleFilete = (y) => [
  { line: { x: M, y, w: CW, h: 0, line: { color: HEX.tinta, width: 2.25 } } },
  { line: { x: M, y: y + 0.06, w: CW, h: 0, line: { color: HEX.tinta, width: 0.75 } } },
];
pres.defineSlideMaster({
  title: "TAPA", background: { color: HEX.papel },
  objects: [
    { text: { text: "La Tapa", options: { x: 2.9, y: 0.12, w: W - 5.8, h: 1.45, fontFace: F.gotica, fontSize: 100, color: HEX.tinta, align: "center", valign: "middle", margin: 0 } } },
    { text: { text: "El diario que lee a los diarios", options: { x: 2.9, y: 1.52, w: W - 5.8, h: 0.34, fontFace: F.cuerpo, italic: true, fontSize: 16, color: HEX.gris, align: "center", margin: 0 } } },
    ...dobleFilete(1.95),
    { line: { x: M, y: 2.45, w: CW, h: 0, line: { color: HEX.tinta, width: 0.75 } } },
    { placeholder: { options: { name: "volanta", type: "body", x: M, y: 2.68, w: 8.0, h: 0.32, fontFace: F.mono, fontSize: 13, bold: true, color: HEX.rojo, charSpacing: 3, margin: 0, valign: "top" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 3.0, w: 8.1, h: 1.95, fontFace: F.titular, bold: true, fontSize: 66, color: HEX.tinta, margin: 0, valign: "top", align: "left", lineSpacingMultiple: 0.88 }, text: "" } },
    { placeholder: { options: { name: "bajada", type: "body", x: M, y: 5.0, w: 8.0, h: 0.72, fontFace: F.cuerpo, fontSize: 18, color: HEX.gris, margin: 0, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "PAGINA", background: { color: HEX.papel },
  objects: [
    { text: { text: "La Tapa", options: { x: M, y: 0.2, w: 1.6, h: 0.5, fontFace: F.gotica, fontSize: 24, color: HEX.tinta, margin: 0, valign: "bottom" } } },
    { text: { text: "PÁG.", options: { x: 2.15, y: 0.37, w: 0.5, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.gris, margin: 0, valign: "bottom", charSpacing: 1 } } },
    { text: { text: FECHA_MAY, options: { x: 3.9, y: 0.37, w: 5.5, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.gris, margin: 0, align: "center", valign: "bottom", charSpacing: 1 } } },
    { placeholder: { options: { name: "seccion", type: "body", x: 8.9, y: 0.37, w: W - M - 8.9, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.tinta, bold: true, margin: 0, align: "right", valign: "bottom", charSpacing: 2 }, text: "" } },
    ...dobleFilete(0.74),
    { placeholder: { options: { name: "volanta", type: "body", x: M, y: 1.0, w: CW, h: 0.3, fontFace: F.mono, fontSize: 13, bold: true, color: HEX.rojo, charSpacing: 3, margin: 0, valign: "top" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.28, w: CW, h: 0.8, fontFace: F.titular, bold: true, fontSize: 42, color: HEX.tinta, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "bajada", type: "body", x: M, y: 2.08, w: CW, h: 0.42, fontFace: F.cuerpo, italic: true, fontSize: 17, color: HEX.gris, margin: 0, valign: "top" }, text: "" } },
    { line: { x: M, y: 7.0, w: CW, h: 0, line: { color: HEX.tinta, width: 0.75 } } },
    { text: { text: "LA TAPA · EL DIARIO QUE LEE A LOS DIARIOS", options: { x: M, y: 7.06, w: 6, h: 0.26, fontFace: F.mono, fontSize: 10, color: HEX.gris, margin: 0, charSpacing: 1 } } },
    { text: { text: "WEB MINING · GRUPO 3 · UNIVERSIDAD AUSTRAL", options: { x: W - M - 6, y: 7.06, w: 6, h: 0.26, fontFace: F.mono, fontSize: 10, color: HEX.gris, margin: 0, align: "right", charSpacing: 1 } } },
  ],
  slideNumber: { x: 2.62, y: 0.37, w: 0.6, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.gris, margin: 0, valign: "bottom" },
});
pres.defineSlideMaster({
  title: "CONTRATAPA", background: { color: HEX.papel },
  objects: [
    { text: { text: "La Tapa", options: { x: M, y: 0.2, w: 1.6, h: 0.5, fontFace: F.gotica, fontSize: 24, color: HEX.tinta, margin: 0, valign: "bottom" } } },
    { text: { text: "CONTRATAPA", options: { x: 8.9, y: 0.37, w: W - M - 8.9, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.tinta, bold: true, margin: 0, align: "right", valign: "bottom", charSpacing: 2 } } },
    { text: { text: FECHA_MAY, options: { x: 3.9, y: 0.37, w: 5.5, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.gris, margin: 0, align: "center", valign: "bottom", charSpacing: 1 } } },
    ...dobleFilete(0.74),
    { placeholder: { options: { name: "volanta", type: "body", x: M, y: 1.3, w: 7.4, h: 0.32, fontFace: F.mono, fontSize: 13, bold: true, color: HEX.rojo, charSpacing: 3, margin: 0, valign: "top" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.6, w: 7.6, h: 1.9, fontFace: F.titular, bold: true, fontSize: 120, color: HEX.tinta, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "bajada", type: "body", x: M, y: 3.55, w: 7.4, h: 0.8, fontFace: F.cuerpo, italic: true, fontSize: 20, color: HEX.gris, margin: 0, valign: "top" }, text: "" } },
    { line: { x: M, y: 7.0, w: CW, h: 0, line: { color: HEX.tinta, width: 0.75 } } },
    { text: { text: "LA TAPA · EL DIARIO QUE LEE A LOS DIARIOS", options: { x: M, y: 7.06, w: 6, h: 0.26, fontFace: F.mono, fontSize: 10, color: HEX.gris, margin: 0, charSpacing: 1 } } },
  ],
});

// ---------- ayudas de composicion ----------
const T = (s, txt, o) => s.addText(txt, { isTextBox: true, fontFace: F.cuerpo, fontSize: 15, color: HEX.tinta, margin: 0, valign: "top", ...o });
const linea = (s, x, y, w, h, o = {}) => s.addShape(pres.shapes.LINE, { x, y, w, h, line: { color: HEX.tinta, width: 0.75, ...o }, objectName: o.nombre || "filete" });
const vFilete = (s, x, y1, y2) => linea(s, x, y1, 0, y2 - y1, { color: HEX.tinta, width: 0.5 });
const hFilete = (s, x, y, w, grosor = 0.5) => linea(s, x, y, w, 0, { width: grosor });
const ancho = (txt, clave, pt) => { let a = 0; for (const c of txt) a += MET[clave][c] ?? 520; return (a / 1000) * pt / 72; };
const TIT = F.titular + "|b";
function revisarTitulo(t, max = CW, pt = 42) {
  if (ancho(t, TIT, pt) > max) console.warn("  ! titulo largo (" + ancho(t, TIT, pt).toFixed(2) + " in): " + t);
}
function pagina(seccion, volanta, titulo, bajada, notas) {
  const s = pres.addSlide({ masterName: "PAGINA", sectionTitle: seccion });
  s.addText(seccion.toUpperCase(), { placeholder: "seccion" });
  s.addText(volanta.toUpperCase(), { placeholder: "volanta" });
  s.addText(titulo, { placeholder: "title" });
  if (bajada) s.addText(bajada, { placeholder: "bajada" });
  revisarTitulo(titulo);
  if (notas) s.addNotes(notas);
  return s;
}
// columna con titulito en mono y filete fino (como los "sumarios" de los diarios)
function cabezaColumna(s, x, y, w, txt, color = HEX.tinta) {
  T(s, txt.toUpperCase(), { x, y, w, h: 0.26, fontFace: F.mono, fontSize: 11, bold: true, color, charSpacing: 2 });
  hFilete(s, x, y + 0.3, w, 0.75);
}
// cortar un titular en renglones con los anchos reales de la fuente (para ubicar la marca roja sobre la palabra)
function cortar(txt, clave, pt, w) {
  const pal = [...txt.matchAll(/\S+/g)].map((m) => ({ ini: m.index, fin: m.index + m[0].length }));
  const out = [];
  let ini = null, fin = null;
  for (const p of pal) {
    if (ini === null) { ini = p.ini; fin = p.fin; continue; }
    if (ancho(txt.slice(ini, p.fin), clave, pt) > w) { out.push({ t: txt.slice(ini, fin), ini }); ini = p.ini; }
    fin = p.fin;
  }
  if (ini !== null) out.push({ t: txt.slice(ini, fin), ini });
  return out;
}
// trazo de birome roja: ovalo a mano alzada que no cierra del todo (PNG con transparencia)
function azar(seed) { let a = seed >>> 0; return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
async function birome(wIn, hIn, seed) {
  const k = 160, Wp = Math.round(wIn * k), Hp = Math.round(hIn * k), sw = 4.2, r = azar(seed);
  const rx = Wp / 2 - sw * 2, ry = Hp / 2 - sw * 2, th0 = Math.PI * (0.8 + 0.3 * r()), vueltas = 1.13 + 0.06 * r();
  const fase = r() * 6, pts = [];
  for (let i = 0; i <= 140; i++) {
    const u = i / 140, th = th0 + u * vueltas * 2 * Math.PI, enc = 1 - 0.07 * u, ond = 1 + 0.025 * Math.sin(3 * th + fase);
    pts.push([Wp / 2 + (rx * enc * ond) * Math.cos(th) + u * 3, Hp / 2 + (ry * enc * ond) * Math.sin(th) - u * 2]);
  }
  const d = "M" + pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" L");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${Wp}" height="${Hp}"><path d="${d}" fill="none" stroke="#C8102E" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" opacity="0.92"/></svg>`;
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
// recorte de diario: titulo real + medio y hora en mono, sobre papel mas claro con borde fino, levemente girado.
// Todas las piezas giran alrededor del centro del recorte, asi la marca roja queda sobre la palabra aunque este torcido.
let nRecorte = 0;
async function recorte(s, o) {
  const { x, y, w, medio, hora, rot = 0, fs: pt = 16, marcas = [], pie = null, pieColor = HEX.gris, extra = "" } = o;
  const titulo = o.titulo.replace(/"([^"]*)"/g, "“$1”");   // comillas tipograficas (mismo largo: las marcas no se corren)
  const pad = 0.15, metaH = 0.22, gap = 0.06, tw = w - 2 * pad, lh = (pt * 1.08) / 72;
  const renglones = cortar(titulo, TIT, pt, tw);
  const th = renglones.length * lh + 0.03, pieH = pie ? 0.3 : 0;
  const h = pad + metaH + gap + th + pieH + pad * 0.8;
  const cx = x + w / 2, cy = y + h / 2, rad = (rot * Math.PI) / 180;
  const ubicar = (bx, by, bw, bh, giro = rot) => {
    const dx = bx + bw / 2 - cx, dy = by + bh / 2 - cy;
    return { x: cx + dx * Math.cos(rad) - dy * Math.sin(rad) - bw / 2, y: cy + dx * Math.sin(rad) + dy * Math.cos(rad) - bh / 2, w: bw, h: bh, rotate: giro };
  };
  const id = "recorte-" + ++nRecorte;
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, rotate: rot, fill: { color: HEX.papelClaro }, line: { color: HEX.gris, width: 0.75 }, objectName: id });
  T(s, [{ text: medio.toUpperCase(), options: { bold: true, color: HEX.tinta } }, { text: " · " + hora + (extra ? " · " + extra : "") }],
    { ...ubicar(x + pad, y + pad, tw + 0.3, metaH), wrap: false, fontFace: F.mono, fontSize: 10.5, color: HEX.gris, charSpacing: 0.5, valign: "middle", objectName: id + "-medio" });
  const ty = y + pad + metaH + gap;
  T(s, renglones.map((r, i) => ({ text: r.t, options: { breakLine: i < renglones.length - 1 } })),
    { ...ubicar(x + pad, ty, tw + 0.2, th), fontFace: F.titular, bold: true, fontSize: pt, lineSpacing: pt * 1.08, wrap: false, objectName: id + "-titulo" });
  if (pie) T(s, pie, { ...ubicar(x + pad, ty + th + 0.04, tw, 0.24), fontFace: F.mono, fontSize: 10.5, bold: true, color: pieColor, charSpacing: 1, valign: "middle", objectName: id + "-pie" });
  let k = 0;
  for (const [a, b] of marcas) {
    if (b - a < 2) continue;   // un signo suelto (? o !) no se marca: se ve en el titulo
    for (const [i, r] of renglones.entries()) {
      const sa = Math.max(a, r.ini), sb = Math.min(b, r.ini + r.t.length);
      if (sa >= sb) continue;
      const x0 = ancho(r.t.slice(0, sa - r.ini), TIT, pt), x1 = x0 + ancho(r.t.slice(sa - r.ini, sb - r.ini), TIT, pt);
      const bw = x1 - x0 + 0.13, bh = lh + 0.15;
      const g = rot + (k % 2 ? 2.5 : -2);
      s.addImage({ data: await birome(bw, bh, 7 + nRecorte * 13 + k), ...ubicar(x + pad + x0 - 0.065, ty + i * lh - 0.07, bw, bh, g), objectName: id + "-marca-" + k, altText: "Marca roja sobre un recurso de cebo" });
      k++;
    }
  }
  return h;
}
// grafico de barras horizontales en tinta: gris, con las categorias destacadas en rojo
function barras(s, filas, { x, y, w, h, rojo = [], color = HEX.gris, nombre = "grafico", fsCat = 13 }) {
  const fl = [...filas].reverse();
  s.addChart(pres.charts.BAR, [{ name: "valor", labels: fl.map((f) => f[0]), values: fl.map((f) => f[1]) }], {
    x, y, w, h, barDir: "bar", barGapWidthPct: 38, chartColors: fl.map((f) => (rojo.includes(f[0]) ? HEX.rojo : f[0].trim() ? color : HEX.papel)),
    catAxisLabelColor: HEX.tinta, catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: fsCat, catAxisLineShow: false, catGridLine: { style: "none" },
    valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: Math.max(...fl.map((f) => f[1])) * 1.14,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%";;;', dataLabelFontFace: "+mn-lt", dataLabelFontSize: 13, dataLabelColor: HEX.tinta, dataLabelFontBold: true,
    showLegend: false, objectName: nombre,
  });
}
// cifra grande con epigrafe (tipo "dato" de diario)
function cifra(s, x, y, w, num, texto, color = HEX.tinta, pt = 72) {
  T(s, num, { x, y, w, h: pt / 72 * 1.0, fontFace: F.titular, bold: true, fontSize: pt, color, valign: "bottom", objectName: "cifra" });
  T(s, texto, { x, y: y + pt / 72 * 1.0 + 0.06, w, h: 0.75, fontSize: 15, color: HEX.gris, objectName: "cifra-texto" });
}
// cita destacada con comillas grandes en rojo
function cita(s, x, y, w, txt, firma, pt = 20) {
  T(s, "“", { x: x - 0.05, y: y - 0.35, w: 0.8, h: 1.2, fontFace: F.titular, bold: true, fontSize: 110, color: HEX.rojo, objectName: "comillas" });
  T(s, txt, { x: x + 0.75, y, w: w - 0.75, h: 1.0, fontFace: F.cuerpo, italic: true, fontSize: pt, color: HEX.tinta, objectName: "cita" });
  if (firma) T(s, firma, { x: x + 0.75, y: y + 1.02, w: w - 0.75, h: 0.26, fontFace: F.mono, fontSize: 11, color: HEX.gris, charSpacing: 1 });
}
// "foto" del diario: imagen con marco fino y epigrafe en mono
function foto(s, data, x, y, w, h, epigrafe, nombre) {
  s.addImage({ data, x, y, w, h, objectName: nombre, altText: epigrafe });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: HEX.tinta, width: 0.75 }, objectName: nombre + "-marco" });
  T(s, epigrafe, { x, y: y + h + 0.07, w, h: 0.26, fontFace: F.mono, fontSize: 10.5, color: HEX.gris, objectName: nombre + "-epigrafe" });
}
// las capturas del tablero se "entintan": el fondo pasa a papel y cada color a la paleta del diario
async function entintar(archivo, anclas, recorte_ = null) {
  let img = sharp(IMG(archivo)).removeAlpha();
  if (recorte_) img = img.extract(recorte_);
  const { data, info } = await img.raw().toBuffer({ resolveWithObject: true });
  const bg = [243, 244, 241], pa = [0xf3, 0xee, 0xe3];
  const A = anclas.map(([o, d]) => { const v = o.map((c, i) => c - bg[i]); return { v, vv: v.reduce((a, c) => a + c * c, 0), d }; });
  for (let p = 0; p < data.length; p += 3) {
    const q = [data[p] - bg[0], data[p + 1] - bg[1], data[p + 2] - bg[2]];
    let mejor = null, err = Infinity, al = 0;
    for (const a of A) {
      const t = Math.max(0, Math.min(1, (q[0] * a.v[0] + q[1] * a.v[1] + q[2] * a.v[2]) / a.vv));
      const e = (q[0] - t * a.v[0]) ** 2 + (q[1] - t * a.v[1]) ** 2 + (q[2] - t * a.v[2]) ** 2;
      if (e < err) { err = e; mejor = a; al = t; }
    }
    for (let i = 0; i < 3; i++) data[p + i] = Math.round(pa[i] + al * (mejor.d[i] - pa[i]));
  }
  const salida = IMG(archivo.replace(".png", "-tinta.png"));
  const png = await sharp(data, { raw: info }).png().toBuffer();
  fs.writeFileSync(salida, png);
  return { data: "image/png;base64," + png.toString("base64"), w: info.width, h: info.height };
}
const rgb = (h) => [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16));

(async () => {
  const tot = D.tot, pct = (a, b) => Math.round((100 * a) / b) + "%";
  const TONO = { n: ["NEGATIVO", HEX.rojo], p: ["POSITIVO", HEX.pos], 0: ["NEUTRO", HEX.gris] };
  const demora = (m) => (m < 60 ? `+${m} min` : `+${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`);

  // ===== 1. Tapa =====
  pres.addSection({ title: "Apertura" });
  let s = pres.addSlide({ masterName: "TAPA", sectionTitle: "Apertura" });
  s.addText("MAESTRÍA EN CIENCIA DE DATOS · WEB MINING", { placeholder: "volanta" });
  s.addText("¿Cómo nos cuentan las noticias?", { placeholder: "title" });
  s.addText(`Un monitor automático lee ${tot.medios} medios argentinos cada media hora y mide de qué hablan, con qué tono y cómo titulan.`, { placeholder: "bajada" });
  // orejas de la cabecera
  [[M, ["EDICIÓN ESPECIAL", "Web Mining", "Grupo 3"]], [W - M - 2.25, [`${tot.medios} MEDIOS`, `${fmt(tot.notas)} notas`, "cada 30 minutos"]]].forEach(([x, l], i) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.42, w: 2.25, h: 1.12, fill: { type: "none" }, line: { color: HEX.tinta, width: 0.75 }, objectName: "oreja-" + i });
    T(s, [{ text: l[0], options: { bold: true, color: i ? HEX.rojo : HEX.tinta, breakLine: true } }, { text: l[1], options: { breakLine: true } }, { text: l[2] }],
      { x: x + 0.1, y: 0.5, w: 2.05, h: 0.96, fontFace: F.mono, fontSize: 12, align: "center", valign: "middle", charSpacing: 1, color: HEX.gris });
  });
  // fecha y edicion entre filetes
  T(s, "ROSARIO, " + FECHA_MAY, { x: M, y: 2.1, w: 4.6, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.tinta, charSpacing: 1, valign: "middle" });
  T(s, "EDICIÓN ESPECIAL · WEB MINING · GRUPO 3", { x: 4.2, y: 2.1, w: 4.95, h: 0.28, fontFace: F.mono, fontSize: 11, bold: true, color: HEX.tinta, charSpacing: 1, align: "center", valign: "middle" });
  T(s, "AÑO 1 · N.º 1 · PRECIO: UNA PREGUNTA", { x: W - M - 4.0, y: 2.1, w: 4.0, h: 0.28, fontFace: F.mono, fontSize: 11, color: HEX.tinta, charSpacing: 1, align: "right", valign: "middle" });
  // firma
  hFilete(s, M, 5.82, 8.0);
  T(s, [{ text: "Por Grupo 3: ", options: { bold: true } }, { text: "Martín Ceriotti · Miguel Garrone · Lucía Tamplin · Milagros Terán" }], { x: M, y: 5.92, w: 8.1, h: 0.32, fontSize: 16 });
  T(s, "Docentes: Enrique Fernández · Héctor E. Giorgiutti", { x: M, y: 6.27, w: 8.1, h: 0.3, fontSize: 15, color: HEX.gris });
  T(s, "UNIVERSIDAD AUSTRAL · SEDE ROSARIO · 2026", { x: M, y: 6.62, w: 8.1, h: 0.28, fontFace: F.mono, fontSize: 12, color: HEX.gris, charSpacing: 2 });
  // columna lateral: recortes reales
  vFilete(s, 9.0, 2.62, 6.92);
  cabezaColumna(s, 9.25, 2.62, W - M - 9.25, "Hoy en los medios");
  let yy = 3.1;
  for (const [i, n] of D.tapa.slice(0, 3).entries()) {
    yy += (await recorte(s, { x: 9.3, y: yy, w: 3.35, titulo: n.titulo, medio: n.medio, hora: n.hora, fs: 15.5, rot: [-1.4, 1.1, -0.7][i] })) + 0.14;
  }
  s.addNotes("Presentación. La pregunta del título es el hilo de toda la charla: cada día los medios cuentan los mismos hechos con énfasis distintos, y queremos medirlo de forma automática. " +
    "Armamos la presentación como un diario, La Tapa, porque eso es lo que hace el sistema: leer a los diarios. Los recortes de la derecha son titulares reales de los últimos días, sacados de nuestra base.");

  // ===== 2. El problema =====
  const H = D.historia;
  s = pagina("Apertura", "El problema", `Un mismo día, contado de ${tot.medios} maneras`,
    `La historia más compartida de los últimos tres días llegó a ${H.medios} medios. Y cada media hora entran ≈3.000 titulares: nadie puede leerlos a mano.`,
    `Nadie puede leer 3.000 titulares por hora. Las preguntas interesantes no están en una nota sino en el conjunto. Estos recortes son reales: la misma noticia en ${H.medios} medios, ` +
    `con la hora de publicación de cada uno (el primero, ${H.recortes[0].medio} a las ${H.recortes[0].hora}). Las cinco preguntas de la derecha guían todo el trabajo.`);
  const pos2 = [[M, 2.75, -1.6], [M + 3.95, 2.82, 1.2], [M + 0.15, 4.12, 0.9], [M + 4.05, 4.2, -1.1], [M, 5.5, -0.6], [M + 3.95, 5.55, 1.5]];
  for (const [i, n] of H.recortes.slice(0, 6).entries()) {
    const [x, y, r] = pos2[i];
    await recorte(s, { x, y, w: 3.75, titulo: n.titulo, medio: n.medio, hora: n.hora, fs: 14.5, rot: r, extra: i === 0 ? "PRIMERO" : demora(n.demora_min) });
  }
  vFilete(s, 8.75, 2.7, 6.9);
  cabezaColumna(s, 9.0, 2.7, W - M - 9.0, "Sumario: cinco preguntas");
  ["¿De qué se habla hoy y qué crece respecto de lo habitual?", "¿Qué medios cubren un tema o una persona, y con qué tono?", "¿Qué noticias cubre todo el ecosistema y cuáles son exclusivas?",
   "¿Quién titula de forma más alarmista o con más clickbait?", "¿Cuánto contenido está firmado y cuánto sale como «Redacción»?"].forEach((q, i) => {
    T(s, String(i + 1), { x: 9.0, y: 3.12 + i * 0.75, w: 0.4, h: 0.6, fontFace: F.titular, bold: true, fontSize: 28, color: i === 3 ? HEX.rojo : HEX.tinta });
    T(s, q, { x: 9.45, y: 3.15 + i * 0.75, w: W - M - 9.45, h: 0.62, fontSize: 14.5 });
  });

  // ===== 3. La solucion en cifras =====
  s = pagina("Apertura", "La solución", "Un monitor que corre solo, cada 30 minutos, y publica todo",
    "Tres cifras para fijar la escala del trabajo.",
    `Tres números para fijar la escala: ${tot.medios} medios, ${fmt(tot.notas)} notas en la base y ${fmt(tot.corridas)} corridas automáticas desde el ${tot.desde.split("-").reverse().join("/")}. ` +
    "Todo corre en GitHub Actions sin intervención; el tablero y la base son públicos.");
  const c3 = [[`${tot.medios}`, "medios: diarios, portales, TV, radios y fuentes oficiales"], [fmt(tot.notas), "notas en la base, cada una con tema, tono, entidades y estilo de título"],
    [fmt(tot.corridas), "corridas automáticas en GitHub Actions; tablero y base SQL publicados en GitHub Pages"]];
  c3.forEach(([n, t], i) => {
    const x = M + i * (CW / 3) + (i ? 0.3 : 0);
    if (i) vFilete(s, M + i * (CW / 3), 2.8, 4.9);
    cifra(s, x, 2.75, CW / 3 - 0.5, n, t, i === 1 ? HEX.rojo : HEX.tinta, 96);
  });
  hFilete(s, M, 5.15, CW, 0.75);
  cita(s, M + 0.2, 5.5, CW - 0.4, "Web mining de punta a punta: crawling de feeds, scraping de cada nota, procesamiento de lenguaje con BERT, base histórica e indicadores comparables entre medios.", null, 21);

  // ===== 4. Como funciona =====
  pres.addSection({ title: "Cómo funciona" });
  s = pagina("Cómo funciona", "Infografía", "Seis etapas, de los feeds al tablero",
    "El recorrido de cada nota, de izquierda a derecha. El paso 3 es el que convierte esto en web mining.",
    "Recorrer el flujo de izquierda a derecha. Remarcar que el paso 3, entrar a cada nota, es lo que convierte esto en web mining real y no solo lectura de RSS.");
  const etapas = [["Feeds", "RSS y Google News de 46 medios, en paralelo"], ["Validación", "Descarta no-notas, fechas imposibles y duplicados"],
    ["Scraping", "Entra a cada nota: bajada y JSON-LD"], ["Lenguaje", "Tema, entidades, tono con BERT y cebo"],
    ["SQLite", "Base histórica y CSV exportable"], ["Tablero", "Pestañas + SQL en el navegador"]];
  const cw4 = CW / 6;
  linea(s, M, 3.05, CW - 0.05, 0, { width: 2.25, endArrowType: "triangle", nombre: "flecha-flujo" });
  etapas.forEach(([t, d], i) => {
    const x = M + i * cw4, rojo = i === 2;
    s.addShape(pres.shapes.OVAL, { x: x + 0.02, y: 2.94, w: 0.22, h: 0.22, fill: { color: rojo ? HEX.rojo : HEX.tinta }, line: { color: HEX.papel, width: 2 }, objectName: "estacion-" + i });
    if (i) vFilete(s, x - 0.12, 3.4, 5.6);
    T(s, String(i + 1), { x, y: 3.3, w: 1, h: 0.95, fontFace: F.titular, bold: true, fontSize: 60, color: rojo ? HEX.rojo : HEX.tinta });
    T(s, t, { x, y: 4.25, w: cw4 - 0.3, h: 0.45, fontFace: F.titular, bold: true, fontSize: 24 });
    T(s, d, { x, y: 4.72, w: cw4 - 0.3, h: 0.9, fontSize: 14, color: HEX.gris });
  });
  hFilete(s, M, 5.85, CW, 0.75);
  T(s, [{ text: "GITHUB ACTIONS — ", options: { fontFace: F.mono, bold: true, fontSize: 13, charSpacing: 1 } },
        { text: "corre el pipeline cada 30 minutos, guarda la base en una rama de datos y publica el tablero en GitHub Pages. La primera corrida con BERT tarda 10 minutos; las siguientes, 2." }],
    { x: M, y: 6.0, w: CW, h: 0.8, fontSize: 16 });

  // ===== 5. Fuentes =====
  s = pagina("Cómo funciona", "Fuentes", "Dos vías para llegar a 46 medios sin claves ni costo",
    "Las APIs de noticias limitan pedidos y no cubren medios regionales: combinamos RSS propio con Google News por sitio.",
    "Las APIs de noticias limitan pedidos y no cubren medios regionales. Un trabajo de 2025 terminó en NewsAPI. Nosotros combinamos RSS propio con Google News por sitio. " +
    `El problema de Google News: da una URL de redirección y ninguna bajada; lo resolvemos en la etapa de scraping. ${fmt(tot.notas_gn)} notas vienen de medios que solo llegan por Google News.`);
  [["RSS propio", `${tot.medios_rss} medios`, ["Feed XML del medio: título, enlace, fecha y bajada", "La vía más limpia y estable", "Clarín, Infobae, La Nación, La Capital, TN…"]],
   ["Google News por sitio", `${tot.medios_gn} medios`, ["Búsqueda site:dominio de las últimas 48 horas", "Cubre los medios sin RSS útil", "Pero devuelve una URL de Google y sin bajada"]]].forEach(([t, n, items], i) => {
    const x = M + i * (CW / 2 + 0.2);
    if (i) vFilete(s, M + CW / 2, 2.8, 5.55);
    T(s, n.toUpperCase(), { x, y: 2.75, w: 5.6, h: 0.3, fontFace: F.mono, fontSize: 13, bold: true, color: i ? HEX.rojo : HEX.tinta, charSpacing: 2 });
    T(s, t, { x, y: 3.05, w: 5.6, h: 0.65, fontFace: F.titular, bold: true, fontSize: 34 });
    T(s, items.map((it, k) => ({ text: it, options: { bullet: { characterCode: "25A0" }, breakLine: k < items.length - 1 } })),
      { x, y: 3.8, w: 5.6, h: 1.6, fontSize: 17, paraSpaceAfter: 8, indent: 14 });
  });
  hFilete(s, M, 5.8, CW, 0.75);
  T(s, [{ text: fmt(tot.notas_gn), options: { fontFace: F.titular, bold: true, fontSize: 40, color: HEX.rojo } },
        { text: `  de ${fmt(tot.notas)} notas vienen de medios que solo llegan por Google News: sin el paso siguiente, de ellas solo tendríamos el título.`, options: { fontSize: 17 } }],
    { x: M, y: 5.95, w: CW, h: 0.85, valign: "middle" });

  // ===== 6. Scraping =====
  s = pagina("Cómo funciona", "Scraping", "Entramos a cada nota para leer lo que el RSS no trae",
    "Los feeds son páginas de listado; cada nota es una página de detalle, con su bajada y sus datos estructurados.",
    "Distinción de clase: páginas de listado y de detalle. Los feeds son listados; cada nota es una página de detalle. Decodificamos el enlace de Google News, bajamos el HTML y leemos dos cosas: " +
    `la meta og:description (la bajada) y el bloque JSON-LD NewsArticle que los diarios incrustan para Google. ${pct(tot.ld, tot.notas)} de las notas lo traen.`);
  cifra(s, M, 2.7, 3.3, pct(tot.analizadas, tot.notas), "de las notas analizadas entrando a su página", HEX.rojo, 80);
  cifra(s, M, 4.75, 3.3, pct(tot.con_bajada, tot.notas), "con bajada: el resumen escrito por el propio medio", HEX.tinta, 80);
  vFilete(s, 4.15, 2.8, 6.85);
  cabezaColumna(s, 4.4, 2.75, 4.0, "Del HTML de cada nota");
  [["URL real", "decodificando el enlace de Google News"], ["Bajada", "meta og:description o primer párrafo"], ["Autor y firma", "persona o «Redacción», del JSON-LD"],
   ["Sección y claves", "como las clasifica el propio medio"], ["Largo", "cantidad de palabras del cuerpo"]].forEach(([a, b], i) => {
    T(s, [{ text: a, options: { fontFace: F.titular, bold: true, fontSize: 20, breakLine: true } }, { text: b, options: { color: HEX.gris } }], { x: 4.4, y: 3.2 + i * 0.73, w: 4.0, h: 0.7, fontSize: 14 });
  });
  vFilete(s, 8.65, 2.8, 6.85);
  const ej = H.recortes[0];
  const jsonld = ['<script type="application/ld+json">', "{", '  "@type": "NewsArticle",', `  "headline": "${ej.titulo.split(" ").slice(0, 2).join(" ").slice(0, 18)}…",`, '  "author": {', '    "@type": "Person",', '    "name": "…"', "  },", '  "articleSection": "Deportes",', '  "wordCount": 412', "}"];
  s.addShape(pres.shapes.RECTANGLE, { x: 8.9, y: 2.8, w: W - M - 8.9, h: 3.4, rotate: 0.8, fill: { color: HEX.papelClaro }, line: { color: HEX.gris, width: 0.75 }, objectName: "jsonld" });
  T(s, jsonld.map((l, k) => ({ text: l, options: { breakLine: k < jsonld.length - 1, color: k === 4 || k === 6 ? HEX.rojo : HEX.tinta } })), { x: 9.05, y: 2.97, w: W - M - 9.15, h: 3.1, rotate: 0.8, fontFace: F.mono, fontSize: 13, objectName: "jsonld-texto" });
  T(s, "JSON-LD: LO QUE EL DIARIO LE DICE A GOOGLE", { x: 8.9, y: 6.4, w: W - M - 8.9, h: 0.26, fontFace: F.mono, fontSize: 10.5, color: HEX.gris });

  // ===== 7. Crawler bien educado =====
  s = pagina("Cómo funciona", "Ética desde el diseño", "Un crawler «bien educado», como pide la teoría",
    "Cuatro reglas que el sistema cumple en cada corrida, como un reglamento de la casa.",
    `Ninguno de los trabajos de 2025 trató este punto. Respetamos robots.txt (${fmt(D.scrap.robots)} bloqueo en ${fmt(D.scrap.pedidos)} pedidos), nos identificamos, limitamos la carga ` +
    "y no guardamos el texto completo de las notas: solo título, bajada y metadatos, siempre enlazando al original.");
  [["robots.txt", `Se lee por dominio antes de pedir una nota: ${fmt(D.scrap.robots)} bloqueo en ${fmt(D.scrap.pedidos)} pedidos.`],
   ["Nos identificamos", "User-Agent propio que enlaza al proyecto: monitor-de-medios/1.0."],
   ["Carga acotada", "Máximo 2 pedidos a la vez por sitio y topes de notas y de tiempo por corrida."],
   ["Sin insistir", "Reintentos con espera creciente; una nota que falla dos veces no se vuelve a pedir."]].forEach(([t, d], i) => {
    const x = M + (i % 2) * (CW / 2 + 0.25), y = 2.8 + Math.floor(i / 2) * 1.75;
    T(s, `ART. ${i + 1}`, { x, y, w: 1.0, h: 0.3, fontFace: F.mono, fontSize: 12, bold: true, color: HEX.rojo, charSpacing: 2 });
    T(s, t, { x: x + 1.05, y: y - 0.1, w: 4.6, h: 0.5, fontFace: F.titular, bold: true, fontSize: 28 });
    T(s, d, { x: x + 1.05, y: y + 0.45, w: 4.65, h: 0.9, fontSize: 16 });
  });
  vFilete(s, M + CW / 2, 2.8, 6.2);
  hFilete(s, M, 4.4, CW);
  hFilete(s, M, 6.3, CW, 0.75);
  T(s, "No guardamos el texto completo de las notas: solo título, bajada y metadatos, siempre con enlace al original.", { x: M, y: 6.42, w: CW, h: 0.4, fontSize: 15, italic: true, color: HEX.gris });

  // ===== 8. Procesamiento de texto =====
  const ejn = D.ejemplo_nlp;
  s = pagina("Cómo funciona", "Procesamiento de texto", "Cada nota recibe tema, entidades, tono y cebo",
    "Bolsa de palabras y modelo vectorial como base; un titular real, tal como lo procesa el sistema.",
    "Bolsa de palabras y modelo vectorial como base. Temas: reglas sobre título y bajada más un Naive Bayes con supervisión débil, que aprende de lo que las reglas clasificaron y solo asigna tema si está seguro. " +
    `Entidades: diccionario con alias. Tono: lo vemos en la próxima. El ejemplo de arriba es un titular real de ${ejn.medio}.`);
  const hEj = await recorte(s, { x: M + 0.1, y: 2.72, w: 6.3, titulo: ejn.titulo, medio: ejn.medio, hora: ejn.hora, fs: 19, rot: -0.8 });
  const etiq = [["TEMA", ejn.temas.join(", "), HEX.tinta], ["ENTIDADES", ejn.entidades.join(", "), HEX.tinta], ["TONO", TONO[ejn.tono][0].toLowerCase(), TONO[ejn.tono][1]], ["CEBO", "ninguno", HEX.tinta]];
  etiq.forEach(([a, b, c], i) => T(s, [{ text: a + "  ", options: { bold: true, color: HEX.gris } }, { text: b, options: { bold: true, color: c } }],
    { x: 7.3, y: 2.78 + i * 0.36, w: 5.4, h: 0.32, fontFace: F.mono, fontSize: 13, charSpacing: 1 }));
  linea(s, 6.75, 2.72 + hEj / 2, 0.45, 0, { width: 1, endArrowType: "triangle", nombre: "flecha-ejemplo" });
  hFilete(s, M, 4.45, CW, 0.75);
  [["Temas", "15 temas. Reglas sobre título + bajada, y un Naive Bayes que aprende de lo que las reglas ya clasificaron (supervisión débil).", "«Otros»: de 24% a menos de 5%"],
   ["Entidades", "Personas, instituciones y clubes con sus alias y reglas de desambiguación («Banco Central» no es Rosario Central).", `Más mencionado: ${D.ents[0][0]}`],
   ["Tono", "Si el hecho es bueno o malo para los involucrados. Palabras + probabilidades de BERT, sobre el título y sobre la bajada.", "77% de acierto con validación cruzada"]].forEach(([t, d, dato], i) => {
    const x = M + i * (CW / 3) + (i ? 0.25 : 0), w = CW / 3 - 0.4;
    if (i) vFilete(s, M + i * (CW / 3), 4.6, 6.85);
    T(s, t, { x, y: 4.55, w, h: 0.5, fontFace: F.titular, bold: true, fontSize: 26 });
    T(s, d, { x, y: 5.08, w, h: 1.25, fontSize: 14, color: HEX.gris });
    T(s, dato.toUpperCase(), { x, y: 6.45, w, h: 0.35, fontFace: F.mono, fontSize: 11, bold: true, charSpacing: 1, color: i === 2 ? HEX.rojo : HEX.tinta });
  });

  // ===== 9. Tono con BERT =====
  s = pagina("Cómo funciona", "Tono con BERT", "Combinar palabras con BERT sube el acierto de 70% a 77%",
    "Ocho enfoques comparados sobre 340 titulares etiquetados a mano, con validación cruzada de 5 pliegues.",
    "Comparamos 8 enfoques sobre 340 titulares etiquetados a mano, con validación cruzada de 5 pliegues. Un BERT entrenado con tuits (pysentimiento) rinde peor que el modelo simple: mide la emoción de quien escribe, " +
    "no si el hecho es bueno o malo. La combinación de rasgos propios con XLM-RoBERTa gana, y sobre todo detecta muchas más noticias negativas.");
  barras(s, D.modelos_tono, { x: M - 0.15, y: 2.6, w: 8.0, h: 4.3, rojo: [D.modelos_tono[0][0]], nombre: "grafico-modelos" });
  vFilete(s, 8.65, 2.75, 6.85);
  cifra(s, 8.95, 2.6, 3.8, "77%", "de acierto (antes 70%), medido con notas que el modelo no vio", HEX.rojo, 88);
  hFilete(s, 8.95, 4.65, W - M - 8.95);
  cifra(s, 8.95, 4.6, 3.8, "84%", "de las notas negativas detectadas (antes 65%)", HEX.tinta, 88);

  // ===== 10. El sistema aprende =====
  s = pagina("Cómo funciona", "Más allá del diccionario", "El sistema aprende lo que no le enseñamos",
    "Tres técnicas para no depender solo de listas fijas.",
    "Tres técnicas para que el sistema no dependa solo de listas fijas. NER con spaCy descubre figuras nuevas, como Fundación Faro o Gonzalo Belloso. Los embeddings de oraciones encuentran la misma noticia contada con otras palabras " +
    "y permiten buscar por significado desde el navegador. El aprendizaje activo elige los titulares donde el modelo de tono duda para que los etiquetemos a mano: el modelo pide ayuda donde más la necesita. " +
    "En la primera ronda (60 titulares) el acierto se mantuvo en 76%: el modelo coincidía con nosotros solo en el 42% de esos casos y, aun reentrenado, acierta el 37% en ellos, casi el azar. " +
    "Conclusión honesta: no eran errores aprendibles sino titulares ambiguos; la ronda sirvió para delimitar la frontera del criterio.");
  [["Figuras nuevas (NER)", "Fundación Faro\nGonzalo Belloso", 30, "spaCy detecta personas e instituciones que no están en el diccionario y marca las que irrumpen hoy en la agenda."],
   ["Búsqueda por significado", "0,85", 72, "Embeddings MiniLM: notas parecidas de otros medios aunque no compartan palabras. «Murió una joven embarazada…» y su par en La Voz: similitud 0,85."],
   ["Aprendizaje activo", "76% → 76%", 54, "El modelo eligió los 60 titulares donde más dudaba; los etiquetamos a mano y reentrenamos. Eran casos ambiguos: la frontera del criterio."]].forEach(([t, big, pt, d], i) => {
    const x = M + i * (CW / 3) + (i ? 0.25 : 0), w = CW / 3 - 0.4;
    if (i) vFilete(s, M + i * (CW / 3), 2.8, 6.85);
    T(s, t.toUpperCase(), { x, y: 2.75, w, h: 0.3, fontFace: F.mono, fontSize: 12, bold: true, charSpacing: 2, color: HEX.rojo });
    T(s, big, { x, y: 3.1, w, h: 1.45, fontFace: F.titular, bold: true, fontSize: pt, valign: "middle" });
    hFilete(s, x, 4.7, w);
    T(s, d, { x, y: 4.85, w, h: 1.9, fontSize: 15 });
  });

  // ===== 11. El dia en un numero =====
  pres.addSection({ title: "Qué encontramos" });
  const tm = D.termo;
  s = pagina("Qué encontramos", "El día en un número", "Un termómetro y un resumen que se escriben solos",
    "Porcentaje estimado de notas negativas de las últimas 24 horas, de 0 a 100, contra los días anteriores.",
    "El termómetro es el porcentaje estimado de notas negativas de las últimas 24 horas, de 0 a 100, con bandas (calmo, moderado, tenso, muy tenso) y la comparación contra los días anteriores. " +
    "El resumen lo arma el tablero con plantillas a partir de los datos: tema más cubierto, noticia más compartida y quién la publicó primero, figura más mencionada, medio más y menos negativo. " +
    "No usa un modelo de lenguaje: es reproducible y gratis. Acá está reconstruido con los datos del " + tm.hasta.slice(0, 10).split("-").reverse().join("/") + ".");
  const gx = 2.55, gy = 5.35, R = 1.85;
  const bandas = [[0, 25, "CALMO"], [25, 40, "MODERADO"], [40, 55, "TENSO"], [55, 100, "MUY TENSO"]];
  bandas.forEach(([a, b], i) => s.addShape(pres.shapes.BLOCK_ARC, { x: gx - R, y: gy - R, w: 2 * R, h: 2 * R, angleRange: [180 + 1.8 * a + 0.7, 180 + 1.8 * b - 0.7], arcThicknessRatio: 0.2,
    fill: { color: mezcla(HEX.rojo, HEX.papel, [0.18, 0.4, 0.65, 0.92][i]) }, line: { type: "none" }, objectName: "termometro-banda-" + i }));
  const ang = Math.PI * (1 - Math.min(tm.val, 100) / 100), r0 = R * 0.62, r1 = R * 1.08;
  const ax = gx + r0 * Math.cos(ang), ay = gy - r0 * Math.sin(ang), bx = gx + r1 * Math.cos(ang), by = gy - r1 * Math.sin(ang);
  s.addShape(pres.shapes.LINE, { x: Math.min(ax, bx), y: Math.min(ay, by), w: Math.abs(bx - ax), h: Math.abs(by - ay), flipH: bx < ax, flipV: by < ay,
    line: { color: HEX.tinta, width: 4.5 }, objectName: "termometro-aguja" });
  T(s, String(tm.val), { x: gx - 1.2, y: gy - 1.25, w: 2.4, h: 1.05, fontFace: F.titular, bold: true, fontSize: 80, align: "center", valign: "bottom" });
  T(s, tm.banda.toUpperCase(), { x: gx - 1.5, y: gy - 0.18, w: 3.0, h: 0.3, fontFace: F.mono, fontSize: 14, bold: true, align: "center", charSpacing: 3, color: HEX.rojo });
  const dif = Math.round(tm.val - tm.prom);
  T(s, `${dif >= 0 ? "↑" : "↓"} ${Math.abs(dif)} ${Math.abs(dif) === 1 ? "pt" : "pts"} vs. el promedio de ${tm.dias.length} días (${dec(tm.prom)}%)`, { x: gx - 1.9, y: gy + 0.25, w: 3.8, h: 0.3, fontFace: F.mono, fontSize: 12, align: "center", color: HEX.gris });
  T(s, "0", { x: gx - R - 0.05, y: gy + 0.02, w: 0.4, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris });
  T(s, "100", { x: gx + R - 0.4, y: gy + 0.02, w: 0.45, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris, align: "right" });
  vFilete(s, 5.0, 2.75, 6.85);
  cabezaColumna(s, 5.25, 2.7, 4.2, "Resumen del día");
  const neg = D.neg, hs = D.historia;
  T(s, [{ text: "ROSARIO — ", options: { fontFace: F.mono, bold: true, fontSize: 13 } },
        { text: `En las últimas 24 horas se publicaron ${fmt(tm.n)} notas; el ${tm.val}% tuvo tono negativo (${tm.banda.toLowerCase()}). ` },
        { text: `La historia más compartida de los últimos días llegó a ${hs.medios} medios; la publicó primero ${hs.recortes[0].medio}. ` },
        { text: `La figura más mencionada es ${D.ents[0][0]}. El medio más negativo de la base es ${neg[0][0]} (${Math.round(neg[0][1])}%) y el menos, ${neg[neg.length - 1][0]} (${Math.round(neg[neg.length - 1][1])}%).` }],
    { x: 5.25, y: 3.15, w: 4.2, h: 3.65, fontSize: 16.5, paraSpaceAfter: 4, lineSpacingMultiple: 1.05 });
  vFilete(s, 9.7, 2.75, 6.85);
  cabezaColumna(s, 9.95, 2.7, W - M - 9.95, "% negativo, 7 días");
  s.addChart(pres.charts.BAR, [{ name: "% negativo", labels: tm.dias.map((d) => ddmm(d[0])), values: tm.dias.map((d) => d[1]) }], {
    x: 9.85, y: 3.1, w: W - M - 9.8, h: 3.7, barDir: "bar", barGapWidthPct: 35, chartColors: tm.dias.map((d) => (d[1] === Math.max(...tm.dias.map((z) => z[1])) ? HEX.rojo : HEX.gris)),
    catAxisLabelColor: HEX.tinta, catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, catAxisLineShow: false, catAxisOrientation: "maxMin",
    valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 55, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"',
    dataLabelFontFace: "+mn-lt", dataLabelFontSize: 12, dataLabelColor: HEX.tinta, dataLabelFontBold: true, showLegend: false, objectName: "grafico-7-dias",
  });

  // ===== 12. Como titula cada medio =====
  const exa = D.exag_ej.find((e) => e.bajada.length <= 150) || D.exag_ej[0];
  const cbe = D.cebo_ej.find((e) => e.marcas.some((m) => m[2] === "exagera") && e.titulo.length <= 80) || D.cebo_ej[0];
  const [fir, red] = D.firma_ej;
  s = pagina("Qué encontramos", "Cómo titula cada medio", "Tres indicadores para medir el estilo, no solo el contenido",
    "Cada uno con un ejemplo real de los últimos días.",
    "Exageración: comparamos el tono del título con el de la bajada, que es el resumen escrito por el propio medio. Cebo: rasgos de clickbait (preguntas, exclamaciones, adjetivos exagerados, intriga, segunda persona, listas). " +
    `Transparencia: notas firmadas por una persona según el JSON-LD. Ejemplos reales: ${exa.medio} (exageración), ${cbe.medio} (cebo), ${fir.medio} y ${red.medio} (firma).`);
  const filas12 = [["Exageración", "El título es negativo y la bajada del propio medio no lo es."], ["Cebo", "Preguntas, exclamaciones, adjetivos exagerados, intriga, segunda persona, listas."],
    ["Transparencia", "Notas firmadas por una persona; «Redacción» o el nombre del medio no cuentan."]];
  filas12.forEach(([t, d], i) => {
    const y = 2.68 + i * 1.42;
    if (i) hFilete(s, M, y - 0.1, CW);
    T(s, String(i + 1), { x: M, y, w: 0.55, h: 1.0, fontFace: F.titular, bold: true, fontSize: 54, color: HEX.rojo });
    T(s, t, { x: M + 0.65, y: y + 0.02, w: 3.9, h: 0.5, fontFace: F.titular, bold: true, fontSize: 26 });
    T(s, d, { x: M + 0.65, y: y + 0.52, w: 3.95, h: 0.75, fontSize: 14, color: HEX.gris });
  });
  vFilete(s, 5.35, 2.7, 6.85);
  await recorte(s, { x: 5.6, y: 2.68, w: 3.7, titulo: exa.titulo, medio: exa.medio, hora: exa.hora, fs: 14.5, rot: -0.8, pie: "TÍTULO: NEGATIVO", pieColor: HEX.rojo });
  T(s, [{ text: "BAJADA DEL MEDIO · NEUTRA", options: { fontFace: F.mono, fontSize: 10.5, bold: true, color: HEX.gris, charSpacing: 1, breakLine: true } }, { text: exa.bajada, options: { italic: true } }],
    { x: 9.55, y: 2.7, w: W - M - 9.55, h: 1.25, fontSize: 14 });
  await recorte(s, { x: 5.6, y: 4.18, w: 7.1, titulo: cbe.titulo, medio: cbe.medio, hora: cbe.hora, fs: 17, rot: 0.5, marcas: cbe.marcas, pie: ("RECURSOS: " + cbe.rasgos.join(" · ")).toUpperCase() });
  await recorte(s, { x: 5.6, y: 5.62, w: 3.45, titulo: fir.titulo, medio: fir.medio, hora: fir.hora, fs: 13.5, rot: -0.6, pie: ("POR " + fir.autor).toUpperCase(), pieColor: HEX.pos });
  await recorte(s, { x: 9.25, y: 5.62, w: 3.45, titulo: red.titulo, medio: red.medio, hora: red.hora, fs: 13.5, rot: 0.7, pie: ("POR " + red.autor + " · NO CUENTA").toUpperCase(), pieColor: HEX.rojo });

  // ===== 13. Cebo =====
  const [c1, c2] = D.cebo;
  const unoDe = Math.floor(100 / Math.min(c1[1], c2[1]));
  s = pagina("Qué encontramos", "Cebo", `${c1[0]} y ${c2[0]} usan cebo en más de 1 de cada ${unoDe} títulos`,
    `En el otro extremo, ${D.cebo.slice(-3).map((r) => r[0]).join(", ").replace(/, ([^,]*)$/, " y $1")} no llegan al ${Math.ceil(D.cebo[D.cebo.length - 3][1])}%.`,
    `Porcentaje de títulos con al menos un recurso de cebo, medios con 300 notas o más en la base. A la derecha, títulos reales de los últimos días con los recursos marcados en rojo, tal como los detecta el sistema. ` +
    `En el otro extremo, ${D.cebo.slice(-3).map((r) => r[0] + " (" + dec(r[1]) + "%)").join(", ")}.`);
  barras(s, D.cebo.slice(0, 10).map((r) => [r[0], r[1]]), { x: M - 0.15, y: 2.6, w: 7.0, h: 4.3, rojo: [c1[0], c2[0]], nombre: "grafico-cebo" });
  vFilete(s, 7.3, 2.75, 6.85);
  cabezaColumna(s, 7.55, 2.7, W - M - 7.55, "Marcados por el sistema");
  const ejCebo = [...D.cebo_ej].sort((a, b) => (b.marcas.some((m) => m[2] === "exagera") - a.marcas.some((m) => m[2] === "exagera"))).filter((e) => e !== cbe).slice(0, 3);
  yy = 3.15;
  for (const [i, e] of ejCebo.entries()) {
    yy += (await recorte(s, { x: 7.6, y: yy, w: W - M - 7.65, titulo: e.titulo, medio: e.medio, hora: e.hora, fs: 16, rot: [-1, 0.9, -0.5][i], marcas: e.marcas })) + 0.13;
  }

  // ===== 14. Mapa del sensacionalismo (dibujado con formas nativas) =====
  const ex = Object.fromEntries(D.exag.map((r) => [r[0], r[1]]));
  const pts = D.cebo.filter((r) => ex[r[0]] !== undefined).map((r) => ({ m: r[0], x: r[1], y: ex[r[0]] }));
  const med = (v) => { const o = [...v].sort((a, b) => a - b); return (o[Math.floor((o.length - 1) / 2)] + o[Math.ceil((o.length - 1) / 2)]) / 2; };
  const mx = med(pts.map((p) => p.x)), my = med(pts.map((p) => p.y));
  const sens = pts.filter((p) => p.x > mx && p.y > my).sort((a, b) => (b.x / mx + b.y / my) - (a.x / mx + a.y / my));
  const sobr = pts.filter((p) => p.x < mx && p.y < my).sort((a, b) => (a.x / mx + a.y / my) - (b.x / mx + b.y / my));
  s = pagina("Qué encontramos", "Sensacionalismo", "El mapa: quién exagera y quién busca el clic",
    "Cada punto es un medio. A la derecha, más cebo; arriba, más exageración respecto de su propia bajada.",
    "Cada punto es un medio. Eje horizontal: porcentaje de títulos con cebo. Eje vertical: exageración respecto de la propia bajada (de los títulos negativos con bajada, cuántos tienen una bajada que no es negativa). " +
    `Las líneas punteadas son las medianas y dividen en cuatro estilos. ${sens.slice(0, 4).map((p) => p.m).join(", ")} quedan como sensacionalistas; ${sobr.slice(0, 2).map((p) => p.m).join(" y ")} como sobrios. ` +
    "Es una medición automática con error conocido: sirve para comparar medios, no para juzgar uno.");
  const px = M + 0.55, py = 2.75, pw = 7.9, ph = 3.75;
  const xmax = Math.ceil(Math.max(...pts.map((p) => p.x)) / 5) * 5, ymin = Math.max(0, Math.floor((Math.min(...pts.map((p) => p.y)) - 6) / 10) * 10), ymax = Math.ceil((Math.max(...pts.map((p) => p.y)) + 6) / 10) * 10;
  const X = (v) => px + (v / xmax) * pw, Y = (v) => py + ph - ((v - ymin) / (ymax - ymin)) * ph;
  linea(s, px, py + ph, pw, 0, { width: 1 });
  linea(s, px, py, 0, ph, { width: 1 });
  linea(s, X(mx), py, 0, ph, { width: 0.75, dashType: "dash", color: HEX.gris });
  linea(s, px, Y(my), pw, 0, { width: 0.75, dashType: "dash", color: HEX.gris });
  [["ALARMISTAS", px + 0.1, py + 0.05, "left", HEX.gris], ["SENSACIONALISTAS", px + pw - 3.0, py + 0.05, "right", HEX.rojo], ["SOBRIOS", px + 0.1, py + ph - 0.33, "left", HEX.gris], ["CLICKBAIT", px + pw - 3.0, py + ph - 0.33, "right", HEX.gris]]
    .forEach(([t, x, y, al, c]) => T(s, t, { x, y, w: 2.9, h: 0.26, fontFace: F.mono, fontSize: 12, bold: true, charSpacing: 3, align: al, color: c }));
  const etiquetar = new Set([...sens.slice(0, 4), ...sobr.slice(0, 2)].map((p) => p.m));
  pts.forEach((p) => {
    const rojo = sens.slice(0, 4).includes(p);
    s.addShape(pres.shapes.OVAL, { x: X(p.x) - 0.07, y: Y(p.y) - 0.07, w: 0.14, h: 0.14, fill: { color: rojo ? HEX.rojo : HEX.tinta }, line: { color: HEX.papel, width: 0.75 }, objectName: "medio-" + p.m });
  });
  // etiquetas: se prueba a la derecha, izquierda, arriba y abajo del punto y se elige la que menos pisa otros puntos y etiquetas
  const puestas = [], choca = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  pts.filter((p) => etiquetar.has(p.m)).forEach((p) => {
    const lw = ancho(p.m, "Cambria|b", 13) + 0.06, lh2 = 0.26, cx2 = X(p.x), cy2 = Y(p.y);
    const opciones = [{ x: cx2 + 0.12, y: cy2 - lh2 / 2 }, { x: cx2 - 0.12 - lw, y: cy2 - lh2 / 2 }, { x: cx2 - lw / 2, y: cy2 - 0.12 - lh2 }, { x: cx2 - lw / 2, y: cy2 + 0.12 }]
      .map((o) => ({ ...o, w: lw, h: lh2 })).filter((o) => o.x >= px + 0.05 && o.x + o.w <= px + pw);
    const costo = (o) => 10 * puestas.filter((q) => choca(o, q)).length + pts.filter((q) => q !== p && choca(o, { x: X(q.x) - 0.08, y: Y(q.y) - 0.08, w: 0.16, h: 0.16 })).length;
    const o = opciones.sort((a, b) => costo(a) - costo(b))[0];
    puestas.push(o);
    T(s, p.m, { ...o, fontSize: 13, bold: true, wrap: false, valign: "middle", objectName: "etiqueta-" + p.m });
  });
  T(s, "0%", { x: px - 0.1, y: py + ph + 0.05, w: 0.6, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris });
  T(s, xmax + "%", { x: px + pw - 0.6, y: py + ph + 0.05, w: 0.6, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris, align: "right" });
  T(s, "% DE TÍTULOS CON CEBO →", { x: px + pw / 2 - 2, y: py + ph + 0.05, w: 4, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris, align: "center", charSpacing: 1 });
  T(s, ymax + "%", { x: M - 0.1, y: py - 0.05, w: 0.6, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris, align: "right" });
  T(s, ymin + "%", { x: M - 0.1, y: py + ph - 0.22, w: 0.6, h: 0.25, fontFace: F.mono, fontSize: 11, color: HEX.gris, align: "right" });
  T(s, "↑ EXAGERA", { x: M - 0.15, y: py + ph / 2 - 0.15, w: 0.65, h: 0.5, fontFace: F.mono, fontSize: 10, color: HEX.gris, align: "right" });
  vFilete(s, 9.35, 2.75, 6.85);
  cabezaColumna(s, 9.6, 2.7, W - M - 9.6, "Cómo leerlo");
  T(s, [{ text: "Arriba a la derecha: ", options: { bold: true } }, { text: "títulos con cebo que además exageran el hecho.", options: { breakLine: true } },
        { text: "Abajo a la izquierda: ", options: { bold: true } }, { text: "títulos sobrios y fieles a su bajada.", options: { breakLine: true } },
        { text: "Las líneas punteadas son las medianas de los medios.", options: { color: HEX.gris } }],
    { x: 9.6, y: 3.15, w: W - M - 9.6, h: 3.6, fontSize: 15, paraSpaceAfter: 12 });

  // ===== 15. Tono por medio =====
  const tt = D.tono.n + D.tono["0"] + D.tono.p;
  s = pagina("Qué encontramos", "Tono", `${neg[0][0]}: ${Math.round(neg[0][1])}% de notas negativas. ${neg[neg.length - 1][0]}: ${Math.round(neg[neg.length - 1][1])}%`,
    "Los cinco medios más negativos y los cinco menos negativos de la base.",
    `Proporción de notas con tono negativo según el modelo combinado, medios con 300 notas o más. Muestra los 5 más negativos y los 5 menos negativos (${neg[0][0]} ${dec(neg[0][1])}%, ${neg[neg.length - 1][0]} ${dec(neg[neg.length - 1][1])}%). ` +
    "El tono mide el hecho, no la postura del medio: un medio con más policiales tiene más negativas.");
  barras(s, [...neg.slice(0, 5).map((r) => [r[0], r[1]]), [" ", 0], ...neg.slice(-5).map((r) => [r[0], r[1]])],
    { x: M - 0.15, y: 2.6, w: 8.0, h: 4.3, rojo: neg.slice(0, 5).map((r) => r[0]), color: HEX.neutro, nombre: "grafico-tono" });
  vFilete(s, 8.65, 2.75, 6.85);
  cabezaColumna(s, 8.9, 2.7, W - M - 8.9, `En toda la base · ${fmt(tt)} notas`);
  [["negativas", D.tono.n, HEX.rojo], ["neutras", D.tono["0"], HEX.gris], ["positivas", D.tono.p, HEX.pos]].forEach(([l, v, c], i) => {
    T(s, pct(v, tt), { x: 8.9, y: 3.15 + i * 1.18, w: 2.0, h: 1.0, fontFace: F.titular, bold: true, fontSize: 60, color: c, valign: "bottom" });
    T(s, l, { x: 10.95, y: 3.55 + i * 1.18, w: 1.75, h: 0.5, fontSize: 18, valign: "bottom" });
  });

  // ===== 16. Transparencia =====
  const cero = D.firm.filter((r) => r[1] === 0).map((r) => r[0]);
  s = pagina("Qué encontramos", "Transparencia", `${D.firm[0][0]} firma el ${Math.round(D.firm[0][1])}% de sus notas; ${cero.length} medios, ninguna`,
    "Notas firmadas por una persona, según el autor que declara el JSON-LD de cada nota.",
    "Proporción de notas firmadas por una persona, según el autor declarado en el JSON-LD de cada nota. Medios con 200 notas o más con datos estructurados. «Redacción» o el nombre del medio no cuentan como firma.");
  barras(s, D.firm.slice(0, 9).map((r) => [r[0], r[1]]), { x: M - 0.15, y: 2.6, w: 8.0, h: 4.3, rojo: [D.firm[0][0]], nombre: "grafico-firmas" });
  vFilete(s, 8.65, 2.75, 6.85);
  cabezaColumna(s, 8.9, 2.7, W - M - 8.9, "Sin ninguna nota firmada");
  T(s, cero.slice(0, 7).map((m, k, arr) => ({ text: m, options: { breakLine: k < arr.length - 1 } })), { x: 8.9, y: 3.15, w: W - M - 8.9, h: 3.0, fontFace: F.titular, bold: true, fontSize: 24, lineSpacingMultiple: 0.95 });
  T(s, "0% de notas con firma de una persona", { x: 8.9, y: 6.45, w: W - M - 8.9, h: 0.3, fontFace: F.mono, fontSize: 11, color: HEX.gris });

  // ===== 17. Una noticia, muchos encuadres + primicia =====
  const en = D.encuadre, pr = D.primicia;
  s = pagina("Qué encontramos", "Encuadre", "Una noticia, muchos encuadres",
    `Una misma historia en ${en.medios} medios, en orden de publicación, con el tono que el sistema le asigna a cada título.`,
    "El sistema agrupa las notas que cuentan lo mismo (TF-IDF y similitud coseno ≥ 0,5) y muestra el título de cada medio en orden de publicación, con su tono y sus recursos de cebo. " +
    `En este ejemplo real, la historia llegó a ${en.medios} medios; la publicó primero ${en.recortes[0].medio} a las ${en.recortes[0].hora} y el último llegó ${demora(en.ultimo_min).slice(1)} después. ` +
    `Con eso también medimos quién llega primero: en los últimos tres días, ${pr[0][0]} fue el primero en ${pr[0][1]} historias que después cubrieron al menos tres medios.`);
  const pos17 = [[M, 2.72, -1.1], [M + 4.1, 2.78, 0.8], [M + 0.05, 4.16, 0.6], [M + 4.15, 4.22, -0.9], [M, 5.6, -0.4], [M + 4.1, 5.62, 1.1]];
  for (const [i, n] of en.recortes.slice(0, 6).entries()) {
    const [x, y, r] = pos17[i];
    await recorte(s, { x, y, w: 3.9, titulo: n.titulo, medio: n.medio, hora: n.hora, fs: 13.5, rot: r, extra: i === 0 ? "PRIMERO" : demora(n.demora_min), pie: "TONO: " + TONO[n.tono][0], pieColor: TONO[n.tono][1] });
  }
  vFilete(s, 8.9, 2.75, 6.85);
  cabezaColumna(s, 9.15, 2.7, W - M - 9.15, "Quién llega primero");
  T(s, "Medio que más veces publicó primero una historia que después cubrieron otros tres o más:", { x: 9.15, y: 3.12, w: W - M - 9.15, h: 0.9, fontSize: 14, color: HEX.gris });
  const empate = pr[1] && pr[1][1] === pr[0][1];
  T(s, empate ? `${pr[0][0]} y ${pr[1][0]}` : pr[0][0], { x: 9.15, y: 4.0, w: W - M - 9.15, h: empate ? 1.3 : 0.8, fontFace: F.titular, bold: true, fontSize: empate ? 34 : 44, color: HEX.rojo });
  T(s, `${pr[0][1]} veces en los últimos tres días, sobre ${D.historias_compartidas} historias compartidas.`, { x: 9.15, y: empate ? 5.35 : 4.9, w: W - M - 9.15, h: 0.7, fontSize: 15 });
  T(s, `Esta historia: ${en.tonos.n || 0} títulos negativos, ${en.tonos["0"] || 0} ${en.tonos["0"] === 1 ? "neutro" : "neutros"} y ${en.tonos.p || 0} positivos.`, { x: 9.15, y: 6.1, w: W - M - 9.15, h: 0.7, fontSize: 14, color: HEX.gris });

  // ===== 18. Tono por figura (tabla nativa) =====
  const fg = D.figuras;
  s = pagina("Qué encontramos", "Tono por figura", "Cómo trata cada medio a cada figura",
    "Porcentaje de notas negativas cuando el medio menciona a la figura, contra el promedio de todos los medios.",
    "Matriz medio por figura: porcentaje de notas negativas cuando el medio menciona a esa figura. Rojo: más negativo que el promedio de los medios con esa figura; verde: menos. Solo celdas con 10 notas o más. " +
    "Ojo: el tono mide el hecho, no la opinión del medio sobre la persona; muestra el método más que una conclusión.");
  const celda = Object.fromEntries(fg.celdas.map(([m, f, p, n]) => [m + "|" + f, [p, n]]));
  const bordeAbajo = (c = HEX.tinta, pt = 0.5) => [{ type: "none" }, { type: "none" }, { pt, color: c }, { type: "none" }];
  const cab = [{ text: "", options: { border: bordeAbajo(HEX.tinta, 1) } }, ...fg.figuras.map((f) => ({ text: f.toUpperCase(), options: { fontFace: F.mono, fontSize: 11, bold: true, align: "center", color: HEX.gris, border: bordeAbajo(HEX.tinta, 1), valign: "bottom" } }))];
  const filasT = fg.medios.map((m) => [{ text: m, options: { fontFace: F.titular, bold: true, fontSize: 18, border: bordeAbajo(HEX.grisClaro) } }, ...fg.figuras.map((f) => {
    const c = celda[m + "|" + f];
    if (!c) return { text: "·", options: { align: "center", color: HEX.gris, border: bordeAbajo(HEX.grisClaro) } };
    const d = c[0] - fg.prom[f], fill = d >= 12 ? mezcla(HEX.rojo, HEX.papel, 0.45) : d >= 6 ? mezcla(HEX.rojo, HEX.papel, 0.2) : d <= -12 ? mezcla(HEX.pos, HEX.papel, 0.45) : d <= -6 ? mezcla(HEX.pos, HEX.papel, 0.2) : null;
    return { text: c[0] + "%", options: { align: "center", fontFace: F.mono, fontSize: 15, bold: Math.abs(d) >= 12, ...(fill ? { fill: { color: fill } } : {}), border: bordeAbajo(HEX.grisClaro) } };
  })]);
  const pie18 = [{ text: "Todos los medios", options: { fontFace: F.cuerpo, italic: true, fontSize: 15, color: HEX.gris } }, ...fg.figuras.map((f) => ({ text: fg.prom[f] + "%", options: { align: "center", fontFace: F.mono, fontSize: 15, color: HEX.gris } }))];
  s.addTable([cab, ...filasT, pie18], { x: M, y: 2.7, w: 9.3, colW: [1.8, ...fg.figuras.map(() => 7.5 / fg.figuras.length)], rowH: [0.45, ...fg.medios.map(() => 0.42), 0.4], fontFace: F.cuerpo, fontSize: 15, color: HEX.tinta, valign: "middle", margin: [0, 0.05, 0, 0.05], objectName: "tabla-figuras" });
  vFilete(s, 10.2, 2.75, 6.85);
  cabezaColumna(s, 10.45, 2.7, W - M - 10.45, "Cómo leerla");
  T(s, [{ text: "Rojo: ", options: { bold: true, color: HEX.rojo } }, { text: "más negativo que el promedio de los medios con esa figura.", options: { breakLine: true } },
        { text: "Verde: ", options: { bold: true, color: HEX.pos } }, { text: "menos negativo.", options: { breakLine: true } },
        { text: "Celdas con 10 notas o más; «·», sin datos suficientes.", options: { color: HEX.gris } }],
    { x: 10.45, y: 3.15, w: W - M - 10.45, h: 3.6, fontSize: 15, paraSpaceAfter: 10 });

  // ===== 19. Mapa de medios =====
  const grafo = await entintar("grafo.png", [[[194, 198, 194], rgb("CFC7B8")], [[154, 162, 156], rgb("ADA597")], [[42, 120, 214], rgb(HEX.tinta)], [[235, 104, 52], rgb(HEX.rojo)],
    [[27, 175, 122], rgb("7A7368")], [[28, 36, 33], rgb(HEX.tinta)]], { left: 0, top: 0, width: 1780, height: 1060 });
  s = pagina("Qué encontramos", "Minería de estructura", "El mapa de medios: quién comparte agenda con quién",
    "Dos medios quedan unidos cuando cubren las mismas historias; los colores son comunidades detectadas solas.",
    "Grafo de medios: una arista une a dos medios que cubren las mismas historias, ponderada por historias compartidas sobre las del medio más chico; cada medio conserva sus 3 vínculos más fuertes. " +
    "Las comunidades salen de propagación de etiquetas y el dibujo es una disposición por fuerzas. Es la rama de minería de estructura de la teoría, aplicada a la cobertura y no a los links.");
  const gh = 3.8, gw = gh * grafo.w / grafo.h;
  foto(s, grafo.data, M, 2.72, gw, gh, "FOTO: TABLERO, PESTAÑA ANÁLISIS · COLORES = COMUNIDADES", "grafo");
  vFilete(s, M + gw + 0.3, 2.75, 6.85);
  const gx2 = M + gw + 0.55;
  cabezaColumna(s, gx2, 2.7, W - M - gx2, "Cómo se arma");
  T(s, ["Nodos: medios; el tamaño, según historias compartidas", "Aristas: los dos cubren las mismas historias", "Colores: comunidades por propagación de etiquetas", "Disposición por fuerzas, animada en el tablero"]
    .map((it, k, arr) => ({ text: it, options: { bullet: { characterCode: "25A0" }, breakLine: k < arr.length - 1 } })),
    { x: gx2, y: 3.15, w: W - M - gx2, h: 3.6, fontSize: 15, paraSpaceAfter: 10, indent: 14 });

  // ===== 20. Clima mediatico y dolar (nueva) =====
  const cl = D.clima, r = D.clima_r;
  const blues = D.dolar_blue.map((b) => b[1]);
  s = pagina("Qué encontramos", "Clima mediático y dólar", "¿Se pone más negativa la agenda cuando sube el dólar?",
    `% de notas negativas y dólar blue, día por día (${cl.length} días). Dos gráficos alineados, un solo calendario.`,
    `Arriba, el porcentaje de notas negativas de cada día; abajo, el dólar blue (venta) del mismo día. Son ${cl.length} días con datos completos. ` +
    `La correlación entre las dos series es r = ${dec(r)}, pero con tan pocos días eso no se distingue del azar, y el blue casi no se movió (entre $${fmt(Math.min(...blues))} y $${fmt(Math.max(...blues))} en 30 días). ` +
    "Conclusión honesta: con estos datos no podemos afirmar ninguna relación. El tablero acumula la serie; con meses de datos se podrá probar.");
  const lay = { x: 0.01, y: 0.12, w: 0.98, h: 0.76 };
  const comun = { catAxisLabelColor: HEX.tinta, catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, catAxisLineShow: false, catGridLine: { style: "none" }, valAxisHidden: true, valGridLine: { style: "none" },
    showValue: true, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: HEX.tinta, showLegend: false, layout: lay };
  const maxNeg = Math.max(...cl.map((c) => c.neg));
  T(s, "% DE NOTAS NEGATIVAS POR DÍA", { x: M, y: 2.68, w: 6, h: 0.25, fontFace: F.mono, fontSize: 11, bold: true, color: HEX.tinta, charSpacing: 1 });
  s.addChart(pres.charts.BAR, [{ name: "% negativo", labels: cl.map((c) => ddmm(c.dia)), values: cl.map((c) => c.neg) }], {
    ...comun, x: M, y: 2.9, w: 8.6, h: 1.95, barDir: "col", barGapWidthPct: 40, chartColors: cl.map((c) => (c.neg === maxNeg ? HEX.rojo : HEX.gris)),
    valAxisMinVal: 0, valAxisMaxVal: maxNeg * 1.2, dataLabelPosition: "outEnd", dataLabelFormatCode: "0", catAxisHidden: true, objectName: "grafico-clima-negativo",
  });
  hFilete(s, M, 4.95, 8.6, 0.5);
  T(s, "DÓLAR BLUE, VENTA ($)", { x: M, y: 5.0, w: 6, h: 0.25, fontFace: F.mono, fontSize: 11, bold: true, color: HEX.tinta, charSpacing: 1 });
  s.addChart(pres.charts.LINE, [{ name: "dólar blue", labels: cl.map((c) => ddmm(c.dia)), values: cl.map((c) => c.blue) }], {
    ...comun, x: M, y: 5.2, w: 8.6, h: 1.75, chartColors: [HEX.tinta], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 5, valAxisMinVal: Math.min(...cl.map((c) => c.blue)) - 25, valAxisMaxVal: Math.max(...cl.map((c) => c.blue)) + 15,
    dataLabelPosition: "t", dataLabelFormatCode: "#,##0", dataLabelFontSize: 10.5, layout: { x: 0.01, y: 0.2, w: 0.98, h: 0.55 }, objectName: "grafico-clima-dolar",
  });
  vFilete(s, 9.5, 2.75, 6.85);
  cabezaColumna(s, 9.75, 2.7, W - M - 9.75, "Lo que se puede decir");
  T(s, "r = " + dec(r), { x: 9.75, y: 3.1, w: 3.0, h: 1.0, fontFace: F.titular, bold: true, fontSize: 60, color: HEX.rojo, valign: "bottom" });
  T(s, `con ${cl.length} días: no se distingue del azar. Y el blue casi no se movió: entre $${fmt(Math.min(...blues))} y $${fmt(Math.max(...blues))} en 30 días.`, { x: 9.75, y: 4.15, w: W - M - 9.75, h: 1.3, fontSize: 15 });
  hFilete(s, 9.75, 5.5, W - M - 9.75);
  T(s, "No afirmamos correlación. La serie se sigue acumulando: con meses de datos se podrá probar.", { x: 9.75, y: 5.62, w: W - M - 9.75, h: 1.2, fontSize: 15, italic: true });

  // ===== 21. Tablero + demo SQL =====
  pres.addSection({ title: "Cierre" });
  const tab = await entintar("tablero-resumen.png", [[[230, 233, 227], rgb("E6DFD0")], [[217, 220, 213], rgb("D9D1C2")], [[154, 162, 156], rgb(HEX.neutro)], [[181, 72, 58], rgb(HEX.rojo)],
    [[28, 36, 33], rgb(HEX.tinta)], [[31, 95, 139], rgb(HEX.tinta)], [[61, 138, 90], rgb(HEX.pos)], [[102, 112, 105], rgb(HEX.gris)]], { left: 120, top: 40, width: 1760, height: 1150 });
  s = pagina("Cierre", "El tablero · demo en vivo", "Todo esto, en un tablero público que se consulta con SQL",
    "Una página estática en GitHub Pages: funciona en el celular y abre la base en el navegador, sin instalar nada.",
    "Mostrar el tablero en vivo: Resumen, Titulares (con buscador), Monitor (seguir una persona), Cómo titulan y Salud de datos. Después tocar «Explorar la base (SQL)»: Datasette Lite corre SQLite en el navegador con WebAssembly. " +
    `Correr esta consulta sobre la tabla notas (últimos 7 días, ${fmt(D.explorar.notas)} notas) y después una propuesta por la clase. A la derecha, el resultado real al ${D.explorar.hasta.slice(0, 10).split("-").reverse().join("/")}.`);
  const tw21 = 5.9, th21 = tw21 * tab.h / tab.w;
  foto(s, tab.data, M, 2.72, tw21, th21, "FOTO: EL TABLERO, PESTAÑA RESUMEN", "tablero");
  vFilete(s, M + tw21 + 0.3, 2.75, 6.85);
  const sx = M + tw21 + 0.55, sw = W - M - sx;
  const sql = ["SELECT medio,", "  ROUND(100*AVG(cebo>=1), 1) AS cebo,", "  ROUND(100*AVG(tono='n'), 1) AS neg", "FROM notas", "GROUP BY medio", "HAVING COUNT(*) >= 50", "ORDER BY cebo DESC;"];
  s.addShape(pres.shapes.RECTANGLE, { x: sx, y: 2.72, w: sw, h: 2.15, fill: { color: HEX.papelClaro }, line: { color: HEX.gris, width: 0.75 }, objectName: "consulta" });
  T(s, sql.map((l, k) => ({ text: l, options: { breakLine: k < sql.length - 1 } })), { x: sx + 0.2, y: 2.85, w: sw - 0.3, h: 1.9, fontFace: F.mono, fontSize: 15, objectName: "consulta-sql" });
  T(s, "RESULTADO", { x: sx, y: 5.0, w: 2, h: 0.25, fontFace: F.mono, fontSize: 11, bold: true, charSpacing: 2, color: HEX.gris });
  const filasSql = [["medio", "cebo", "neg"], ...D.sql_demo.slice(0, 5).map((r2) => [r2[0], dec(r2[1].toFixed(1)), dec(r2[2].toFixed(1))])];
  s.addTable(filasSql.map((f, i) => f.map((c, j) => ({ text: c, options: { bold: i === 0, color: i === 0 ? HEX.gris : j === 1 && i === 1 ? HEX.rojo : HEX.tinta, align: j ? "right" : "left", border: bordeAbajo(i === 0 ? HEX.tinta : HEX.grisClaro, i === 0 ? 0.75 : 0.5) } }))),
    { x: sx, y: 5.27, w: sw, colW: [sw - 2.2, 1.1, 1.1], rowH: 0.26, fontFace: F.mono, fontSize: 13, margin: [0, 0.04, 0, 0.04], valign: "middle", objectName: "resultado-sql" });

  // ===== 22. Ficha tecnica (el stack como staff del diario) =====
  s = pagina("Cierre", "Ficha técnica", "Staff: un stack simple, gratuito y reproducible",
    "Sin servidores ni costos: todo corre en GitHub. Así se reparten las tareas en la redacción.",
    "Sin servidores ni costos: todo corre en GitHub. SQLite simplifica la operación y se puede abrir en el navegador. Leímos el stack como el staff de un diario: quién junta, quién corrige, quién edita, quién imprime.");
  s.addShape(pres.shapes.RECTANGLE, { x: M + 0.4, y: 2.72, w: CW - 0.8, h: 4.1, fill: { type: "none" }, line: { color: HEX.tinta, width: 2 }, objectName: "staff-marco" });
  s.addShape(pres.shapes.RECTANGLE, { x: M + 0.48, y: 2.8, w: CW - 0.96, h: 3.94, fill: { type: "none" }, line: { color: HEX.tinta, width: 0.5 }, objectName: "staff-marco-fino" });
  T(s, "STAFF", { x: M + 0.5, y: 2.9, w: CW - 1.0, h: 0.4, fontFace: F.mono, fontSize: 15, bold: true, charSpacing: 8, align: "center" });
  const staff = [["Cronistas · recolección", "requests · feedparser · googlenewsdecoder · urllib.robotparser"], ["Correctores · extracción", "expresiones regulares · JSON-LD (schema.org) · HTML"],
    ["Editores · lenguaje", "bolsa de palabras · Naive Bayes · regresión logística · XLM-RoBERTa · MiniLM · spaCy"], ["Archivo · datos", "SQLite · CSV · Datasette Lite · notebook con pandas"],
    ["Imprenta · automatización", "GitHub Actions cada 30 minutos · pruebas automáticas"], ["Diagramación · visualización", "HTML, CSS y JavaScript sin frameworks · GitHub Pages"]];
  const sw22 = (CW - 1.4) / 3;
  staff.forEach(([rol, quien], i) => {
    const x = M + 0.75 + (i % 3) * sw22, y = 3.45 + Math.floor(i / 3) * 1.55;
    if (i % 3) vFilete(s, x - 0.12, y, y + 1.3);
    T(s, rol.toUpperCase(), { x, y, w: sw22 - 0.3, h: 0.28, fontFace: F.mono, fontSize: 11, bold: true, charSpacing: 1, color: HEX.rojo, align: "center" });
    T(s, quien, { x, y: y + 0.32, w: sw22 - 0.3, h: 1.0, fontSize: 16, align: "center" });
  });
  hFilete(s, M + 2.0, 4.92, CW - 4.0);

  // ===== 23. Lo que aprendimos =====
  s = pagina("Cierre", "Editorial", "Cómo nos cuentan las noticias: lo que aprendimos",
    "Tres conclusiones, con la cautela de una medición automática con error conocido.",
    `Tres conclusiones. Uno: el estilo se mide. Cebo y exageración separan a los medios de forma estable: ${c1[0]} y ${c2[0]} en un extremo, ${D.cebo[D.cebo.length - 1][0]} en el otro. ` +
    "Dos: el tono mide el hecho, no la postura; combinar rasgos propios con BERT llega a 77%, y lo que queda son titulares ambiguos (el aprendizaje activo lo mostró). " +
    `Tres: la agenda es compartida: en tres días hubo ${D.historias_compartidas} historias cubiertas por tres o más medios, y la carrera por publicar primero se puede medir. Además, un crawler respetuoso alcanza: ${fmt(D.scrap.robots)} bloqueo en ${fmt(D.scrap.pedidos)} pedidos.`);
  [["El estilo se mide", `El cebo y la exageración separan a los medios de forma estable: ${c1[0]} y ${c2[0]} titulan con cebo en más de 1 de cada ${unoDe} notas; ${D.cebo[D.cebo.length - 1][0]}, casi nunca.`],
   ["El tono mide el hecho", "No la postura del medio. Palabras + BERT llegan a 77%; lo que falla son titulares ambiguos, la frontera del propio criterio."],
   ["La agenda es compartida", `En tres días, ${D.historias_compartidas} historias llegaron a tres medios o más. Se puede medir quién llega primero y cómo encuadra cada uno.`]].forEach(([t, d], i) => {
    const x = M + i * (CW / 3) + (i ? 0.25 : 0), w = CW / 3 - 0.4;
    if (i) vFilete(s, M + i * (CW / 3), 2.8, 5.55);
    T(s, ["I", "II", "III"][i], { x, y: 2.65, w, h: 0.9, fontFace: F.titular, bold: true, fontSize: 54, color: HEX.rojo });
    T(s, t, { x, y: 3.55, w, h: 0.55, fontFace: F.titular, bold: true, fontSize: 28 });
    T(s, d, { x, y: 4.15, w, h: 1.45, fontSize: 15 });
  });
  hFilete(s, M, 5.75, CW, 0.75);
  cita(s, M + 0.2, 6.0, CW - 0.4, "Cada día los medios cuentan los mismos hechos con énfasis distintos. Ahora lo podemos medir.", null, 20);

  // ===== 24. Cierre (contratapa) =====
  s = pres.addSlide({ masterName: "CONTRATAPA", sectionTitle: "Cierre" });
  s.addText("PROBALO AHORA", { placeholder: "volanta" });
  s.addText("Gracias", { placeholder: "title" });
  s.addText("Escaneá el código para abrir el tablero y consultar la base con SQL. ¿Preguntas?", { placeholder: "bajada" });
  hFilete(s, M, 4.6, 7.4, 0.75);
  T(s, [{ text: "Grupo 3: ", options: { bold: true } }, { text: "Martín Ceriotti · Miguel Garrone · Lucía Tamplin · Milagros Terán" }], { x: M, y: 4.75, w: 7.6, h: 0.65, fontSize: 17 });
  T(s, "Docentes: Enrique Fernández · Héctor E. Giorgiutti", { x: M, y: 5.45, w: 7.6, h: 0.32, fontSize: 15, color: HEX.gris });
  T(s, [{ text: "CÓDIGO  ", options: { bold: true, color: HEX.gris } }, { text: "github.com/miguegarrone-blip/Web-Mining" }], { x: M, y: 5.95, w: 7.6, h: 0.3, fontFace: F.mono, fontSize: 14 });
  T(s, "UNIVERSIDAD AUSTRAL · SEDE ROSARIO · MAESTRÍA EN CIENCIA DE DATOS · 2026", { x: M, y: 6.4, w: 7.6, h: 0.3, fontFace: F.mono, fontSize: 11, color: HEX.gris, charSpacing: 1 });
  vFilete(s, 8.55, 1.25, 6.85);
  s.addShape(pres.shapes.RECTANGLE, { x: 9.2, y: 1.35, w: 3.5, h: 3.5, fill: { color: "FFFFFF" }, line: { color: HEX.tinta, width: 1 }, objectName: "qr-marco" });
  s.addImage({ path: IMG("qr-tablero.png"), x: 9.35, y: 1.5, w: 3.2, h: 3.2, objectName: "qr", altText: "Código QR al tablero" });
  T(s, "EL TABLERO, EN VIVO", { x: 8.85, y: 5.0, w: 4.2, h: 0.28, fontFace: F.mono, fontSize: 12, bold: true, align: "center", charSpacing: 2, color: HEX.rojo });
  T(s, "miguegarrone-blip.github.io/Web-Mining", { x: 8.85, y: 5.32, w: 4.2, h: 0.32, fontFace: F.mono, fontSize: 13, align: "center" });
  T(s, "Se actualiza cada 30 minutos. Funciona en el celular.", { x: 8.85, y: 5.75, w: 4.2, h: 0.6, fontSize: 14, italic: true, color: HEX.gris, align: "center" });
  s.addNotes("Cierre con la invitación a probarlo en vivo: el QR abre el tablero. Preguntas.");

  const salida = path.join(__dirname, "..", "presentacion-tp.pptx");
  await pres.writeFile({ fileName: salida });
  try { const { applyTheme } = require(APPLY_THEME); await applyTheme(salida, THEME); }
  catch (e) { console.log("sin apply_theme.js: queda la paleta estandar de Office (" + e.message.slice(0, 80) + ")"); }
  console.log("generado", salida);
})();
