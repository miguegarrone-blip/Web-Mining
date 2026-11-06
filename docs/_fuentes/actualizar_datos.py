"""Regenera docs/_fuentes/datos.json con cifras frescas para la presentacion "La Tapa".

Uso (antes de la clase), desde docs/_fuentes:
    python actualizar_datos.py              # baja las bases publicadas y escribe datos.json
    python actualizar_datos.py --local DIR  # usa explorar.db e historico.db ya bajadas en DIR

Fuentes (GitHub Pages del proyecto):
  - explorar.db  : ultimos 7 dias, tabla `notas` (titulares reales, horas, tono, cebo, bajada)
  - historico.db : base completa, tabla `items` (rankings, totales, tono por dia), `scraping`, `salud`, `dolar`
Despues: node presentacion.js (ver docs/README.md).
"""
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta

BASE_URL = "https://miguegarrone-blip.github.io/Web-Mining/"
AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
TONO = "COALESCE(NULLIF(tono_manual,''),tono_auto)"

# Comparacion de los 8 modelos de tono (340 titulares etiquetados a mano, validacion cruzada de 5 pliegues).
# Es una evaluacion fija del informe, no cambia con los datos: queda aca para que la presentacion la tome de datos.json.
MODELOS_TONO = [["Palabras + XLM-RoBERTa", 76.8], ["Palabras + ambos BERT", 75.3], ["Palabras + pysentimiento", 75.0],
                ["XLM-RoBERTa solo", 74.1], ["Embeddings + reg. logística", 72.4], ["Solo probas BERT", 72.4],
                ["Modelo inicial (palabras)", 70.3], ["pysentimiento solo", 64.4]]


# ---------- texto: mismas reglas que el tablero (diarios-del-pais/nlp.py y tpl2.html) ----------
def norm(t):
    return unicodedata.normalize("NFD", t.lower()).encode("ascii", "ignore").decode()


def norm_con_mapa(t):
    """norm() caracter por caracter, con el indice original de cada caracter normalizado (para ubicar las marcas)."""
    out, idx = [], []
    for i, ch in enumerate(t):
        for c in norm(ch):
            out.append(c)
            idx.append(i)
    return "".join(out), idx


CEBO = {
    "pregunta": re.compile(r"[?¿]"),
    "exclamacion": re.compile(r"[!¡]"),
    "exagera": re.compile(r"\b(?:impactante|insolito|increible|bomba|escandalo|escandaloso|furia|brutal|picante|tremend[oa]|terrible|dramatic[oa]|polemic[oa]|explosiv[oa]|estallo|exploto|durisim[oa]|lapidari[oa]|contundente|sin filtro|filtr(?:o|aron)|destapo|desopilante|letal|alarmante|shock|viral|furor|bochorn\w*|escandal\w*|bombazo|inesperad[oa]|sorpresiv[oa])\b"),
    "intriga": re.compile(r"(?:^|[\s:.,\"“])(?:lo que|la razon|el motivo|el truco|el secreto|la verdad|nadie|esto es|asi (?:es|fue|quedo|son|luce)|que es|por que|quien es|quienes son|cual es|cuales son|como (?:es|hacer|saber|evitar)|el dato|la clave|lo que (?:hay|tenes|nadie))\b"),
    "segunda_persona": re.compile(r"\b(?:tenes|podes|debes|sabias|mira|descubri|enterate|conoce|evita|hace esto|tu|vos)\b"),
    "lista": re.compile(r"^(?:las?|los)?\s*\d{1,2}\s+(?:claves|cosas|razones|consejos|trucos|errores|alimentos|senales|pasos|formas|motivos|datos|lugares|frases|preguntas|beneficios|habitos)\b"),
}
NOMBRE_CEBO = {"pregunta": "pregunta", "exclamacion": "exclamación", "exagera": "adjetivo exagerado", "intriga": "intriga",
               "segunda_persona": "segunda persona", "lista": "lista"}


