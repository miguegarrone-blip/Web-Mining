"""Relevamiento COMPLETO de La Gallega y DAR (tiendas ASP con la misma plataforma).

Ambas aceptan cualquier texto en el buscador y la cookie `cantP` fija cuántos productos muestran por página
(hasta 500). Una búsqueda amplia ("a") recorre casi todo el catálogo; las demás vocales suman lo que falte.
Se pagina hasta que una página no trae productos nuevos.

Uso:
    python asp_full.py                  # La Gallega y DAR
    python asp_full.py dar              # una sola
"""
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import dar_scraper
import gallega_scraper
import net
from store import save_rows
from vtex_scraper import DB_PATH, SCHEMA

TERMS = ("a", "e", "o", "i", "u")      # la primera trae casi todo; las otras suman los pocos que falten
PER_PAGE = 500
MAX_PAGES = 80
PAUSE = (0.2, 0.5)


def id_of(html, pattern):
    m = re.search(pattern, html)
    return m.group(1) if m else None


def gallega_session():
    s = net.new_session()
    s.get(gallega_scraper.BASE + "/", timeout=40)
    s.cookies.set("cantP", str(PER_PAGE), domain="www.lagallega.com.ar", path="/")
    return s


def gallega_pages(session, term):
    for pg in range(1, MAX_PAGES + 1):
        params = {"TM": "Bus", "cpoB": term}
        if pg > 1:
            params["Pg"] = pg
        r = session.get(f"{gallega_scraper.BASE}/productosnl.asp", params=params, timeout=90)
        r.raise_for_status()
        yield gallega_scraper.ITEM_RE.findall(r.text), r.text


def dar_session():
    s = dar_scraper.open_session()
    s.cookies.set("cantP", str(PER_PAGE), domain="www.darentucasa.com.ar", path="/")
    return s


def dar_pages(session, term):
    for pg in range(1, MAX_PAGES + 1):
        if pg == 1:
            r = session.get(f"{dar_scraper.BASE}/Productos.asp", params={"cpoBuscar": term}, timeout=90)
        else:
            r = session.get(f"{dar_scraper.BASE}/productos.asp",
                            params={"page": pg, "N1": "", "N2": "", "N3": "", "N4": ""}, timeout=90)
        r.raise_for_status()
        yield dar_scraper.ITEM_RE.findall(r.text), r.text
        if f"page={pg + 1}" not in r.text:
            return


SOURCES = {
    "lagallega": (gallega_session, gallega_pages, gallega_scraper.parse_item, r"Pr=(\d+)"),
    "dar": (dar_session, dar_pages, dar_scraper.parse_item, r"Pr=(\d+)"),
}


def crawl(chain):
    make_session, pages, parse_item, id_pattern = SOURCES[chain]
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    seen, saved, t0 = set(), 0, time.time()
    for term in TERMS:
        session = make_session()                     # sesión nueva por término: el estado de paginación es de sesión
        gained = 0
        for items, _html in pages(session, term):
            fresh = []
            for html in items:
                key = id_of(html, id_pattern)
                if key and key not in seen:
                    seen.add(key)
                    fresh.append(html)
            if not fresh:
                break
            rows = [r for r in (parse_item(h, observed_at) for h in fresh) if r]
            saved += save_rows(db, rows)[0]
            gained += len(fresh)
            db.commit()
            time.sleep(random.uniform(*PAUSE))
        print(f"[{chain}] '{term}': +{gained} productos (acumulado {len(seen)}, {time.time() - t0:.0f}s)", flush=True)
        if term != TERMS[0] and gained == 0 and term in ("i", "u"):
            break                                    # ya no suman productos
    db.close()
    print(f"[{chain}] LISTO: {saved} productos en {time.time() - t0:.0f}s", flush=True)
    return saved


def main():
    chains = [a for a in sys.argv[1:] if a in SOURCES] or list(SOURCES)
    results = {}
    for chain in chains:
        try:
            results[chain] = crawl(chain)
        except Exception as e:
            print(f"[{chain}] ERROR: {type(e).__name__}: {e}", flush=True)
            results[chain] = 0
    if any(n == 0 for n in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
