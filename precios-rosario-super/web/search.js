/*!
 * PriceSearch: buscador tolerante para el catálogo de precios. Sin dependencias.
 *
 * Qué resuelve
 *   "473 heineken lata" encuentra "Cerveza Heineken Lata 473cc" (y al revés): el orden de las
 *   palabras no importa, se ignoran tildes y mayúsculas, "473", "473cc" y "473ml" son equivalentes,
 *   "1 kg" equivale a "1000 g", y se toleran errores de tipeo leves ("cervesa", "heneiken").
 *
 * Cómo funciona (4 pasos)
 *   1. normalize(): minúsculas, sin tildes, solo letras y números ("473cc" pasa a "473 cc").
 *   2. tokenize(): separa en palabras. Cada palabra es un "token" con alternativas:
 *        - números con unidad generan alias de escala: "1 kg" -> {1, 1000}; "2,25 l" -> {2.25, 2250}
 *        - las unidades sueltas (cc, ml, lt, g, kg, un...) son opcionales: suman puntos si coinciden
 *          pero no hacen falta para que el producto aparezca
 *        - plurales simples: "cervezas" -> "cerveza"
 *   3. createIndex(): arma una sola vez, por producto, el conjunto de tokens de su nombre, marca,
 *      tamaño, categoría y los nombres que usa cada cadena. Buscar después es barato.
 *   4. search(): cada token de la consulta busca su mejor coincidencia en el producto:
 *        exacta (1.0) > prefijo (0.9, sirve para autocompletar mientras se escribe) > difusa (0.7,
 *        distancia de Damerau-Levenshtein <= 1 en palabras de 4-7 letras, <= 2 desde 8 letras).
 *      Los números exigen coincidencia exacta (473 no es 474). Se pide que coincidan TODOS los
 *      tokens; si no hay ningún producto así, se aceptan los que coinciden con al menos dos tercios
 *      (marcados partial:true) para no devolver una pantalla vacía. Excepción: si una palabra no
 *      existe en ningún producto del catálogo (devuelta en `unknown`), no hay resultados: el producto
 *      no está, y rellenar con otros que coinciden en el resto confunde.
 *
 * Uso
 *   const index = PriceSearch.createIndex(catalogo.items);
 *   const { results, partial } = PriceSearch.search(index, "473 heineken lata", { limit: 20 });
 *   // results: [{ item, score, matched, total }], ordenados de mejor a peor
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PriceSearch = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---- 1. Normalización ------------------------------------------------------------------------
  function normalize(text) {
    return String(text == null ? "" : text)
      .normalize("NFD").replace(/[̀-ͯ]/g, "")   // tildes
      .toLowerCase()
      .replace(/(\d)\s*[.,]\s*(\d)/g, "$1.$2")             // 2,25 -> 2.25
      .replace(/(\d)([a-z])/g, "$1 $2")                    // 473cc -> 473 cc
      .replace(/([a-z])(\d)/g, "$1 $2")
      .replace(/[^a-z0-9.\s]/g, " ")
      .replace(/\.(?!\d)|(?<!\d)\./g, " ")                 // puntos que no son decimales
      .replace(/\s+/g, " ")
      .trim();
  }

  // ---- 2. Tokenización -------------------------------------------------------------------------
  var UNIT_SCALE = {                // unidad -> factor para llevar a g / ml
    kg: 1000, kgs: 1000, kilo: 1000, kilos: 1000,
    l: 1000, lt: 1000, lts: 1000, litro: 1000, litros: 1000,
    g: 1, gr: 1, grs: 1, gm: 1, gms: 1, gramos: 1,
    cc: 1, ml: 1,
  };
  var OPTIONAL_WORDS = {            // sin valor para distinguir productos: opcionales
    x: 1, un: 1, u: 1, uni: 1, unid: 1, unidad: 1, unidades: 1, de: 1, del: 1, la: 1, el: 1, los: 1, las: 1,
    con: 1, y: 1, en: 1, por: 1, cada: 1, c: 1,
  };

  function singular(w) {
    return w.length > 4 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w;
  }

  function isNumber(w) { return /^\d+(\.\d+)?$/.test(w); }

  function fmt(n) { return String(Math.round(n * 1000) / 1000); }

  /**
   * Convierte texto en tokens. Devuelve [{ alts: [..], unit: bool, optional: bool, num: bool }].
   * alts son las formas aceptadas (ej. "1 kg" -> ["1", "1000"]).
   */
  function tokenize(text) {
    var words = normalize(text).split(" ").filter(Boolean);
    var out = [];
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (isNumber(w)) {
        var next = words[i + 1];
        var alts = [fmt(Number(w))];
        if (next && UNIT_SCALE[next] !== undefined) {
          if (UNIT_SCALE[next] !== 1) alts.push(fmt(Number(w) * UNIT_SCALE[next]));
        }
        out.push({ alts: alts, num: true, unit: false, optional: false });
      } else if (UNIT_SCALE[w] !== undefined) {
        out.push({ alts: [w], num: false, unit: true, optional: true });
      } else if (OPTIONAL_WORDS[w]) {
        out.push({ alts: [w], num: false, unit: false, optional: true });
      } else {
        out.push({ alts: [singular(w)], num: false, unit: false, optional: false });
      }
    }
    return out;
  }

  // ---- 3. Distancia de edición (Damerau-Levenshtein con tope) ---------------------------------
  function editDistance(a, b, max) {
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return max + 1;
    var prev2 = null, prev = new Array(lb + 1), cur = new Array(lb + 1), i, j;
    for (j = 0; j <= lb; j++) prev[j] = j;
    for (i = 1; i <= la; i++) {
      cur[0] = i;
      var rowMin = cur[0];
      for (j = 1; j <= lb; j++) {
        var cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        var v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
        if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, prev2[j - 2] + 1);
        cur[j] = v;
        if (v < rowMin) rowMin = v;
      }
      if (rowMin > max) return max + 1;
      prev2 = prev; prev = cur; cur = new Array(lb + 1);
    }
    return prev[lb];
  }

  function fuzzyLimit(len) { return len >= 8 ? 2 : len >= 4 ? 1 : 0; }

  // ---- 4. Índice y búsqueda --------------------------------------------------------------------
  function docTokens(item) {
    var offers = (item.offers || []).map(function (o) { return o.title; });
    var text = [item.name, item.brand, item.size_text, item.category].concat(offers).join(" ");
    var set = Object.create(null), list = [];
    tokenize(text).forEach(function (t) {
      t.alts.forEach(function (a) { if (!set[a]) { set[a] = 1; list.push(a); } });
    });
    return { set: set, list: list };
  }

  function createIndex(items) {
    // Índice invertido: palabra -> ids de producto. words (ordenadas) permite buscar prefijos con búsqueda
    // binaria y byLen agrupa las palabras por largo para comparar difuso solo contra largos parecidos.
    var vocab = Object.create(null);
    for (var id = 0; id < items.length; id++) {
      var list = docTokens(items[id]).list;
      for (var j = 0; j < list.length; j++) {
        var w = list[j];
        (vocab[w] || (vocab[w] = [])).push(id);
      }
    }
    var words = Object.keys(vocab).filter(function (w) { return !isNumber(w); }).sort();
    var byLen = Object.create(null);
    words.forEach(function (w) { (byLen[w.length] || (byLen[w.length] = [])).push(w); });
    return { items: items, vocab: vocab, words: words, byLen: byLen };
  }

  function lowerBound(words, prefix) {
    var lo = 0, hi = words.length;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (words[mid] < prefix) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  /** Productos que coinciden con un token de la consulta: Map(id -> mejor puntaje 1 / 0.9 / 0.7). */
  function tokenMatches(tok, isLast, index) {
    var out = new Map();
    function add(docs, score) {
      for (var i = 0; i < docs.length; i++) {
        var d = docs[i];
        if ((out.get(d) || 0) < score) out.set(d, score);
      }
    }
    for (var a = 0; a < tok.alts.length; a++) {
      var q = tok.alts[a];
      if (index.vocab[q]) add(index.vocab[q], 1);
      if (tok.num) continue;                                           // los números no son difusos
      if (isLast && q.length >= 2) {                                   // prefijo (autocompletado)
        var i = lowerBound(index.words, q), seen = 0;
        while (i < index.words.length && index.words[i].indexOf(q) === 0 && seen < 300) {
          if (index.words[i] !== q) add(index.vocab[index.words[i]], 0.9);
          i++; seen++;
        }
      }
      var lim = fuzzyLimit(q.length);
      if (lim) {
        for (var L = q.length - lim; L <= q.length + lim; L++) {
          var group = index.byLen[L];
          if (!group) continue;
          for (var g = 0; g < group.length; g++) {
            var w = group[g];
            if (w !== q && editDistance(q, w, lim) <= lim) add(index.vocab[w], 0.7);
          }
        }
      }
    }
    return out;
  }

  function chainsOf(item) { return item.stats ? item.stats.n_chains : (item.n_chains || 0); }

  function search(index, query, options) {
    options = options || {};
    var limit = options.limit || 50;
    var minShare = options.minShare || 2 / 3;      // al menos dos tercios de las palabras
    var tokens = tokenize(query);
    var required = tokens.filter(function (t) { return !t.optional; });
    var optional = tokens.filter(function (t) { return t.optional && t.unit; });
    if (!required.length) return { results: [], partial: false, tokens: tokens };

    var lastRequired = required[required.length - 1];
    var maps = required.map(function (t) { return tokenMatches(t, t === lastRequired, index); });
    // Una palabra (no numérica) que no existe en ningún producto significa que ese producto no está en el
    // catálogo: no se rellena con otros que coinciden solo en el resto ("473 heineken lata" sin Heineken).
    var unknown = required.filter(function (t, k) { return !t.num && maps[k].size === 0; }).map(function (t) { return t.alts[0]; });
    if (unknown.length) return { results: [], partial: false, tokens: tokens, unknown: unknown };

    var total = required.length, candidates = [], partial = false;
    var seed = 0;                                   // se parte del token más selectivo (menos productos)
    maps.forEach(function (m, k) { if (m.size < maps[seed].size) seed = k; });
    maps[seed].forEach(function (_s, id) {
      var sum = 0, ok = true;
      for (var k = 0; k < total; k++) {
        var s = maps[k].get(id);
        if (!s) { ok = false; break; }
        sum += s;
      }
      if (ok) candidates.push({ id: id, sum: sum, matched: total });
    });
    if (!candidates.length && total >= 2) {          // ninguno con todas: se aceptan los de dos tercios
      var need = Math.max(1, Math.ceil(total * minShare - 1e-9)), acc = new Map();
      maps.forEach(function (m) {
        m.forEach(function (s, id) {
          var cur = acc.get(id) || { id: id, sum: 0, matched: 0 };
          cur.sum += s; cur.matched++; acc.set(id, cur);
        });
      });
      acc.forEach(function (c) { if (c.matched >= need) candidates.push(c); });
      partial = candidates.length > 0;
    }
    function byScore(a, b) { return b.score - a.score || chainsOf(b.item) - chainsOf(a.item); }
    var top = candidates.map(function (c) {
      return { item: index.items[c.id], score: c.sum / total, matched: c.matched, total: total };
    }).sort(byScore).slice(0, 300);
    top.forEach(function (r) {                       // bonos: unidad coincidente y todas las palabras en el nombre
      var set = docTokens(r.item).set, bonus = 0;
      optional.forEach(function (t) { if (set[t.alts[0]]) bonus += 0.05; });
      var nameTokens = tokenize(r.item.name).map(function (t) { return t.alts[0]; });
      if (required.every(function (t) { return t.alts.some(function (a) { return nameTokens.indexOf(a) >= 0; }); })) bonus += 0.1;
      r.score += bonus;
    });
    return { results: top.sort(byScore).slice(0, limit), partial: partial, tokens: tokens };
  }

  /** ¿Una cadena de texto cumple la consulta? (para filtrar tablas que no usan índice) */
  function matchesText(text, query) {
    var idx = createIndex([{ name: text }]);
    var r = search(idx, query, { limit: 1 });
    return r.results.length > 0 && !r.partial;
  }

  return { normalize: normalize, tokenize: tokenize, createIndex: createIndex, search: search,
           matchesText: matchesText, editDistance: editDistance };
});