def marcas_cebo(titulo):
    """rasgos de cebo y los tramos [ini, fin) del titulo original donde aparecen (para la marca de birome roja)."""
    n, idx = norm_con_mapa(titulo)
    rasgos, tramos = [], []
    for k, rx in CEBO.items():
        if k in ("pregunta", "exclamacion"):
            ms = list(rx.finditer(titulo))
            if ms:
                rasgos.append(NOMBRE_CEBO[k])
                # se marca toda la frase entre signos (¿...? o ¡...!) si esta completa; si no, el signo solo
                abre, cierra = ("¿", "?") if k == "pregunta" else ("¡", "!")
                a, b = titulo.find(abre), titulo.find(cierra)
                if 0 <= a < b and b - a <= 60:
                    tramos.append([a, b + 1, k])
                else:
                    tramos.append([ms[-1].start(), ms[-1].end(), k])
            continue
        m = rx.search(n)
        if m:
            rasgos.append(NOMBRE_CEBO[k])
            ini, fin = m.start(), m.end()
            while ini < fin and not n[ini].isalnum():
                ini += 1
            tramos.append([idx[ini], idx[fin - 1] + 1, k])
    return rasgos, tramos


def sin_superponer(tramos):
    """deja las marcas que no se pisan, priorizando las palabras (adjetivo, intriga) sobre los signos."""
    orden = {"exagera": 0, "lista": 1, "intriga": 2, "segunda_persona": 3, "exclamacion": 4, "pregunta": 5}
    out = []
    for a, b, k in sorted(tramos, key=lambda x: orden[x[2]]):
        if all(b <= a2 or a >= b2 for a2, b2, _ in out):
            out.append([a, b, k])
    return sorted(out)


SW2 = set(("contra pero video videos quedo asi aca alla hasta tambien sigue siguen de la el en y a los las un una por con para que del al se su sus es lo como mas sobre tras ante este esta ya no si le les o u e entre hasta desde sin que como cuando dias dia ano anos sera ser fue hoy vs hace va ha han fin semana nueva nuevo primer primera dos tres cinco uno rosario argentina javier torneo clausura horario posibles formaciones canal vivo tambien cada todo todos esta este estos esas ese eso lunes martes miercoles jueves viernes sabado domingo enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre 2025 2026 ahora minuto ultimas noticias ultima ultimo hora horas tras segun ademas puede pueden podria hacer hizo luego antes despues mientras donde quien quienes cual cuales porque").split())


def agrupar(notas):
    """Agrupa notas que cuentan lo mismo como el tablero: TF-IDF + coseno >= 0,5 contra la semilla del grupo (sin encadenar).
    notas: lista de dicts con 't' (titulo) y 'ts' (orden). Devuelve listas de indices."""
    T = [set(w for w in re.sub(r"[^a-z0-9 ]", " ", norm(x["t"])).split() if len(w) > 3 and w not in SW2) for x in notas]
    df = Counter(w for st in T for w in st)
    N = len(notas)
    V = []
    for st in T:
        v = {w: math.log(1 + N / df[w]) for w in st}
        V.append((v, math.sqrt(sum(x * x for x in v.values())) or 1))

    def cos(a, b):
        (va, na), (vb, nb) = a, b
        if len(va) > len(vb):
            va, vb = vb, va
        d = c = 0
        for w, x in va.items():
            y = vb.get(w)
            if y:
                d += x * y
                c += 1
        return d / (na * nb) if c >= 2 else 0

    grupos, post = [], defaultdict(list)
    for i in sorted(range(N), key=lambda i: notas[i]["ts"], reverse=True):   # de la mas nueva a la mas vieja
        cand = {k for w in T[i] for k in post[w]}
        best, bs = -1, 0.5
        for k in cand:
            c = cos(V[i], V[grupos[k][0]])
            if c > bs:
                bs, best = c, k
        if best >= 0:
            grupos[best].append(i)
        else:
            grupos.append([i])
            for w in T[i]:
                post[w].append(len(grupos) - 1)
    return grupos


