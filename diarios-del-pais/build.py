"""Pipeline: baja medios -> valida -> guarda en SQLite -> exporta CSV -> genera rosario.html
Solo usa libreria estandar + requests + feedparser."""
import feedparser, requests, json, time, html, calendar, csv, os, re, sqlite3, hashlib, statistics, urllib.parse
import concurrent.futures as cf
from datetime import datetime, timezone, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from topics import tag, merge_tema, entrenar_nb, predecir_nb, UMBRAL
from nlp import tone, cebo, cebo_rasgos, ents as get_ents
from enriquecer import enriquecer, depurar_bajada
import bert

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", BASE)   # donde viven historico.db y historico.csv
OUT = os.environ.get("OUT_DIR", BASE)     # donde se escribe rosario.html
os.makedirs(DATA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
TOPE = 100          # notas maximas por feed que se leen
# ---- REGLAS (para que ningun numero crezca sin limite) ----
VENTANA_HORAS = 48      # "notas analizadas" = notas publicadas en las ultimas 48 h
POR_MEDIO_PAGINA = 100  # tope por medio dentro de esa ventana
RETENCION_DIAS = 30     # la base y el CSV guardan solo los ultimos 30 dias (la base comprimida debe quedar bajo el limite de 100 MB de GitHub)
TOPE_BERT = 4000        # textos por corrida que pasan por XLM-RoBERTa (titulos y bajadas por separado)
H = {"User-Agent": "Mozilla/5.0 (monitor-de-medios; uso personal)"}
AR = timedelta(hours=-3)

def gn(d): return "https://news.google.com/rss/search?q=" + urllib.parse.quote("site:" + d + " when:2d") + "&hl=es-419&gl=AR&ceid=AR:es-419"
# medio: (alcance, tipo, [feeds]); "gn:" = Google News por sitio
F = {
"La Capital":("Rosario","Diario",["https://www.lacapital.com.ar/rss/ultimas-noticias.xml"]),
"Rosarioplus":("Rosario","Digital",["https://rosarioplus.com/rss"]),
"El Ciudadano":("Rosario","Diario",["https://www.elciudadanoweb.com/feed/"]),
"Conclusión":("Rosario","Digital",["https://www.conclusion.com.ar/feed/"]),
"Rosario3":("Rosario","TV",["gn:rosario3.com"]),
"Olé":("Nacional","Diario",["https://www.ole.com.ar/rss/ultimas-noticias/","https://www.ole.com.ar/rss/futbol-primera/","https://www.ole.com.ar/rss/rosario-central/"]),
"Clarín":("Nacional","Diario",["https://www.clarin.com/rss/lo-ultimo/","gn:clarin.com"]),
"La Nación":("Nacional","Diario",["https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml"]),
"Infobae":("Nacional","Digital",["https://www.infobae.com/arc/outboundfeeds/rss/"]),
"Perfil":("Nacional","Diario",["https://www.perfil.com/feed"]),
"Ámbito":("Nacional","Diario",["https://www.ambito.com/rss/pages/home.xml"]),
"Noticias Argentinas":("Nacional","Digital",["https://noticiasargentinas.com/rss"]),
"Página/12":("Nacional","Diario",["gn:pagina12.com.ar"]),
"El Cronista":("Nacional","Diario",["gn:cronista.com"]),
"El Destape":("Nacional","Digital",["gn:eldestapeweb.com"]),
"Infocielo":("Nacional","Digital",["gn:infocielo.com"]),
"TN":("Nacional","TV",["https://tn.com.ar/arc/outboundfeeds/rss/?outputType=xml"]),
"C5N":("Nacional","TV",["gn:c5n.com"]),
"A24":("Nacional","TV",["gn:a24.com"]),
"El Trece":("Nacional","TV",["gn:eltrecetv.com.ar"]),
"Canal 26":("Nacional","TV",["gn:canal26.com"]),
"Cadena 3":("Nacional","Radio",["gn:cadena3.com"]),
"Radio Mitre":("Nacional","Radio",["gn:radiomitre.cienradios.com"]),
"Radio 10":("Nacional","Radio",["gn:radio10.com.ar"]),
"Radio Continental":("Nacional","Radio",["gn:continental.com.ar"]),
"Aire de Santa Fe":("Interior","Digital",["https://www.airedesantafe.com.ar/rss/ultimas-noticias.xml"]),
"El Litoral":("Interior","Diario",["gn:ellitoral.com"]),
"La Voz":("Interior","Diario",["gn:lavoz.com.ar"]),
"Eldoce":("Interior","TV",["gn:eldoce.tv"]),
"Los Andes":("Interior","Diario",["gn:losandes.com.ar"]),
"La Gaceta":("Interior","Diario",["gn:lagaceta.com.ar"]),
"El Tribuno":("Interior","Diario",["gn:eltribuno.com"]),
"El Día (La Plata)":("Interior","Diario",["https://www.eldia.com/.rss"]),
"Río Negro":("Interior","Diario",["https://www.rionegro.com.ar/feed/"]),
"El Chubut":("Interior","Diario",["gn:elchubut.com.ar"]),
"Diario Chaco":("Interior","Diario",["https://www.diariochaco.com/rss.xml","gn:diariochaco.com"]),
"Misiones Online":("Interior","Digital",["https://misionesonline.net/feed/","gn:misionesonline.net"]),
"Rosario Nuestro":("Rosario","Digital",["gn:rosarionuestro.com"]),
"Uno Santa Fe":("Interior","Digital",["gn:unosantafe.com.ar"]),
"Elonce":("Interior","TV",["gn:elonce.com"]),
"La Nueva (Bahía Blanca)":("Interior","Diario",["gn:lanueva.com"]),
"La Capital (Mar del Plata)":("Interior","Diario",["gn:lacapitalmdp.com"]),
"El Diario de la República":("Interior","Diario",["gn:eldiariodelarepublica.com"]),
"Diario de Cuyo":("Interior","Diario",["gn:diariodecuyo.com.ar"]),
"Gobierno de Santa Fe":("Interior","Oficial",["gn:santafe.gob.ar"]),
"Municipalidad de Rosario":("Rosario","Oficial",["gn:rosario.gob.ar"]),
}

# ---------- red con reintentos ----------
SES = requests.Session()
SES.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))))
SES.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1.0)))

