"""Scraper Cadena DAR (darentucasa.com.ar, ASP clásico) -> misma tabla que vtex_scraper.

Uso:
    python dar_scraper.py              # canasta por defecto
    python dar_scraper.py "leche"      # una búsqueda

No requiere cuenta: la sesión de invitado se abre con Login.asp -> index.asp, y recién entonces
Productos.asp?cpoBuscar=<término> devuelve resultados (sin ese paso redirige a login).
DAR no publica EAN (usa un código interno de 13 dígitos), así que el matching con otras cadenas
tiene que ser por texto/marca/gramaje. Solo muestra un precio por producto (sin precio de lista);
las ofertas vienen marcadas con la etiqueta "Oferta".
"""
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

from vtex_scraper import BASKET, DB_PATH, HEADERS, PAUSE, SCHEMA
import net
from store import save_rows

BASE = "https://www.darentucasa.com.ar"
CHAIN = "dar"
MAX_PAGES = 5

ITEM_RE = re.compile(r'<li class="cuadProd">.*?</li>', re.S)
PRICE_RE = re.compile(r"\$([\d.]+),(?:<b>)?(\d{2})")


def open_session():
    s = net.new_session()
    s.headers.update(HEADERS)
    s.get(BASE + "/Login.asp", timeout=30)
    s.get(BASE + "/index.asp", timeout=30)   # abre la sesión de invitado
    return s


def parse_item(html, observed_at):
    code = re.search(r"Detalle\.asp\?Pr=(\d+)", html)
    desc = re.search(r'class="desc[^"]*">([^<]+)', html)
    price = PRICE_RE.search(html)
    if not (code and desc and price):
        return None
    amount = float(price.group(1).replace(".", "") + "." + price.group(2))
    offer = "OferProd" in html
    return (observed_at, CHAIN, code.group(1), None, None, desc.group(1).strip(),
            None, amount, 1, "Oferta" if offer else None, None, None,
            f"{BASE}/Detalle.asp?Pr={code.group(1)}",
            json.dumps({"html": re.sub(r"\s+", " ", html)[:1500]}, ensure_ascii=False))


def search(session, query):
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if page == 1:
            r = session.get(f"{BASE}/Productos.asp", params={"cpoBuscar": query}, timeout=30)
        else:
            r = session.get(f"{BASE}/productos.asp",
                            params={"page": page, "N1": "", "N2": "", "N3": "", "N4": ""}, timeout=30)
        r.raise_for_status()
        items = ITEM_RE.findall(r.text)
        new = [i for i in items if re.search(r"Pr=(\d+)", i).group(1) not in seen]
        if not new:
            break
        seen.update(re.search(r"Pr=(\d+)", i).group(1) for i in new)
        out.extend(new)
        if f"page={page + 1}" not in r.text:   # no hay link a la página siguiente
            break
        time.sleep(random.uniform(*PAUSE))
    return out


def main():
    queries = [sys.argv[1]] if len(sys.argv) > 1 else BASKET
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    session = open_session()
    print(f"[{CHAIN}]")
    for q in queries:
        try:
            items = search(session, q)
            if not items and " " in q:   # el buscador de DAR es literal: probar palabra por palabra
                for word in sorted(q.split(), key=len, reverse=True):
                    items = search(session, word)
                    if items:
                        print(f"    (sin resultados para {q!r}; se usó {word!r})")
                        break
        except Exception as e:
            print(f"  {q!r}: ERROR {e}")
            continue
        rows = [r for r in (parse_item(i, observed_at) for i in items) if r]
        save_rows(db, rows)
        db.commit()
        print(f"  {q!r}: {len(rows)} productos")
        time.sleep(random.uniform(*PAUSE))
    db.close()


if __name__ == "__main__":
    main()