# ---------- bajada de las bases ----------
def bajar(nombre, destino):
    ruta = os.path.join(destino, nombre)
    print("bajando", BASE_URL + nombre, "...", flush=True)
    req = urllib.request.Request(BASE_URL + nombre, headers={"User-Agent": "monitor-de-medios/1.0 (presentacion del TP)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(ruta, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return ruta


def medios_por_via():
    """lee la configuracion de feeds de build.py: medios con RSS propio y medios que solo llegan por Google News."""
    txt = open(os.path.join(REPO, "diarios-del-pais", "build.py"), encoding="utf-8").read()
    rss, gn = [], []
    for m, feeds in re.findall(r'^"([^"]+)":\("[^"]*","[^"]*",\[(.*?)\]\)', txt, re.M):
        (gn if all(f.strip().strip('"').startswith("gn:") for f in feeds.split(",")) else rss).append(m)
    return rss, gn


def hhmm(publicado):
    return publicado[11:16] if publicado else ""


def main():
    args = sys.argv[1:]
    if "--local" in args:
        carpeta = args[args.index("--local") + 1]
        exp, his = os.path.join(carpeta, "explorar.db"), os.path.join(carpeta, "historico.db")
    else:
        carpeta = tempfile.mkdtemp(prefix="latapa_")
        exp, his = bajar("explorar.db", carpeta), bajar("historico.db", carpeta)
    E, H = sqlite3.connect(exp), sqlite3.connect(his)
    D = {"generado": datetime.now().strftime("%Y-%m-%d %H:%M")}

    # ---- totales (base completa) ----
    rss, gn = medios_por_via()
    tot = H.execute(f"""SELECT COUNT(*), COUNT(DISTINCT medio), SUM(ld IS NOT NULL OR enr>=2),
        SUM(bajada IS NOT NULL AND bajada!=''), SUM(ld=1), SUM(firmada=1),
        MIN(CASE WHEN pub_ms>0 THEN visto END), MAX(visto) FROM items""").fetchone()
    corr = H.execute("SELECT COUNT(DISTINCT run) FROM salud").fetchone()[0]
    n_gn = H.execute(f"SELECT COUNT(*) FROM items WHERE medio IN ({','.join('?' * len(gn))})", gn).fetchone()[0]
    D["tot"] = {"notas": tot[0], "medios": tot[1], "analizadas": tot[2], "con_bajada": tot[3], "ld": tot[4], "firmadas": tot[5],
                "desde": tot[6][:10], "hasta": tot[7][:10], "corridas": corr, "medios_rss": len(rss), "medios_gn": len(gn), "notas_gn": n_gn}
    sc = H.execute("SELECT SUM(intentos), SUM(ok), SUM(robots) FROM scraping").fetchone()
    D["scrap"] = {"pedidos": sc[0], "ok": sc[1], "robots": sc[2]}
    D["tono"] = {k: v for k, v in H.execute(f"SELECT {TONO}, COUNT(*) FROM items GROUP BY 1") if k}

    # ---- rankings por medio (como build.py, "Como titula cada medio") ----
    S = H.execute(f"""SELECT medio, COUNT(*), AVG(cebo>=1), AVG({TONO}='n'),
        SUM(tono_bajada IS NOT NULL AND {TONO}='n'), SUM(tono_bajada IS NOT NULL AND {TONO}='n' AND tono_bajada!='n'),
        SUM(ld=1), SUM(ld=1 AND firmada=1), CAST(AVG(CASE WHEN largo>30 THEN largo END) AS INTEGER)
        FROM items WHERE tipo!='Oficial' GROUP BY medio""").fetchall()   # rankings de medios: sin las fuentes oficiales
    r1 = lambda x: round(100 * x, 1)
    D["cebo"] = sorted([[m, r1(c), n] for m, n, c, *_ in S if n >= 300], key=lambda r: -r[1])
    D["neg"] = sorted([[m, r1(g), n] for m, n, _, g, *_ in S if n >= 300], key=lambda r: -r[1])
    D["firm"] = sorted([[m, r1(f / ld), ld] for m, *_, ld, f, _l in S if ld and ld >= 200], key=lambda r: -r[1])
    D["exag"] = sorted([[m, r1(a / t), t] for m, _n, _c, _g, t, a, *_ in S if t and t >= 100], key=lambda r: -r[1])
    D["largo"] = sorted([[m, l] for m, *_, l in S if l], key=lambda r: -r[1])[:5]
    ents = Counter()
    for (e,) in H.execute("SELECT entidades FROM items WHERE entidades!=''"):
        ents.update(x for x in e.split("|") if x)
    D["ents"] = ents.most_common(6)
    D["modelos_tono"] = MODELOS_TONO

    # ---- clima: % negativo por dia y dolar blue, alineados por dia ----
    dias = H.execute(f"""SELECT date(pub_ms/1000,'unixepoch','-3 hours') d, COUNT(*), ROUND(100.0*AVG({TONO}='n'),1)
        FROM items WHERE pub_ms>0 GROUP BY d HAVING COUNT(*)>=1000 ORDER BY d""").fetchall()
    blue = dict(H.execute("SELECT fecha, venta FROM dolar WHERE casa='blue' ORDER BY fecha"))
    hoy = datetime.now().strftime("%Y-%m-%d")
    D["dolar_blue"] = [[f, v] for f, v in sorted(blue.items()) if f >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]
    clima = [{"dia": d, "n": n, "neg": p, "blue": blue.get(d)} for d, n, p in dias if d != hoy and blue.get(d)]
    D["clima"] = clima
    xs, ys = [c["neg"] for c in clima], [c["blue"] for c in clima]
    if len(clima) >= 3:
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        sx, sy = math.sqrt(sum((a - mx) ** 2 for a in xs)), math.sqrt(sum((b - my) ** 2 for b in ys))
        D["clima_r"] = round(sxy / (sx * sy), 2) if sx and sy else None
    D["clima_dias"] = len(clima)

    # ---- termometro: % negativo ultimas 24 h y promedio de los dias anteriores (como el tablero) ----
    ult = E.execute("SELECT MAX(publicado) FROM notas").fetchone()[0]
    corte = (datetime.fromisoformat(ult) - timedelta(hours=24)).isoformat(sep=" ")
    v24 = E.execute("SELECT COUNT(*), AVG(tono='n') FROM notas WHERE publicado>?", (corte,)).fetchone()
    prev = [c["neg"] for c in clima[-7:]]
    val = round(100 * v24[1])
    banda = next(b for a, z, b in [[0, 25, "Calmo"], [25, 40, "Moderado"], [40, 55, "Tenso"], [55, 101, "Muy tenso"]] if a <= val < z)
    D["termo"] = {"val": val, "banda": banda, "n": v24[0], "prom": round(sum(prev) / len(prev), 1) if prev else None,
                  "dias": [[c["dia"], c["neg"]] for c in clima[-7:]], "hasta": ult}

    # ---- titulares reales: la historia compartida mas cubierta (ultimas 72 h) ----
    corte72 = (datetime.fromisoformat(ult) - timedelta(hours=72)).isoformat(sep=" ")
    filas = E.execute("SELECT medio, titulo, publicado, tono, cebo, bajada, tono_bajada FROM notas WHERE publicado>? ORDER BY publicado", (corte72,)).fetchall()
    notas = [{"m": m, "t": t, "p": p, "ts": p, "tono": to, "cebo": c, "b": b, "tb": tb} for m, t, p, to, c, b, tb in filas]
    G = agrupar(notas)
    nm = lambda g: len({notas[i]["m"] for i in g})
    G.sort(key=lambda g: (-nm(g), -len(g)))

    def recortes(g, k=6):
        """una nota por medio, en orden de publicacion; primero los titulos distintos entre si (mas variedad de encuadre)."""
        vistos, out = set(), []
        for i in sorted(g, key=lambda i: notas[i]["p"]):
            x = notas[i]
            if x["m"] in vistos or len(x["t"]) > 110:
                continue
            vistos.add(x["m"])
            out.append({"medio": x["m"], "titulo": x["t"], "hora": hhmm(x["p"]), "fecha": x["p"][:10], "p": x["p"], "tono": x["tono"], "cebo": x["cebo"]})
        if len(out) > k:   # el primero siempre (la primicia); despues, los titulos que no repiten a otro ya elegido
            elegidos, textos = [out[0]], {norm(out[0]["titulo"])}
            for x in out[1:]:
                if len(elegidos) < k and norm(x["titulo"]) not in textos:
                    elegidos.append(x)
                    textos.add(norm(x["titulo"]))
            for x in out[1:]:
                if len(elegidos) < k and x not in elegidos:
                    elegidos.append(x)
            out = sorted(elegidos, key=lambda x: x["p"])
        t0 = datetime.fromisoformat(out[0]["p"]) if out else None
        for x in out:
            x["demora_min"] = round((datetime.fromisoformat(x.pop("p")) - t0).total_seconds() / 60)
        return out

    top = G[0]
    D["historia"] = {"medios": nm(top), "notas": len(top), "recortes": recortes(top, 6)}
    # otras historias del momento para la tapa: una nota por historia, de medios distintos
    tapa, usados = [], set()
    for g in G[1:]:
        r = recortes(g, 12)
        r = [x for x in r if x["medio"] not in usados and len(x["titulo"]) <= 95]
        if r:
            x = r[0]
            x["medios_historia"] = nm(g)
            tapa.append(x)
            usados.add(x["medio"])
        if len(tapa) == 4:
            break
    D["tapa"] = tapa
    # primicia: que medio publico primero mas historias que despues cubrieron 3 o mas medios
    prim = Counter(notas[min(g, key=lambda i: notas[i]["p"])]["m"] for g in G if nm(g) >= 3)
    D["primicia"] = prim.most_common(3)
    D["historias_compartidas"] = sum(1 for g in G if nm(g) >= 3)

    # ---- titulares reales con recursos de cebo (cebo >= 2), uno por medio ----
    cb, usados = [], set()
    for m, t, p, c in E.execute("SELECT medio, titulo, publicado, cebo FROM notas WHERE cebo>=2 AND length(titulo)<=95 ORDER BY cebo DESC, publicado DESC"):
        if m in usados:
            continue
        if sum(ch.isupper() for ch in t) > 0.5 * sum(ch.isalpha() for ch in t):
            continue   # titulos enteros en mayusculas: ilegibles como recorte
        rasgos, tramos = marcas_cebo(t)
        if not any(k in ("exagera", "intriga", "lista") for *_, k in tramos):
            continue   # se prefieren titulos con una palabra marcable (adjetivo exagerado, intriga, lista)
        usados.add(m)
        cb.append({"medio": m, "titulo": t, "hora": hhmm(p), "fecha": p[:10], "cebo": c, "rasgos": rasgos, "marcas": sin_superponer(tramos)})
        if len(cb) == 8:
            break
    D["cebo_ej"] = cb

    # ---- titulo negativo, bajada neutra (exageracion) ----
    ex, usados = [], {x["medio"] for x in cb[:6]}   # medios distintos de los del cebo, para no repetir titulos
    for m, t, b, p in E.execute("""SELECT medio, titulo, bajada, publicado FROM notas WHERE tono='n' AND tono_bajada='0'
            AND length(titulo)<=90 AND length(bajada) BETWEEN 60 AND 200 ORDER BY cebo=0 DESC, publicado DESC"""):   # sin cebo: que se vea solo la exageracion
        if m in usados:
            continue
        usados.add(m)
        ex.append({"medio": m, "titulo": t, "bajada": b, "hora": hhmm(p), "fecha": p[:10]})
        if len(ex) == 5:
            break
    D["exag_ej"] = ex

    # ---- demo SQL: la consulta de la diapositiva, corrida sobre explorar.db ----
    # una noticia, muchos encuadres: entre las historias de 8 medios o mas, la de titulos con tonos mas variados
    cand = [g for g in G[:40] if nm(g) >= 8]
    if cand:
        enc = max(cand, key=lambda g: (len({notas[i]["tono"] for i in g}), len({norm(notas[i]["t"]) for i in g}) / len(g), nm(g)))
        rec = recortes(enc, 6)
        D["encuadre"] = {"medios": nm(enc), "notas": len(enc), "recortes": rec,
                         "tonos": dict(Counter(notas[i]["tono"] for i in enc)), "cebo": sum(1 for i in enc if (notas[i]["cebo"] or 0) >= 1),
                         "ultimo_min": round((datetime.fromisoformat(max(notas[i]["p"] for i in enc)) - datetime.fromisoformat(min(notas[i]["p"] for i in enc))).total_seconds() / 60)}

    # ejemplo de procesamiento: un titular real con tema, entidades y tono
    fila = E.execute("""SELECT medio, titulo, publicado, temas, entidades, tono FROM notas WHERE tono='n' AND cebo=0 AND entidades!=''
        AND temas!='' AND temas NOT LIKE '%Otros%' AND length(titulo) BETWEEN 55 AND 85 AND medio IN ('Clarín','La Nación','Infobae','La Capital','TN','Perfil')
        ORDER BY publicado DESC LIMIT 1""").fetchone()
    if fila:
        D["ejemplo_nlp"] = {"medio": fila[0], "titulo": fila[1], "hora": hhmm(fila[2]), "fecha": fila[2][:10],
                            "temas": [t for t in fila[3].split("|") if t], "entidades": [e for e in fila[4].split("|") if e], "tono": fila[5]}

    # transparencia: una nota firmada por una persona y una firmada por "Redaccion"
    f1 = E.execute("SELECT medio, titulo, autor, publicado FROM notas WHERE firmada=1 AND autor!='' AND length(titulo)<=80 AND cebo=0 ORDER BY publicado DESC LIMIT 1").fetchone()
    f0 = E.execute("SELECT medio, titulo, autor, publicado FROM notas WHERE firmada=0 AND autor LIKE 'Redacci%' AND length(titulo)<=80 AND cebo=0 ORDER BY publicado DESC LIMIT 1").fetchone()
    D["firma_ej"] = [{"medio": m, "titulo": t, "autor": a, "hora": hhmm(p), "fecha": p[:10]} for m, t, a, p in (f1, f0) if m]

    # tono por figura: % de notas negativas de cada medio cuando menciona a cada figura (base completa)
    figs = [e for e, _ in ents.most_common(12) if e not in ("Policía",)][:6]
    meds = [m for m, *_ in sorted(S, key=lambda r: -r[1])][:7]
    cel = defaultdict(lambda: [0, 0])
    for m, e, t in H.execute(f"SELECT medio, entidades, {TONO} FROM items WHERE entidades!=''"):
        for x in e.split("|"):
            if x in figs:
                cel[(m, x)][0] += 1
                cel[(m, x)][1] += t == "n"
    prom = {f: round(100 * sum(cel[k][1] for k in cel if k[1] == f) / max(1, sum(cel[k][0] for k in cel if k[1] == f))) for f in figs}
    D["figuras"] = {"figuras": figs, "medios": meds, "prom": prom,
                    "celdas": [[m, f, round(100 * cel[(m, f)][1] / cel[(m, f)][0]), cel[(m, f)][0]] for m in meds for f in figs if cel[(m, f)][0] >= 10]}

    D["sql_demo"] = E.execute("""SELECT medio, ROUND(100*AVG(cebo>=1), 1) AS cebo, ROUND(100*AVG(tono='n'), 1) AS neg
        FROM notas GROUP BY medio HAVING COUNT(*) >= 50 ORDER BY cebo DESC LIMIT 6""").fetchall()
    D["explorar"] = {"notas": E.execute("SELECT COUNT(*) FROM notas").fetchone()[0], "desde": E.execute("SELECT MIN(publicado) FROM notas").fetchone()[0][:10], "hasta": ult[:16]}

    out = os.path.join(AQUI, "datos.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=1)
    print("escrito", out)
    print(f"  {D['tot']['notas']:,} notas, {D['tot']['medios']} medios, {D['tot']['corridas']} corridas; historia: {nm(top)} medios;",
          f"cebo_ej: {len(cb)}; exag_ej: {len(ex)}; clima: {len(clima)} dias (r={D.get('clima_r')})")


if __name__ == "__main__":
    main()
