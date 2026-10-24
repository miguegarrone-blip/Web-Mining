"""Enriquecimiento de notas: baja la pagina de cada nota y extrae datos que el RSS no trae.
- URL real: las notas de Google News se decodifican (googlenewsdecoder) para llegar al sitio del medio.
- Bajada: meta og:description (o el primer parrafo). Los RSS propios ya la traen (ver build.py).
- Datos estructurados: el bloque JSON-LD "NewsArticle" que los diarios incrustan para los buscadores
  (autor, seccion, fecha de modificacion, palabras clave y largo del cuerpo).
Buenas practicas: respeta robots.txt, se identifica con un User-Agent propio y limita los pedidos
simultaneos por dominio. Tiene tope de notas y de tiempo; lo pendiente se hace en la corrida siguiente."""
import re, html, json, time, threading, calendar, urllib.parse, urllib.robotparser
import concurrent.futures as cf
from collections import Counter
from email.utils import parsedate_tz
import requests
try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None

TOPE_NOTAS = 1200   # notas por corrida
TOPE_SEG = 420      # tiempo maximo por corrida
INTENTOS = 2        # despues de 2 fallos, la nota se deja como esta
POR_DOMINIO = 2     # pedidos simultaneos maximos a un mismo sitio
UA = {"User-Agent": "Mozilla/5.0 (compatible; monitor-de-medios/1.0; +https://miguegarrone-blip.github.io/Web-Mining/)",
      "Accept-Language": "es-AR,es;q=0.9"}

def limpiar(s, n=500):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]

# ---------- robots.txt y limite por dominio ----------
_robots, _sem, _lock = {}, {}, threading.Lock()
def dominio(u): return urllib.parse.urlsplit(u).netloc.lower()
def permitido(u):
    d = dominio(u)
    with _lock:
        rp = _robots.get(d)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get("https://%s/robots.txt" % d, headers=UA, timeout=8)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])   # sin robots.txt: todo permitido
        except Exception:
            rp.parse([])
        with _lock: _robots[d] = rp
    return rp.can_fetch(UA["User-Agent"], u)
def semaforo(u):
    d = dominio(u)
    with _lock:
        return _sem.setdefault(d, threading.Semaphore(POR_DOMINIO))

# ---------- extraccion ----------
_META = [re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]*content=["\']([^"\']{20,})', re.I),
         re.compile(r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]*(?:property|name)=["\'](?:og:description|description|twitter:description)', re.I)]
_P = re.compile(r"<p[^>]*>(.{60,}?)</p>", re.I | re.S)
_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.I | re.S)
def bajada_de_html(p):
    for rx in _META:
        m = rx.search(p)
        if m: return limpiar(m.group(1))
    m = _P.search(p)
    return limpiar(m.group(1)) if m else ""

def _articulos(o):
    if isinstance(o, list):
        for x in o: yield from _articulos(x)
    elif isinstance(o, dict):
        t = o.get("@type"); t = t if isinstance(t, list) else [t]
        if any(str(x).endswith(("NewsArticle", "Article", "BlogPosting")) for x in t): yield o
        if "@graph" in o: yield from _articulos(o["@graph"])
def _primero(v):
    while isinstance(v, list): v = v[0] if v else None
    return v