def fetch(job):
    medio, u = job
    real = gn(u[3:]) if u.startswith("gn:") else u
    t0 = time.time()
    try:
        r = SES.get(real, headers=H, timeout=(8, 25))
        ents = feedparser.parse(r.content).entries[:TOPE]
        return medio, ents, r.status_code, int((time.time() - t0) * 1000), ""
    except Exception as e:
        return medio, [], 0, int((time.time() - t0) * 1000), str(e)[:120]

# ---------- utilidades ----------
def canon(u):
    if "news.google.com" in u: return u
    p = urllib.parse.urlsplit(u)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", urllib.parse.urlencode(q), ""))
def h(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]
def tsms(ts):
    try: return int(calendar.timegm(ts) * 1000) if ts else 0
    except Exception: return 0
def ntitle(t): return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

# ---------- validacion ----------
def validar(x, ahora_ms):
    t = x["t"]
    if len(t) < 12: return "titulo corto"
    if len(t) > 320: return "titulo largo"
    if len(t.split()) < 3: return "titulo corto"
    low = t.lower()
    if low.startswith(("noticias sobre", "últimas noticias", "ultimas noticias", "videos", "video mobile", "se ofr", "avisos fun", "últimas noticias -", "ultimas noticias -")) or " p/trabajo" in low: return "no es una nota"
    if not x["u"].startswith(("http://", "https://")): return "url invalida"
    if x["ts"] and (x["ts"] > ahora_ms + 2 * 86400000 or x["ts"] < 1577836800000): return "fecha fuera de rango"
    return ""

