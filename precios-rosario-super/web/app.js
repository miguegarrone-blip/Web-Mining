/* Precios Rosario: interfaz de consulta.
 * Datos: data/index.js (índice liviano: una fila por producto; se carga una vez y se busca y filtra acá)
 *        data/d/XX.js (detalle completo, repartido en 256 archivos que se leen solo cuando hacen falta)
 * Usa PriceSearch (search.js). Secciones: utilidades · datos · tarjetas · búsqueda · paleta · catálogo · arranque. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var served = location.protocol.indexOf("http") === 0;

  // ---------- utilidades ----------
  var money = function (n) { return n == null ? "–" : "$" + Math.round(n).toLocaleString("es-AR"); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function debounce(fn, ms) { var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); }; }
  var BADGE = {
    green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300",
    rose: "bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300",
    amber: "bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-200",
    sky: "bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-300",
    slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  };
  function badge(text, tone, title) {
    return '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ' + BADGE[tone] + '"' + (title ? ' title="' + esc(title) + '"' : "") + ">" + esc(text) + "</span>";
  }
  function promoBadge(o) {
    if (!o.promo_label) return "";
    var tone = { nxm: "rose", pct_nth: "rose", bulk: "rose", card: "sky", installments: "sky", pct: "green", offer: "green" }[o.promo_type] || "slate";
    return badge(o.promo_label, tone, o.promo);
  }
  function basisWord(b) { return b === "$/l" ? "litro" : "kg"; }

  // ---------- datos ----------
  var CAT = null, INDEX = null, DETAIL = {};
  var state = { tab: "search", cat: null, chains: null, min: null, max: null, minDisc: 0, onlyAnom: false, sort: "unit", shown: 60 };
  var BASIS = [null, "$/kg", "$/l"];

  /** Convierte una fila del índice en un producto liviano. */
  function toItem(row, categories) {
    return { id: row[0], name: row[1], brand: row[2] || null, size_text: row[3] || null, category: categories[row[4]].name,
      denom: row[5], basis: BASIS[row[6]], prices: row[7], aggressive: !!(row[8] & 1), anomaly: !!(row[8] & 2),
      max_discount: row[9], n_chains: row[10], spread_pct: row[11], stats: { n_chains: row[10] } };
  }
  /** Precios por cadena de un producto liviano (solo cadenas seleccionadas, o todas si ninguna coincide). */
  function lightOffers(item, onlySelected) {
    var all = [], sel = [];
    CAT.chains.forEach(function (c, k) {
      var p = item.prices[k];
      if (!p) return;
      var o = { chain: c.id, chain_label: c.label, price: p, unit_price: item.denom ? Math.round(p / item.denom) : null };
      all.push(o);
      if (state.chains.has(c.id)) sel.push(o);
    });
    var out = onlySelected ? sel : (sel.length ? sel : all);
    return out.sort(function (a, b) { return (a.unit_price == null) - (b.unit_price == null) || (a.unit_price || a.price) - (b.unit_price || b.price); });
  }
  /** Reparto del detalle en 256 archivos: mismo cálculo que catalogo.py (FNV-1a de 32 bits sobre el id). */
  function bucketOf(id) {
    var h = 2166136261;
    for (var i = 0; i < id.length; i++) { h ^= id.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return ("0" + (h % 256).toString(16)).slice(-2);
  }
  var CHAIN_LABEL = {}, shardLoads = {};
  /** Cada archivo data/d/XX.js llama a esta función con los productos de su grupo. */
  window.__shard = function (bucket, group) {
    Object.keys(group).forEach(function (id) {
      var it = group[id];
      it.offers.forEach(function (o) { o.chain_label = CHAIN_LABEL[o.chain] || o.chain; o.basis = it.basis; });
      DETAIL[id] = it;
    });
  };
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src; s.onload = resolve;
      s.onerror = function () { reject(new Error("no se encontró " + src)); };
      document.head.appendChild(s);
    });
  }
  function loadShard(bucket) {
    if (!shardLoads[bucket]) shardLoads[bucket] = loadScript("data/d/" + bucket + ".js").catch(function (e) { delete shardLoads[bucket]; throw e; });
    return shardLoads[bucket];
  }
  /** Detalle completo de varios productos: lee solo los archivos que hagan falta (con caché). Promesa de {id: item}. */
  function fetchDetails(ids) {
    var buckets = {};
    ids.forEach(function (id) { if (!DETAIL[id]) buckets[bucketOf(id)] = 1; });
    return Promise.all(Object.keys(buckets).map(loadShard)).then(function () {
      var out = {};
      ids.forEach(function (id) { if (DETAIL[id]) out[id] = DETAIL[id]; });
      return out;
    });
  }

  // ---------- tarjetas ----------
  function sparkline(item) {
    var h = item.history || [];
    if (h.length < 2) {
      return '<p class="text-xs text-slate-500">Historial: ' + (h.length ? "1 día de datos" : "sin datos") + ". El gráfico aparece cuando hay más corridas diarias.</p>";
    }
    var vals = h.map(function (p) { return p.min; }), lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), span = hi - lo || 1;
    var W = 160, H = 36, pts = vals.map(function (v, i) { return [(i / (vals.length - 1)) * W, H - 4 - ((v - lo) / span) * (H - 8)]; });
    var delta = ((vals[vals.length - 1] - vals[0]) / vals[0]) * 100;
    var tone = delta > 1 ? "text-rose-600" : delta < -1 ? "text-emerald-600" : "text-slate-500";
    return '<div class="flex items-center gap-3"><svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" class="' + tone + '" role="img" aria-label="Evolución del precio mínimo">' +
      '<polyline fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" points="' + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '"/>' +
      '<circle cx="' + pts[pts.length - 1][0].toFixed(1) + '" cy="' + pts[pts.length - 1][1].toFixed(1) + '" r="3" fill="currentColor"/></svg>' +
      '<div class="text-xs"><div class="font-semibold ' + tone + '">' + (delta > 0 ? "+" : "") + delta.toFixed(1) + " %</div><div class=\"text-slate-500\">en " + h.length + " días</div></div></div>";
  }

  /** Tarjeta comparativa multicadena (producto con detalle): todas las cadenas, de menor a mayor precio por kg/litro. */
  function compareCard(item) {
    var s = item.stats;
    var head = '<div class="flex flex-wrap items-start justify-between gap-2"><div class="min-w-0">' +
      '<h3 class="font-semibold leading-snug">' + esc(item.name) + "</h3>" +
      '<p class="mt-0.5 text-xs text-slate-500">' + [item.brand, item.size_text, item.category].filter(Boolean).map(esc).join(" · ") + "</p></div>" +
      '<div class="flex flex-wrap gap-1.5">' +
      (s.aggressive ? badge("Oferta fuerte", "rose") : "") +
      (item.anomaly ? badge(item.anomaly.type === "posible_error" ? "Posible error de precio" : "Muy bajo vs mercado", "amber", item.anomaly.detail) : "") +
      badge(s.n_chains + (s.n_chains === 1 ? " cadena" : " cadenas"), "slate") + "</div></div>";
    var rows = item.offers.map(function (o, i) {
      var isBest = i === 0 && item.offers.length > 1;
      return '<li class="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2 sm:grid-cols-[110px_1fr_auto_auto] ' +
        (isBest ? "bg-emerald-50 ring-1 ring-emerald-300 dark:bg-emerald-950/40 dark:ring-emerald-800" : o.flag ? "bg-amber-50 ring-1 ring-amber-300 dark:bg-amber-950/30 dark:ring-amber-800" : "") + '">' +
        '<div class="flex items-center gap-1.5 text-sm font-medium">' + esc(o.chain_label) + (isBest ? badge("más barata", "green") : "") + "</div>" +
        '<div class="order-3 col-span-2 min-w-0 sm:order-none sm:col-span-1"><a href="' + esc(o.url) + '" target="_blank" rel="noopener" class="block truncate text-xs text-slate-500 hover:underline" title="' + esc(o.title) + '">' + esc(o.title) + "</a>" +
        '<div class="mt-0.5 flex flex-wrap gap-1">' + promoBadge(o) + (o.flag ? badge("revisar precio", "amber") : "") + "</div></div>" +
        '<div class="text-right tabular text-sm"><div class="font-semibold">' + money(o.price) + "</div>" +
        (o.list_price ? '<div class="text-xs text-slate-400 line-through">' + money(o.list_price) + "</div>" : "") + "</div>" +
        '<div class="hidden text-right tabular text-xs text-slate-500 sm:block">' + (o.unit_price ? money(o.unit_price) + "<br>" + o.basis : "") + "</div></li>";
    }).join("");
    var foot = '<div class="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-3 dark:border-slate-800">' + sparkline(item) +
      (s.spread_pct > 0 ? '<p class="text-xs text-slate-500">Entre la más barata y la más cara hay <b class="text-slate-700 dark:text-slate-200">' + s.spread_pct + ' %</b> por ' + basisWord(item.basis) + ".</p>" : "") + "</div>";
    return '<article class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900" data-id="' + esc(item.id) + '">' +
      head + '<ul class="mt-3 space-y-1">' + rows + "</ul>" + foot + "</article>";
  }

  /** Tarjeta compacta para la grilla del catálogo (producto liviano + clave de orden ya calculada). */
  function gridCard(entry) {
    var item = entry.item, o = entry.best, n = entry.n;
    return '<button type="button" data-open="' + esc(item.id) + '" class="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:border-emerald-400 hover:shadow focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600">' +
      '<div class="flex flex-wrap gap-1.5">' + (item.aggressive ? badge("Oferta fuerte", "rose") : "") + (item.anomaly ? badge("Posible error", "amber") : "") + (item.max_discount >= 10 ? badge("-" + item.max_discount + " %", "green") : "") + "</div>" +
      '<h3 class="mt-1.5 line-clamp-2 text-sm font-medium leading-snug">' + esc(item.name) + "</h3>" +
      '<p class="mt-0.5 text-xs text-slate-500">' + [item.size_text, item.category].filter(Boolean).map(esc).join(" · ") + "</p>" +
      '<div class="mt-auto pt-3"><div class="flex items-end justify-between"><div><div class="text-lg font-semibold tabular">' + money(o.price) + '</div><div class="text-xs text-emerald-700 dark:text-emerald-400">' + esc(o.chain_label) + "</div></div>" +
      '<div class="text-right text-xs text-slate-500 tabular">' + (o.unit_price ? money(o.unit_price) + " " + item.basis : "") + "<br>" + n + (n === 1 ? " cadena" : " cadenas") + "</div></div></div></button>";
  }

  // ---------- estados vacíos / error ----------
  function emptyState(q, canLive, unknown) {
    var tips = ["heineken", "yerba mate", "leche", "aceite girasol", "fideos", "gaseosa"];
    return '<div class="rounded-2xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">' +
      '<p class="font-medium">No encontramos "' + esc(q) + '" en el catálogo</p>' +
      (unknown && unknown.length ? '<p class="mt-1 text-sm text-slate-500">En el catálogo diario no hay nada con <b>' + unknown.map(esc).join(", ") + "</b>.</p>" : "") +
      '<p class="mt-1 text-sm text-slate-500">Probá con menos palabras o solo la marca. Por ejemplo:</p>' +
      '<div class="mt-3 flex flex-wrap justify-center gap-2">' + tips.map(function (t) { return '<button type="button" data-suggest="' + esc(t) + '" class="rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">' + esc(t) + "</button>"; }).join("") + "</div>" +
      (canLive ? '<div class="mt-5 border-t border-slate-200 pt-4 dark:border-slate-800"><p class="text-sm text-slate-500">Para cualquier producto que no esté, buscalo en vivo en las ' + CAT.chains.length + ' cadenas (20 a 30 segundos).</p>' +
        '<button type="button" data-live="' + esc(q) + '" class="mt-3 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">Buscar en vivo</button></div>' : '<p class="mt-4 text-sm text-slate-500">Si el producto existe en las tiendas pero no aparece, se suma en la próxima actualización diaria.</p>') + "</div>";
  }
  function errorBox(msg, retryAttr) {
    return '<div class="rounded-2xl border border-rose-300 bg-rose-50 p-5 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200" role="alert"><p class="font-medium">' + esc(msg) + "</p>" +
      (retryAttr ? '<button type="button" ' + retryAttr + ' class="mt-3 rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-700">Reintentar</button>' : "") + "</div>";
  }
  function skeletonCards(n) { var h = ""; for (var i = 0; i < n; i++) h += '<div class="skeleton h-44 w-full"></div>'; return h; }

  // ---------- búsqueda puntual ----------
  var searchSeq = 0;
  function runSearch(q) {
    var out = $("#searchOut");
    q = q.trim();
    var seq = ++searchSeq;
    if (!q) { out.innerHTML = ""; renderChips(); return; }
    var r = PriceSearch.search(INDEX, q, { limit: 12 });
    if (!r.results.length) { out.innerHTML = emptyState(q, served, r.unknown); return; }
    var ids = r.results.map(function (x) { return x.item.id; });
    var notice = r.partial ? '<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">No hay coincidencia exacta. Mostramos productos que coinciden con la mayoría de las palabras.</p>' : "";
    var count = '<p class="text-sm text-slate-500">' + r.results.length + (r.results.length === 12 ? "+ resultados" : r.results.length === 1 ? " resultado" : " resultados") + "</p>";
    if (ids.some(function (id) { return !DETAIL[id]; })) out.innerHTML = notice + count + '<div class="space-y-3">' + skeletonCards(Math.min(3, ids.length)) + "</div>";
    fetchDetails(ids).then(function (det) {
      if (seq !== searchSeq) return;                       // llegó una búsqueda más nueva
      out.innerHTML = notice + count + ids.filter(function (id) { return det[id]; }).map(function (id) { return compareCard(det[id]); }).join("");
    }).catch(function (e) {
      if (seq === searchSeq) out.innerHTML = errorBox("No se pudo cargar el detalle de los productos (" + e.message + ").", 'data-retry="' + esc(q) + '"');
    });
  }
  var runSearchDebounced = debounce(function () { runSearch($("#q").value); }, 180);

  function liveSearch(q) {
    var out = $("#searchOut");
    out.innerHTML = '<p class="text-sm text-slate-500" aria-live="polite">Consultando las ' + CAT.chains.length + ' cadenas… puede tardar 20 a 30 segundos.</p><div class="space-y-3">' + skeletonCards(3) + "</div>";
    fetch("/api/buscar?q=" + encodeURIComponent(q)).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (d) {
      var rows = (d.rows || []).filter(function (row) { return PriceSearch.matchesText(row.title + " " + (row.brand || ""), q); });
      rows.sort(function (a, b) { return (a.unit_price == null) - (b.unit_price == null) || (a.unit_price || a.price) - (b.unit_price || b.price); });
      if (!rows.length) { out.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">Tampoco apareció en vivo. Revisá la ortografía o probá con menos palabras.</div>'; return; }
      var failed = Object.keys(d.errors || {});
      out.innerHTML = (failed.length ? '<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">No respondieron: ' + failed.map(esc).join(", ") + "</p>" : "") +
        '<p class="text-sm text-slate-500">' + rows.length + " productos en vivo, ordenados por precio por kg / litro</p>" +
        '<div class="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"><table class="w-full text-sm"><tbody>' +
        rows.slice(0, 80).map(function (r) {
          return '<tr class="border-b border-slate-100 last:border-0 dark:border-slate-800"><td class="px-3 py-2 font-medium whitespace-nowrap">' + esc(r.chain_label) + '</td><td class="px-3 py-2"><a class="hover:underline" target="_blank" rel="noopener" href="' + esc(r.url) + '">' + esc(r.title) + "</a>" +
            (r.promo ? ' <span class="ml-1">' + badge(r.promo.slice(0, 24), "sky") + "</span>" : "") + '</td><td class="px-3 py-2 text-right tabular font-semibold">' + money(r.price) + '</td><td class="px-3 py-2 text-right tabular text-xs leading-tight text-slate-500">' + (r.unit_price ? money(r.unit_price) + "<br>" + r.basis : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }).catch(function (e) {
      out.innerHTML = errorBox("La búsqueda en vivo necesita el panel abierto (Precios Rosario). Detalle: " + e.message, 'data-live="' + esc(q) + '"');
    });
  }

  function renderChips() {
    var brands = {};
    CAT.items.forEach(function (i) { if (i.brand) brands[i.brand] = (brands[i.brand] || 0) + i.n_chains; });
    var top = Object.keys(brands).sort(function (a, b) { return brands[b] - brands[a]; }).slice(0, 8);
    $("#chips").innerHTML = '<span class="text-sm text-slate-500">Probá:</span>' + top.map(function (b) { return '<button type="button" data-suggest="' + esc(b) + '" class="rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">' + esc(b) + "</button>"; }).join("");
  }

  // ---------- paleta Ctrl/Cmd+K ----------
  var palette = { sel: 0, items: [] };
  function openPalette(prefill) {
    var d = $("#palette");
    if (!d.open) d.showModal();
    $("#pq").value = prefill || "";
    paletteSearch();
    $("#pq").focus();
  }
  function paletteSearch() {
    var q = $("#pq").value.trim();
    var res = q ? PriceSearch.search(INDEX, q, { limit: 8 }) : { results: [] };
    palette.items = res.results.map(function (x) { return x.item; });
    palette.sel = 0;
    var list = $("#pList");
    if (!q) { list.innerHTML = '<li class="px-3 py-6 text-center text-sm text-slate-500">Escribí el nombre, la marca o el tamaño. El orden no importa.</li>'; $("#pHint").textContent = ""; return; }
    if (!palette.items.length) { list.innerHTML = '<li class="px-3 py-6 text-center text-sm text-slate-500">Sin resultados para "' + esc(q) + '". Probá con menos palabras.</li>'; $("#pHint").textContent = ""; return; }
    list.innerHTML = palette.items.map(function (i, k) {
      var best = lightOffers(i)[0];
      return '<li role="option" data-k="' + k + '" class="flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 ' + (k === 0 ? "bg-emerald-50 dark:bg-emerald-950/40" : "") + '">' +
        '<div class="min-w-0"><div class="truncate text-sm font-medium">' + esc(i.name) + '</div><div class="text-xs text-slate-500">' + [i.size_text, i.category, i.n_chains + " cadenas"].filter(Boolean).map(esc).join(" · ") + "</div></div>" +
        '<div class="shrink-0 text-right tabular"><div class="text-sm font-semibold">' + money(best.price) + '</div><div class="text-xs text-emerald-700 dark:text-emerald-400">' + esc(best.chain_label) + "</div></div></li>";
    }).join("");
    $("#pHint").textContent = res.partial ? "Coincidencia parcial" : palette.items.length + " resultados";
  }
  function paletteMove(delta) {
    if (!palette.items.length) return;
    palette.sel = (palette.sel + delta + palette.items.length) % palette.items.length;
    $$("#pList li[data-k]").forEach(function (li) {
      var on = +li.dataset.k === palette.sel;
      li.classList.toggle("bg-emerald-50", on); li.classList.toggle("dark:bg-emerald-950/40", on);
      if (on) li.scrollIntoView({ block: "nearest" });
    });
  }
  function paletteChoose(k) {
    var item = palette.items[k];
    if (!item) return;
    $("#palette").close();
    openDetail(item.id);
  }

  // ---------- detalle ----------
  function openDetail(id) {
    var d = $("#detail");
    $("#detailBody").innerHTML = DETAIL[id] ? compareCard(DETAIL[id]) : '<div class="space-y-3">' + skeletonCards(2) + "</div>";
    if (!d.open) d.showModal();
    if (DETAIL[id]) return;
    fetchDetails([id]).then(function (det) {
      if (!d.open) return;
      $("#detailBody").innerHTML = det[id] ? compareCard(det[id]) : errorBox("No se encontró el detalle de este producto.");
    }).catch(function (e) { $("#detailBody").innerHTML = errorBox("No se pudo cargar el detalle (" + e.message + ").", 'data-open="' + esc(id) + '"'); });
  }

  // ---------- catálogo con filtros ----------
  /** Filtra y ordena con la clave calculada una sola vez por producto (rápido con decenas de miles). */
  function applyFilters() {
    var entries = [];
    for (var n = 0; n < CAT.items.length; n++) {
      var i = CAT.items[n];
      if (state.cat && i.category !== state.cat) continue;
      if (state.minDisc && i.max_discount < state.minDisc) continue;
      if (state.onlyAnom && !i.anomaly) continue;
      var offers = lightOffers(i, true);
      if (!offers.length) continue;
      var minPrice = Infinity;
      for (var k = 0; k < offers.length; k++) if (offers[k].price < minPrice) minPrice = offers[k].price;
      if (state.min != null && minPrice < state.min) continue;
      if (state.max != null && minPrice > state.max) continue;
      var best = offers[0];
      var key = state.sort === "unit" ? (best.unit_price == null ? 1e12 : best.unit_price)
        : state.sort === "price" ? minPrice
        : state.sort === "discount" ? -i.max_discount
        : state.sort === "chains" ? -offers.length
        : i.name.toLowerCase();
      entries.push({ item: i, best: best, n: offers.length, key: key });
    }
    entries.sort(function (a, b) { return a.key < b.key ? -1 : a.key > b.key ? 1 : 0; });
    return entries;
  }
  function renderCatalog() {
    var list = applyFilters();
    $("#catCount").textContent = list.length.toLocaleString("es-AR") + " productos" + (state.cat ? " en " + state.cat : "");
    var grid = $("#grid");
    if (!list.length) {
      grid.innerHTML = '<div class="col-span-full rounded-2xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><p class="font-medium">Ningún producto cumple esos filtros</p><p class="mt-1 text-sm text-slate-500">Probá bajando el descuento mínimo, ampliando el precio o sumando supermercados.</p><button type="button" data-reset class="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">Limpiar filtros</button></div>';
      $("#more").classList.add("hidden");
      return;
    }
    grid.innerHTML = list.slice(0, state.shown).map(gridCard).join("");
    $("#more").classList.toggle("hidden", list.length <= state.shown);
    $("#more").textContent = "Ver más productos (" + (list.length - state.shown).toLocaleString("es-AR") + " restantes)";
  }
  function renderCats() {
    var total = CAT.items.length;
    var rows = [{ name: null, count: total }].concat(CAT.categories);
    $("#cats").innerHTML = rows.map(function (c) {
      var on = state.cat === c.name;
      return '<button type="button" data-cat="' + esc(c.name || "") + '" class="flex items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-sm ' + (on ? "bg-emerald-100 font-semibold text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200" : "hover:bg-slate-100 dark:hover:bg-slate-800") + '"><span>' + esc(c.name || "Todas") + '</span><span class="text-xs text-slate-500">' + c.count.toLocaleString("es-AR") + "</span></button>";
    }).join("");
  }
  function renderChainFilter() {
    $("#chainFilter").innerHTML = CAT.chains.map(function (c) {
      return '<label class="flex items-center gap-1.5"><input type="checkbox" data-chain="' + esc(c.id) + '" class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"' + (state.chains.has(c.id) ? " checked" : "") + "> " + esc(c.label) + "</label>";
    }).join("");
  }
  function resetFilters() {
    state.cat = null; state.chains = new Set(CAT.chains.map(function (c) { return c.id; })); state.min = state.max = null; state.minDisc = 0; state.onlyAnom = false; state.shown = 60;
    $("#pMin").value = ""; $("#pMax").value = ""; $("#minDisc").value = "0"; $("#onlyAnom").checked = false;
    renderCats(); renderChainFilter(); renderCatalog();
  }

  // ---------- pestañas ----------
  function setTab(tab) {
    state.tab = tab;
    $("#viewSearch").hidden = tab !== "search"; $("#viewCatalog").hidden = tab !== "catalog";
    $$(".tab").forEach(function (b) {
      var on = b.dataset.tab === tab;
      b.className = "tab rounded-lg px-3 py-1.5 text-sm font-medium " + (on ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800");
    });
    if (tab === "catalog") renderCatalog(); else $("#q").focus();
  }

  // ---------- arranque ----------
  function init(data) {
    var items = new Array(data.rows.length);
    for (var n = 0; n < data.rows.length; n++) items[n] = toItem(data.rows[n], data.categories);
    CAT = { generated_at: data.generated_at, chains: data.chains, categories: data.categories, items: items };
    data.chains.forEach(function (c) { CHAIN_LABEL[c.id] = c.label; });
    INDEX = PriceSearch.createIndex(items);
    state.chains = new Set(CAT.chains.map(function (c) { return c.id; }));
    var when = new Date(CAT.generated_at);
    $("#updated").textContent = items.length.toLocaleString("es-AR") + " productos · " + CAT.chains.length + " supermercados · actualizado el " +
      when.toLocaleDateString("es-AR", { day: "numeric", month: "long" }) + ", " + when.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
    var ageDays = (Date.now() - when.getTime()) / 86400000;          // aviso si los datos quedaron viejos
    if (ageDays > 1.5) {
      $("#updated").insertAdjacentHTML("beforeend", ' <span class="font-medium text-amber-700 dark:text-amber-400">· Datos de hace ' + Math.floor(ageDays) +
        ' días. Para actualizar: doble clic en “Actualizar precios.bat”.</span>');
    }
    $("#loading").classList.add("hidden");
    $("#fatal").classList.add("hidden");
    $("#canastaLink").hidden = !served;                    // "Mi canasta" y la búsqueda en vivo necesitan el panel
    if (window.innerWidth < 1024) $("#filtersBox").open = false;
    $("#kbdHint").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ K" : "Ctrl K";
    renderChips(); renderCats(); renderChainFilter(); setTab("search");
    var initial = new URLSearchParams(location.search).get("q");
    if (initial) { $("#q").value = initial; runSearch(initial); }
  }

  function load() {
    $("#loading").classList.remove("hidden"); $("#fatal").classList.add("hidden");
    var ready = window.CATALOGO_INDEX ? Promise.resolve() : loadScript("data/index.js");
    ready.then(function () { init(window.CATALOGO_INDEX); }).catch(function (e) {
      $("#loading").classList.add("hidden");
      var f = $("#fatal"); f.classList.remove("hidden");
      f.innerHTML = errorBox("No se pudo cargar el catálogo (" + e.message + "). Se genera con la actualización diaria o con: python catalogo.py", "data-reload");
    });
  }

  // ---------- eventos ----------
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-tab],[data-suggest],[data-live],[data-open],[data-cat],[data-reset],[data-reload],[data-retry],#more,#openPalette,#resetFilters,#detailClose");
    if (!t) return;
    if (t.dataset.tab) setTab(t.dataset.tab);
    else if (t.dataset.suggest != null) { setTab("search"); $("#q").value = t.dataset.suggest; runSearch(t.dataset.suggest); }
    else if (t.dataset.live != null) liveSearch(t.dataset.live);
    else if (t.dataset.retry != null) runSearch(t.dataset.retry);
    else if (t.dataset.open) openDetail(t.dataset.open);
    else if (t.dataset.cat != null) { state.cat = t.dataset.cat || null; state.shown = 60; renderCats(); renderCatalog(); }
    else if (t.hasAttribute("data-reset") || t.id === "resetFilters") resetFilters();
    else if (t.hasAttribute("data-reload")) load();
    else if (t.id === "more") { state.shown += 60; renderCatalog(); }
    else if (t.id === "openPalette") openPalette($("#q").value);
    else if (t.id === "detailClose") $("#detail").close();
  });
  $("#q").addEventListener("input", runSearchDebounced);
  $("#q").addEventListener("keydown", function (e) { if (e.key === "Enter") runSearch(e.target.value); });
  $("#pq").addEventListener("input", debounce(paletteSearch, 120));
  $("#pq").addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); paletteMove(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); paletteMove(-1); }
    else if (e.key === "Enter") { e.preventDefault(); paletteChoose(palette.sel); }
  });
  $("#pList").addEventListener("click", function (e) { var li = e.target.closest("li[data-k]"); if (li) paletteChoose(+li.dataset.k); });
  ["palette", "detail"].forEach(function (id) {   // clic en el fondo cierra
    $("#" + id).addEventListener("click", function (e) { if (e.target === e.currentTarget) e.currentTarget.close(); });
  });
  document.addEventListener("keydown", function (e) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (CAT) openPalette(""); }
    else if (e.key === "/" && !typing && CAT) { e.preventDefault(); openPalette(""); }
  });
  $("#chainFilter").addEventListener("change", function (e) {
    var id = e.target.dataset.chain; if (!id) return;
    if (e.target.checked) state.chains.add(id); else state.chains.delete(id);
    if (!state.chains.size) { state.chains.add(id); e.target.checked = true; }     // al menos una
    state.shown = 60; renderCatalog();
  });
  var numberOrNull = function (v) { return v === "" ? null : Number(v); };
  $("#pMin").addEventListener("input", debounce(function (e) { state.min = numberOrNull(e.target.value); state.shown = 60; renderCatalog(); }, 250));
  $("#pMax").addEventListener("input", debounce(function (e) { state.max = numberOrNull(e.target.value); state.shown = 60; renderCatalog(); }, 250));
  $("#minDisc").addEventListener("change", function (e) { state.minDisc = Number(e.target.value); state.shown = 60; renderCatalog(); });
  $("#onlyAnom").addEventListener("change", function (e) { state.onlyAnom = e.target.checked; state.shown = 60; renderCatalog(); });
  $("#sort").addEventListener("change", function (e) { state.sort = e.target.value; renderCatalog(); });

  load();
})();