def _ms(s):
    """fecha ISO 8601 o RFC 2822 -> epoch ms (0 si no se entiende)"""
    if not s or not isinstance(s, str): return 0
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(s.strip().replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        t = parsedate_tz(s)
        return int((calendar.timegm(t[:9]) - (t[9] or 0)) * 1000) if t else 0
def json_ld(p):
    """datos del primer NewsArticle del HTML: autor, seccion, fecha de modificacion, palabras clave, largo en palabras"""
    for b in _LD.findall(p):
        try: objs = list(_articulos(json.loads(b.strip())))
        except Exception: continue
        if not objs: continue
        a = objs[0]
        au = a.get("author")
        if isinstance(au, list): au = ", ".join(filter(None, (x.get("name") if isinstance(x, dict) else str(x) for x in au[:3])))
        elif isinstance(au, dict): au = au.get("name")
        sec = _primero(a.get("articleSection"))
        sec = sec.split(",")[0].strip() if isinstance(sec, str) and not sec.startswith("http") else ""
        kw = a.get("keywords")
        kw = ", ".join(map(str, kw[:12])) if isinstance(kw, list) else (kw if isinstance(kw, str) else "")
        cuerpo = a.get("articleBody") or ""
        largo = len(cuerpo.split()) if isinstance(cuerpo, str) and cuerpo else int(a.get("wordCount") or 0)
        return {"autor": limpiar(au, 120) if isinstance(au, str) else "", "seccion": limpiar(sec, 60), "mod_ms": _ms(a.get("dateModified")),
                "claves": limpiar(kw, 300), "largo": largo or None}
    return {}

# autor generico (la redaccion o el propio medio) vs. nota firmada por una persona
_GEN = re.compile(r"redacci|newsroom|agencia|staff|equipo|diario|noticias|\.com|radio|canal|tv\b|online|digital|^(?:la|el|los)\s|infobae|clar[ií]n|naci[oó]n|perfil|[aá]mbito|p[aá]gina|cronista|destape|eltrece|ole\b|ol[eé]$|a24|c5n|tn$|mitre|cadena|continental|rosario|capital|ciudadano|conclusi|litoral|tribuno|gaceta|andes|ovaci", re.I)
def firmada(autor, medio=""):
    if not autor or len(autor.split()) < 2: return 0
    if _GEN.search(autor) or (medio and medio.lower().split(" (")[0] in autor.lower()): return 0
    return 1

def resolver(url):
    if "news.google.com" not in url: return url
    if not gnewsdecoder: return None
    r = gnewsdecoder(url, interval=0)
    return r.get("decoded_url") if r.get("success") else None

def una(h, url):
    """(h, url_real, bajada, datos_json_ld, error)"""
    try:
        real = resolver(url)
        if not real: return h, None, "", {}, "no se pudo resolver"
        if not permitido(real): return h, real, "", {}, "robots.txt"
        with semaforo(real):
            r = requests.get(real, headers=UA, timeout=(6, 15))
        if r.status_code != 200: return h, real, "", {}, "HTTP %s" % r.status_code
        p = r.text[:600000]
        return h, r.url or real, bajada_de_html(p), json_ld(p), ""
    except Exception as e:
        return h, None, "", {}, str(e)[:80]

def enriquecer(db):
    """Procesa las notas pendientes (las mas nuevas primero). Devuelve ({h: bajada} de lo completado, estadisticas por medio)."""
    pend = db.execute("SELECT h,url,titulo,medio FROM items WHERE ld IS NULL AND enr<? ORDER BY pub_ms DESC LIMIT ?", (INTENTOS, TOPE_NOTAS)).fetchall()
    info = {h: (t, m) for h, _, t, m in pend}
    hechos, stats, t0 = {}, {}, time.time()
    ex = cf.ThreadPoolExecutor(12)
    futs = [ex.submit(una, h, u) for h, u, _, _ in pend]
    try:
        for f in cf.as_completed(futs, timeout=TOPE_SEG):
            h, real, baj, ld, err = f.result()
            tit, medio = info[h]
            st = stats.setdefault(medio, Counter()); st["intentos"] += 1
            if baj and baj.lower().startswith(tit.lower()[:40]): baj = ""   # la "bajada" es el mismo titulo
            if err == "robots.txt":
                st["robots"] += 1
                db.execute("UPDATE items SET enr=?, url_real=? WHERE h=?", (INTENTOS, real, h)); continue
            if err:
                db.execute("UPDATE items SET enr=enr+1, url_real=COALESCE(?,url_real) WHERE h=?", (real, h)); continue
            st["ok"] += 1; st["bajada"] += bool(baj); st["ld"] += bool(ld)
            db.execute("""UPDATE items SET ld=?, url_real=?, bajada=COALESCE(NULLIF(?,''),bajada), autor=?, firmada=?, seccion=?, mod_ms=?, claves=?, largo=? WHERE h=?""",
                       (1 if ld else 0, real, baj, ld.get("autor", ""), firmada(ld.get("autor", ""), medio), ld.get("seccion", ""), ld.get("mod_ms", 0), ld.get("claves", ""), ld.get("largo"), h))
            if baj: hechos[h] = baj
    except cf.TimeoutError:
        pass
    ex.shutdown(wait=False, cancel_futures=True)
    # descripciones genericas del sitio ("Las ultimas noticias de...") repetidas en muchas notas: no son bajadas
    db.execute("UPDATE items SET bajada='' WHERE bajada!='' AND (medio,bajada) IN (SELECT medio,bajada FROM items WHERE bajada!='' GROUP BY medio,bajada HAVING COUNT(*)>3)")
    db.commit()
    tot = sum(stats.values(), Counter())
    print(f"enriquecimiento: {tot['ok']} paginas ({tot['bajada']} con bajada, {tot['ld']} con JSON-LD), {tot['intentos'] - tot['ok'] - tot['robots']} fallos, {tot['robots']} bloqueadas por robots.txt, {len(pend)} pendientes al inicio, {time.time() - t0:.0f}s")
    return hechos, stats
