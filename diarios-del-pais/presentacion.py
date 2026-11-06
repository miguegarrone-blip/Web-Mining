"""Presentacion "La Tapa": llena tpl_presentacion.html con los mismos datos del tablero y escribe presentacion.html.

Se llama al final de build.py. Para que la pagina pese poco (< 1,5 MB) no se pasa D completo: cada nota de la ventana
va como una lista corta [medio, titulo, minuto, tono, tono manual, rasgos de cebo, temas, entidades] (sin URL, bajada
ni vecinos), y de AGG solo lo que usan las diapositivas. Los grupos de historias compartidas se calculan en el
navegador con el mismo codigo del tablero (TF-IDF + coseno)."""
import json, os

# Comparacion de los 8 modelos de tono sobre los 340 titulares representativos (validacion cruzada de 5 pliegues):
# la misma tabla del informe y de la presentacion en PowerPoint. tono_comparacion.json hoy guarda las filas 1-8
# evaluadas sobre el conjunto ampliado con los 60 casos activos (400), que no son representativos, por eso no se usan aca.
MODELOS = [["Palabras + XLM-RoBERTa", 76.8], ["Palabras + ambos BERT", 75.3], ["Palabras + pysentimiento", 75.0],
           ["XLM-RoBERTa solo", 74.1], ["Embeddings + reg. logística", 72.4], ["Solo probas BERT", 72.4],
           ["Modelo inicial (palabras)", 70.3], ["pysentimiento solo", 64.4]]


def _ejemplo_parecidas(pag):
    """par de notas de distintos medios con sentido parecido pero pocas palabras en comun (embeddings)"""
    pal = lambda t: {w for w in t.lower().split() if len(w) > 3}
    mejor = None
    for x in pag:
        sim = x.get("sim") or []
        for k in range(0, len(sim), 2):
            j, s = sim[k], sim[k + 1]
            if j >= len(pag) or not 72 <= s <= 92: continue
            y = pag[j]
            a, b = pal(x["t"]), pal(y["t"])
            jac = len(a & b) / max(1, len(a | b))
            if jac > 0.3: continue
            puntaje = s - 40 * jac
            if not mejor or puntaje > mejor[0]: mejor = (puntaje, [x["m"], x["t"]], [y["m"], y["t"]], s)
    return {"a": mejor[1], "b": mejor[2], "s": mejor[3]} if mejor else None


def generar(DB, F, pag, AGG, HEALTH, CAL, tpl_path, out_path, now):
    meds = sorted({x["m"] for x in pag})
    im = {m: i for i, m in enumerate(meds)}
    temas = sorted({t for x in pag for t in x["tg"]})
    it = {t: i for i, t in enumerate(temas)}
    ents = sorted({e for x in pag for e in x.get("e", [])})
    ie = {e: i for i, e in enumerate(ents)}
    rasgos = ["pregunta", "exclamación", "adjetivo exagerado", "intriga", "segunda persona", "lista"]
    ir = {r: i for i, r in enumerate(rasgos)}
    D = [[im[x["m"]], x["t"], int(x["ts"] // 60000), x["sa"], x.get("s", ""), [ir[r] for r in x.get("cr", []) if r in ir],
          [it[t] for t in x["tg"]], [ie[e] for e in x.get("e", [])]] for x in pag]

    # fuentes: medios con RSS propio (al menos un feed del medio) y medios solo por Google News
    rss = [m for m, (_, _, us) in F.items() if any(not u.startswith("gn:") for u in us)]
    gn = [m for m in F if m not in rss]
    n_gn = DB.execute("SELECT COUNT(*) FROM items WHERE medio IN (%s)" % ",".join("?" * len(gn)), gn).fetchone()[0] if gn else 0
    scr = DB.execute("SELECT SUM(intentos), SUM(ok), SUM(bajada), SUM(ld), SUM(robots) FROM scraping").fetchone()
    tono = dict(DB.execute("SELECT COALESCE(NULLIF(tono_manual,''),tono_auto), COUNT(*) FROM items GROUP BY 1").fetchall())

    med = {}
    for m, v in (AGG.get("med") or {}).items():
        p = v["p"]
        med[m] = {"r": v["r"], "tp": v["tp"], "p": {"1": {"n": p[1]["n"], "t": p[1]["t"]}, "7": {"n": p[7]["n"], "t": p[7]["t"], "en": p[7]["en"]},
                                                     "30": {"n": p[30]["n"], "t": p[30]["t"]}}}
    ner = AGG.get("ner") or {}
    figs = [f for f in ner.get("fig", []) if not f["dic"] and f["n24"] > 0]
    figs = sorted(figs, key=lambda f: (-(f["nueva"] and not f["dep"]), -f["n24"]))[:6]
    horas = dict(sorted(AGG["horas"].items())[-30:])

    P = {
        "now": now, "run": HEALTH["run"], "total_db": HEALTH["total_db"], "corridas": HEALTH["corridas"],
        "medios": meds, "temas": temas, "ents": ents, "rasgos": rasgos, "D": D,
        "agg": {"dn": AGG["dn"], "dneg": AGG["dneg"], "hoy": AGG["hoy"], "tema": AGG["tema"], "horas": horas, "med": med,
                "sens": AGG.get("sens", []), "aut": AGG.get("aut", [])[:5], "ej_al": [r[:3] for r in AGG.get("ej_al", [])[:6]],
                "ej_cb": [r[:3] for r in AGG.get("ej_cb", [])[:8]], "scr": AGG.get("scr", []), "prog": AGG.get("prog"),
                "dolar": AGG.get("dolar", {}), "ner": {"fig": [{k: f[k] for k in ("n", "n24", "m24", "nueva", "dep", "ej")} for f in figs], "hist": ner.get("hist", 0)}},
        "cal": CAL["cal"] if CAL else None, "acuerdo": CAL["acierto_cv"] if CAL else None,
        "fuentes": {"rss": rss, "gn": gn, "n_gn": n_gn, "n_medios": len(F)},
        "scraping": {"intentos": scr[0] or 0, "ok": scr[1] or 0, "bajada": scr[2] or 0, "ld": scr[3] or 0, "robots": scr[4] or 0},
        "tono": tono, "modelos": MODELOS,
        "parecidas": _ejemplo_parecidas(pag),
    }
    js = json.dumps(P, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = open(tpl_path, encoding="utf-8").read().replace("__PRES__", js).replace("__NOW__", now)
    open(out_path, "w", encoding="utf-8").write(html)
    return len(html.encode("utf-8"))
