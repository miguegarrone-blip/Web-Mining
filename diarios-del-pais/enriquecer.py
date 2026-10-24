"""Enriquecimiento de notas: consigue la URL real y la bajada (descripcion) de cada nota.
- Medios con RSS propio: la bajada ya viene en el feed (ver build.py, campo summary).
- Notas de Google News: se decodifica la URL de redireccion y se baja la pagina del medio
  para leer la meta og:description (o el primer parrafo).
Tiene tope de notas y de tiempo para no alargar la corrida horaria; lo que queda pendiente se hace en la siguiente."""
import re, html, time
import concurrent.futures as cf
import requests
try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None

TOPE_NOTAS = 600    # notas por corrida
TOPE_SEG = 240      # tiempo maximo por corrida
INTENTOS = 2        # despues de 2 fallos, la nota se deja sin bajada
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "es-AR,es;q=0.9"}

def limpiar(s, n=500):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]

_META = [re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]*content=["\']([^"\']{20,})', re.I),
         re.compile(r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]*(?:property|name)=["\'](?:og:description|description|twitter:description)', re.I)]
_P = re.compile(r"<p[^>]*>(.{60,}?)</p>", re.I | re.S)
def bajada_de_html(p):
    for rx in _META:
        m = rx.search(p)
        if m: return limpiar(m.group(1))
    m = _P.search(p)
    return limpiar(m.group(1)) if m else ""

def resolver(url):
    if "news.google.com" not in url: return url
    if not gnewsdecoder: return None
    r = gnewsdecoder(url, interval=0)
    return r.get("decoded_url") if r.get("success") else None

def una(h, url):
    try:
        real = resolver(url)
        if not real: return h, None, "", "no se pudo resolver"
        r = requests.get(real, headers=UA, timeout=(6, 15))
        return h, r.url or real, bajada_de_html(r.text[:400000]), ""
    except Exception as e:
        return h, None, "", str(e)[:80]

def enriquecer(db):
    """Completa url_real y bajada de las notas pendientes (las mas nuevas primero). Devuelve {h: bajada} de lo completado."""
    pend = db.execute("SELECT h,url,titulo FROM items WHERE (bajada IS NULL OR bajada='') AND enr<? ORDER BY pub_ms DESC LIMIT ?", (INTENTOS, TOPE_NOTAS)).fetchall()
    tit = {h: t for h, _, t in pend}
    hechos, fallos, t0 = {}, 0, time.time()
    ex = cf.ThreadPoolExecutor(6)
    futs = [ex.submit(una, h, u) for h, u, _ in pend]
    try:
        for f in cf.as_completed(futs, timeout=TOPE_SEG):
            h, real, baj, err = f.result()
            if baj and baj.lower().startswith(tit[h].lower()[:40]): baj = ""   # la "bajada" es el mismo titulo
            db.execute("UPDATE items SET enr=enr+1, url_real=COALESCE(?,url_real), bajada=? WHERE h=?", (real, baj, h))
            if baj: hechos[h] = baj
            else: fallos += 1
    except cf.TimeoutError:
        pass
    ex.shutdown(wait=False, cancel_futures=True)
    # descripciones genericas del sitio ("Las ultimas noticias de...") repetidas en muchas notas: no son bajadas
    db.execute("UPDATE items SET bajada='' WHERE bajada!='' AND (medio,bajada) IN (SELECT medio,bajada FROM items WHERE bajada!='' GROUP BY medio,bajada HAVING COUNT(*)>3)")
    db.commit()
    print(f"enriquecimiento: {len(hechos)} con bajada, {fallos} sin, {len(pend)} pendientes al inicio, {time.time() - t0:.0f}s")
    return hechos