# ---------- base de datos ----------
DB = sqlite3.connect(os.path.join(DATA, "historico.db"))
DB.executescript("""
CREATE TABLE IF NOT EXISTS items(h TEXT PRIMARY KEY, th TEXT, medio TEXT, alcance TEXT, tipo TEXT, titulo TEXT, url TEXT, pub_ms INTEGER, temas TEXT, entidades TEXT, tono_auto TEXT, tono_manual TEXT, visto TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ix_medio_titulo ON items(medio, th);
CREATE TABLE IF NOT EXISTS salud(run TEXT, medio TEXT, ok INTEGER, http INTEGER, n_raw INTEGER, n_valid INTEGER, ms INTEGER, err TEXT);
CREATE TABLE IF NOT EXISTS cuarentena(run TEXT, medio TEXT, motivo TEXT, titulo TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS scraping(run TEXT, medio TEXT, intentos INTEGER, ok INTEGER, bajada INTEGER, ld INTEGER, robots INTEGER);
""")
# columnas agregadas despues (bases viejas): datos del enriquecimiento (ver enriquecer.py) y de "como titula" (nlp.cebo)
cols = {r[1] for r in DB.execute("PRAGMA table_info(items)")}
for c, tipo in (("url_real", "TEXT"), ("bajada", "TEXT"), ("enr", "INTEGER DEFAULT 0"), ("tema_fuente", "TEXT DEFAULT 'reglas'"),
                ("ld", "INTEGER"), ("autor", "TEXT"), ("firmada", "INTEGER"), ("seccion", "TEXT"), ("mod_ms", "INTEGER"), ("claves", "TEXT"), ("largo", "INTEGER"),
                ("tono_bajada", "TEXT"), ("cebo", "INTEGER"), ("bert_t", "TEXT"), ("bert_b", "TEXT")):
    if c not in cols: DB.execute("ALTER TABLE items ADD COLUMN %s %s" % (c, tipo))
COLS = "h,th,medio,alcance,tipo,titulo,url,pub_ms,temas,entidades,tono_auto,tono_manual,visto"
# migracion unica desde el CSV anterior
if DB.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0 and os.path.exists(os.path.join(DATA, "historico.csv")):
    with open(os.path.join(DATA, "historico.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            DB.execute("INSERT OR IGNORE INTO items(" + COLS + ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (h(canon(r["url"])), h(ntitle(r["titulo"])), r["medio"], r["alcance"], r["tipo"], r["titulo"], r["url"], int(r["publicado_ms"] or 0), r["temas"], r["entidades"], r["tono_auto"], r["tono_manual"], r["capturado"]))
    DB.commit()

LB = json.load(open(os.path.join(BASE, "labels.json"), encoding="utf-8"))
run = datetime.now().isoformat(timespec="seconds")
ahora_ms = int(time.time() * 1000)

jobs = [(m, u) for m, (r, tp, us) in F.items() for u in us]
with cf.ThreadPoolExecutor(10) as ex: res = list(ex.map(fetch, jobs))

items, seen, nuevos = [], set(), []
stat = {m: {"ok": 1, "http": 200, "n_raw": 0, "n_valid": 0, "ms": 0, "err": "", "fallos": 0, "nf": len(F[m][2])} for m in F}
cuarentena, dups = {}, 0
for m, ents, code, ms, err in res:
    s = stat[m]; s["ms"] = max(s["ms"], ms); s["n_raw"] += len(ents)
    if err or code != 200:
        s["fallos"] += 1; s["http"] = code or s["http"]; s["err"] = err or ("HTTP %s" % code)
        if s["fallos"] >= s["nf"]: s["ok"] = 0   # solo cae si fallan todos los feeds del medio
    for e in ents:
        t = html.unescape(e.get("title", "")).strip(); u = e.get("link", "")
        if "news.google.com" in u and " - " in t: t = t.rsplit(" - ", 1)[0].strip()
        ts = e.get("published_parsed") or e.get("updated_parsed")
        x = {"m": m, "r": F[m][0], "tp": F[m][1], "t": t, "u": u, "ts": tsms(ts)}
        motivo = validar(x, ahora_ms)
        if motivo:
            cuarentena[motivo] = cuarentena.get(motivo, 0) + 1
            DB.execute("INSERT INTO cuarentena VALUES(?,?,?,?,?)", (run, m, motivo, t[:200], u[:300])); continue
        k = (m, h(ntitle(t)))
        if k in seen or canon(u) in seen: dups += 1; continue
        seen.add(k); seen.add(canon(u))
        x["h"] = h(canon(u))
        x["b"] = "" if "news.google.com" in u else depurar_bajada(e.get("summary", ""))[:400]   # bajada que trae el RSS propio
        if x["b"].lower().startswith(t.lower()[:40]): x["b"] = ""
        x["tg"] = tag(t + " " + x["b"], m); x["sa"] = tone(t); x["e"] = get_ents(t); x["cr"] = cebo_rasgos(t)
        if u in LB: x["s"] = LB[u][1]
        items.append(x); s["n_valid"] += 1
        cur = DB.execute("INSERT OR IGNORE INTO items(" + COLS + ",url_real,bajada,tono_bajada,cebo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (x["h"], k[1], m, x["r"], x["tp"], t, u, x["ts"], "|".join(x["tg"]), "|".join(x["e"]), x["sa"], x.get("s", ""), run, None if "news.google.com" in u else u, x["b"] or None, tone(x["b"]) if x["b"] else None, cebo(t)))
        if cur.rowcount: nuevos.append(x)
for m, s in stat.items():
    DB.execute("INSERT INTO salud VALUES(?,?,?,?,?,?,?,?)", (run, m, s["ok"], s["http"], s["n_raw"], s["n_valid"], s["ms"], s["err"]))
# retencion: se borra lo mas viejo que RETENCION_DIAS (la cuarentena solo sirve para diagnostico: 7 dias)
for t, col, dias in (("items", "visto", RETENCION_DIAS), ("salud", "run", RETENCION_DIAS), ("cuarentena", "run", 7)):
    corte = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    DB.execute("DELETE FROM %s WHERE %s < ?" % (t, col), (corte,))
DB.commit()

# enriquecimiento (pagina de cada nota: url real, bajada, JSON-LD) y re-etiquetado de temas con titulo + bajada
hechos, scr = enriquecer(DB)
for h_, b_ in hechos.items():
    t_, m_ = DB.execute("SELECT titulo,medio FROM items WHERE h=?", (h_,)).fetchone()
    DB.execute("UPDATE items SET temas=?, tema_fuente='reglas', tono_bajada=? WHERE h=?", ("|".join(tag(t_ + " " + b_, m_)), tone(b_), h_))
for m_, st in scr.items():
    DB.execute("INSERT INTO scraping VALUES(?,?,?,?,?,?,?)", (run, m_, st["intentos"], st["ok"], st["bajada"], st["ld"], st["robots"]))
DB.execute("DELETE FROM scraping WHERE run < ?", ((datetime.now() - timedelta(days=RETENCION_DIAS)).isoformat(timespec="seconds"),))
DB.commit()

# temas: si cambiaron las reglas se re-etiqueta todo; despues un Naive Bayes entrenado con lo que
# clasificaron las reglas completa las notas "Otros" (solo si esta seguro, ver topics.UMBRAL)
DB.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
huella_t = hashlib.sha1(open(os.path.join(BASE, "topics.py"), "rb").read()).hexdigest()
if (DB.execute("SELECT v FROM meta WHERE k='temas'").fetchone() or [""])[0] != huella_t:
    for h_, t_, b_, m_ in DB.execute("SELECT h,titulo,bajada,medio FROM items").fetchall():
        DB.execute("UPDATE items SET temas=?, tema_fuente='reglas' WHERE h=?", ("|".join(tag(t_ + " " + (b_ or ""), m_)), h_))
    DB.execute("INSERT OR REPLACE INTO meta VALUES('temas',?)", (huella_t,))
NB = entrenar_nb([(t_ + " " + (b_ or ""), tg.split("|")[0]) for t_, b_, tg in DB.execute("SELECT titulo,bajada,temas FROM items WHERE tema_fuente='reglas' AND temas!='Otros'")])
n_nb = 0
for h_, t_, b_ in DB.execute("SELECT h,titulo,bajada FROM items WHERE temas='Otros' OR tema_fuente='modelo'").fetchall():
    k_, p_ = predecir_nb(NB, t_ + " " + (b_ or ""))
    if k_ and p_ >= UMBRAL: DB.execute("UPDATE items SET temas=?, tema_fuente='modelo' WHERE h=?", (k_, h_)); n_nb += 1
    else: DB.execute("UPDATE items SET temas='Otros', tema_fuente='reglas' WHERE h=?", (h_,))
DB.commit()
print("temas asignados por el modelo:", n_nb)
EXTRA = {h_: (ur or "", b_ or "", tg) for h_, ur, b_, tg in DB.execute("SELECT h,url_real,bajada,temas FROM items WHERE pub_ms>=?", (ahora_ms - VENTANA_HORAS * 3600 * 1000,))}
for x in items:
    if x["h"] in EXTRA:
        ur, b_, tg = EXTRA[x["h"]]
        if ur: x["u"] = ur
        if b_: x["b"] = b_
        if tg: x["tg"] = [merge_tema(z) for z in tg.split("|")]

# tono con BERT: probabilidades de XLM-RoBERTa para los titulos y bajadas que todavia no las tienen (ver bert.py)
tocadas = set(hechos)                       # notas cuyo tono hay que recalcular: bajada nueva o probas nuevas
if bert.disponible():
    t0 = time.time()
    for col, txt in (("bert_t", "titulo"), ("bert_b", "bajada")):
        pend = DB.execute(f"SELECT h,{txt} FROM items WHERE {col} IS NULL AND {txt}!='' ORDER BY pub_ms DESC LIMIT ?", (TOPE_BERT,)).fetchall()
        for (h_, _), pb in zip(pend, bert.probas([t_ for _, t_ in pend])):
            DB.execute(f"UPDATE items SET {col}=? WHERE h=?", (bert.a_texto(pb), h_)); tocadas.add(h_)
        print(f"BERT {txt}: {len(pend)} textos")
    DB.execute("UPDATE items SET bert_b=NULL WHERE bajada IS NULL OR bajada=''")
    DB.commit(); print(f"BERT: {time.time() - t0:.0f}s")
def retono(h_, t_, b_, bt, bb):
    DB.execute("UPDATE items SET tono_auto=?, tono_bajada=?, cebo=? WHERE h=?", (tone(t_, bert.de_texto(bt)), tone(b_, bert.de_texto(bb)) if b_ else None, cebo(t_), h_))
# si cambio el modelo de tono, re-clasifica todo lo guardado; si no, solo lo tocado en esta corrida. Siempre aplica las etiquetas manuales
DB.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
huella = hashlib.sha1(b"".join(open(os.path.join(BASE, f), "rb").read() for f in ("nlp.py", "modelo_tono.json", "modelo_tono_bert.json"))).hexdigest()
SEL = "SELECT h,titulo,bajada,bert_t,bert_b FROM items"
if (DB.execute("SELECT v FROM meta WHERE k='modelo_tono'").fetchone() or [""])[0] != huella:
    for r_ in DB.execute(SEL).fetchall(): retono(*r_)
    DB.execute("INSERT OR REPLACE INTO meta VALUES('modelo_tono',?)", (huella,))
else:
    for h_ in tocadas:
        r_ = DB.execute(SEL + " WHERE h=?", (h_,)).fetchone()
        if r_: retono(*r_)
for u_, (k_, s_) in LB.items():
    DB.execute("UPDATE items SET tono_manual=? WHERE url=?", (s_, u_))
DB.commit()
TON = dict(DB.execute("SELECT h,tono_auto FROM items WHERE pub_ms>=?", (ahora_ms - VENTANA_HORAS * 3600 * 1000,)).fetchall())
for x in items:
    if x["h"] in TON: x["sa"] = TON[x["h"]]

# CSV exportable (Power BI / Excel): se regenera desde la base, solo con la ventana de retencion
HC = os.path.join(DATA, "historico.csv")
with open(HC, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["capturado", "medio", "alcance", "tipo", "titulo", "url", "publicado_ms", "temas", "entidades", "tono_auto", "tono_manual", "url_real", "bajada", "tono_bajada", "cebo", "autor", "firmada", "seccion", "largo", "bert_titulo", "bert_bajada"])
    for r in DB.execute("SELECT visto,medio,alcance,tipo,titulo,url,pub_ms,temas,entidades,tono_auto,tono_manual,url_real,bajada,tono_bajada,cebo,autor,firmada,seccion,largo,bert_t,bert_b FROM items ORDER BY visto, pub_ms"): w.writerow(r)

# ---------- pagina: notas de las ultimas VENTANA_HORAS, con tope por medio ----------
items.sort(key=lambda x: x["ts"], reverse=True)
desde = ahora_ms - VENTANA_HORAS * 3600 * 1000
cnt, pag = {}, []
for x in items:
    if x["ts"] and x["ts"] < desde: continue          # fuera de la ventana
    cnt[x["m"]] = cnt.get(x["m"], 0) + 1
    if cnt[x["m"]] <= POR_MEDIO_PAGINA: pag.append(x)

# ---------- calibracion del tono (ver tono_entrenar.py) ----------
CALP = os.path.join(BASE, "calibracion.json")
CAL = json.load(open(CALP, encoding="utf-8")) if os.path.exists(CALP) else None
_ONE = {"n": [1, 0, 0], "0": [0, 1, 0], "p": [0, 0, 1]}
def dist(sm, sa):
    """reparto esperado [neg, neu, pos] de una nota: etiqueta manual si existe; si no, corregido por calibracion"""
    if sm in _ONE: return _ONE[sm]
    if CAL: p = CAL["cal"][sa]["p"]; return [p["n"], p["0"], p["p"]]
    return _ONE[sa]

# ---------- agregados historicos (por fecha de publicacion, hora Argentina) ----------
rows = DB.execute("SELECT medio,pub_ms,temas,entidades,tono_auto,tono_manual FROM items WHERE pub_ms>0").fetchall()
def dia(ms): return (datetime.fromtimestamp(ms / 1000, timezone.utc) + AR).strftime("%Y-%m-%d")
def hora(ms): return (datetime.fromtimestamp(ms / 1000, timezone.utc) + AR).strftime("%Y-%m-%dT%H")
dn, dneg, tema, ent, horas, horasT = {}, {}, {}, {}, {}, {}
lim7d = ahora_ms - 7 * 24 * 3600 * 1000   # el grafico por hora llega hasta 7 dias
for m, ms, tg, en, sa, sm in rows:
    d = dia(ms); dn[d] = dn.get(d, 0) + 1
    dneg[d] = dneg.get(d, 0) + dist(sm, sa)[0]
    for t in {merge_tema(x) for x in tg.split("|") if x}:   # el historico guarda nombres viejos: se fusionan al leer
        tema.setdefault(t, {}); tema[t][d] = tema[t].get(d, 0) + 1
    for e in en.split("|"):
        if e: ent.setdefault(e, {}); ent[e][d] = ent[e].get(d, 0) + 1
    if lim7d <= ms <= ahora_ms:
        hh = hora(ms); v = dist(sm, sa)                                      # [negativas, neutras, positivas] esperadas
        a = horas.setdefault(hh, [0, 0, 0])
        for k in range(3): a[k] += v[k]
        for t in {merge_tema(x) for x in tg.split("|") if x}:
            a = horasT.setdefault(t, {}).setdefault(hh, [0, 0, 0])
            for k in range(3): a[k] += v[k]
dneg = {d: round(v, 2) for d, v in dneg.items()}
horas = {h_: [round(x, 2) for x in v] for h_, v in horas.items()}
horasT = {t: {h_: [round(x, 2) for x in v] for h_, v in hs.items()} for t, hs in horasT.items()}
AGG = {"dn": dn, "dneg": dneg, "tema": tema, "ent": ent, "horas": horas, "horasT": horasT, "hoy": dia(ahora_ms)}

# ---------- por medio y periodo (pestaña Analisis: filtros de periodo, agenda y tono por medio) ----------
# MED[medio] = {r: alcance, tp: tipo, p: {dias: {n, t: [neg, neu, pos] esperados, tg: {tema: notas}}}}
PERIODOS = (1, 2, 7, 30)
MED = {m: {"r": F[m][0], "tp": F[m][1], "p": {d: {"n": 0, "t": [0.0, 0.0, 0.0], "tg": {}, "en": {}} for d in PERIODOS}} for m in F}
for m, ms, tg, en, sa, sm in rows:
    if m not in MED or ms > ahora_ms: continue
    v = dist(sm, sa); temas_n = {merge_tema(x) for x in tg.split("|") if x}
    for d in PERIODOS:
        if ms < ahora_ms - d * 86400000: continue
        a = MED[m]["p"][d]; a["n"] += 1
        for k in range(3): a["t"][k] += v[k]
        for t in temas_n: a["tg"][t] = a["tg"].get(t, 0) + 1
        for e in en.split("|"):            # menciones de cada figura y cuantas se esperan negativas (matriz medio x figura)
            if e: z = a["en"].setdefault(e, [0, 0.0]); z[0] += 1; z[1] += v[0]
for m in MED:
    for d in PERIODOS:
        MED[m]["p"][d]["t"] = [round(x, 1) for x in MED[m]["p"][d]["t"]]
        MED[m]["p"][d]["en"] = {e: [z[0], round(z[1], 1)] for e, z in MED[m]["p"][d]["en"].items()}
AGG["med"] = MED

# ---------- como titula cada medio (todo el historico) ----------
# alarma: de los titulos negativos con bajada, cuantos tienen una bajada que NO es negativa (el titulo exagera el hecho)
# cebo: rasgos de clickbait en el titulo (nlp.cebo). firmadas: notas con autor persona, sobre las que tienen JSON-LD
TONO = "COALESCE(NULLIF(tono_manual,''),tono_auto)"
SENS = [dict(zip(("m", "n", "cebo", "cebo_pct", "tneg", "alarma", "nld", "firm", "largo"), r)) for r in DB.execute(f"""
  SELECT medio, COUNT(*), ROUND(AVG(cebo),3), ROUND(AVG(cebo>=1),3),
         SUM(tono_bajada IS NOT NULL AND {TONO}='n'), SUM(tono_bajada IS NOT NULL AND {TONO}='n' AND tono_bajada!='n'),
         SUM(ld=1), SUM(ld=1 AND firmada=1), CAST(AVG(CASE WHEN largo>30 THEN largo END) AS INTEGER)
  FROM items GROUP BY medio""")]
AUT = DB.execute(f"SELECT autor, medio, COUNT(*) n, ROUND(AVG({TONO}='n'),2) FROM items WHERE firmada=1 GROUP BY autor, medio ORDER BY n DESC LIMIT 25").fetchall()
EJ_AL = DB.execute(f"SELECT medio, titulo, bajada, COALESCE(url_real,url) FROM items WHERE {TONO}='n' AND tono_bajada='0' AND pub_ms>=? ORDER BY cebo DESC, pub_ms DESC LIMIT 12", (desde,)).fetchall()
EJ_CB = DB.execute("SELECT medio, titulo, cebo, COALESCE(url_real,url) FROM items WHERE cebo>=2 AND pub_ms>=? ORDER BY cebo DESC, pub_ms DESC LIMIT 12", (desde,)).fetchall()
corte24 = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
SCR = DB.execute("SELECT medio, SUM(intentos), SUM(ok), SUM(bajada), SUM(ld), SUM(robots) FROM scraping WHERE run>=? GROUP BY medio ORDER BY medio", (corte24,)).fetchall()
PROG = DB.execute("SELECT SUM(ld IS NOT NULL OR enr>=2), COUNT(*) FROM items").fetchone()
AGG.update({"prog": PROG, "sens": SENS, "aut": AUT, "ej_al": EJ_AL, "ej_cb": EJ_CB, "scr": SCR})

# ---------- salud de datos ----------
SAL = []
for m in F:
    hist = [r[0] for r in DB.execute("SELECT n_raw FROM salud WHERE medio=? AND run<? ORDER BY run DESC LIMIT 14", (m, run))]
    med = statistics.median(hist) if hist else None
    s = stat[m]
    ult = DB.execute("SELECT pub_ms,titulo,url FROM items WHERE medio=? AND pub_ms>0 ORDER BY pub_ms DESC LIMIT 1", (m,)).fetchone() or (0, "", "")
    lastpub = ult[0]
    nd = DB.execute("SELECT COUNT(*) FROM items WHERE medio=? AND pub_ms=0", (m,)).fetchone()[0]
    tot = DB.execute("SELECT COUNT(*) FROM items WHERE medio=?", (m,)).fetchone()[0]
    estado = "caida" if (not s["ok"] or s["n_raw"] == 0) else ("degradada" if (s["n_valid"] == 0 or (med and len(hist) >= 3 and s["n_raw"] < 0.5 * med)) else "ok")
    SAL.append({"m": m, "estado": estado, "http": s["http"], "n": s["n_raw"], "v": s["n_valid"], "med": med, "ms": s["ms"], "err": s["err"], "last": lastpub, "lt": ult[1], "lu": ult[2], "nd": round(100 * nd / tot) if tot else 0, "tot": tot})
HEALTH = {"run": run, "rows": SAL, "valid": len(items), "dups": dups, "cuarentena": cuarentena, "total_db": DB.execute("SELECT COUNT(*) FROM items").fetchone()[0], "corridas": DB.execute("SELECT COUNT(DISTINCT run) FROM salud").fetchone()[0]}

AG = round(100 * CAL["acierto_cv"]) if CAL else 0
now = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
tpl = open(os.path.join(BASE, "tpl2.html"), encoding="utf-8").read()
js = lambda o: json.dumps(o, ensure_ascii=False)
out = tpl.replace("__DATA__", js(pag)).replace("__AGG__", js(AGG)).replace("__HEALTH__", js(HEALTH)).replace("__NOW__", now).replace("__AGREE__", str(AG)).replace("__MUESTRA__", str(CAL["muestra"]) if CAL else "").replace("__CAL__", js(CAL["cal"] if CAL else None)).replace("__VENTANA__", str(VENTANA_HORAS)).replace("__RETENCION__", str(RETENCION_DIAS))
open(os.path.join(OUT, "rosario.html"), "w", encoding="utf-8").write(out)
DB.execute("VACUUM")   # devuelve el espacio de lo borrado por la retencion
print("corrida", run, "| validas", len(items), "| nuevas", len(nuevos), "| duplicadas", dups, "| cuarentena", cuarentena, "| acuerdo tono", AG)
print("fuentes caidas/degradadas:", [(r["m"], r["estado"]) for r in SAL if r["estado"] != "ok"])
