"""Scraper La Gallega (ASP clásico, HTML server-rendered) -> misma tabla que vtex_scraper.

Uso:
    python gallega_scraper.py                 # canasta por defecto
    python gallega_scraper.py "leche"         # una búsqueda

Notas: el precio es idéntico entre sucursales (verificado en Dorrego, Hipermercado y 3 Vías),
así que se modela a nivel cadena. El EAN viene en el alt de la imagen del producto.
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

BASE = "https://www.lagallega.com.ar"
PAGE_SIZE = 20
MAX_PAGES = 5
CHAIN = "lagallega"

ITEM_RE = re.compile(r'<li class="cuadProd">.*?</li>', re.S)
PRICE_RE = re.compile(r"\$([\d.]+,\d+)")


def money(txt):
    return float(txt.replace(".", "").replace(",", "."))


def parse_item(html, observed_at):
    ean = re.search(r'alt="(\d{8,14}) - ', html)
    pr = re.search(r"productosdet\.asp\?Pr=(\d+)", html)
    desc = re.search(r'class="desc">([^<]+)', html)
    if not (pr and desc):
        return None
    old = re.search(r"class='izqdes'>\$([\d.]+,\d+)", html)
    new = re.search(r"class='der'><b>\$([\d.]+,\d+)", html)
    plain = re.search(r"class='izq'>\$([\d.]+,\d+)", html)
    on_offer = "OferProd" in html and new is not None
    if on_offer:
        list_price, sale_price = money(old.group(1)) if old else None, money(new.group(1))
    else:
        amount = plain or (PRICE_RE.search(html))
        if not amount:
            return None
        list_price = sale_price = money(amount.group(1) if plain else amount.group(1))
    return (observed_at, CHAIN, pr.group(1), ean.group(1) if ean else None, None,
            desc.group(1).strip(), list_price, sale_price, 1,
            "Oferta" if on_offer else None, None, None,
            f"{BASE}/productosdet.asp?Pr={pr.group(1)}",
            json.dumps({"html": re.sub(r"\s+", " ", html)[:1500]}, ensure_ascii=False))


def search(session, query):
    out, seen_first = [], None
    for page in range(1, MAX_PAGES + 1):
        params = {"TM": "Bus", "cpoB": query}
        if page > 1:
            params["Pg"] = page
        r = session.get(f"{BASE}/productosnl.asp", params=params, timeout=30)
        r.raise_for_status()
        items = ITEM_RE.findall(r.text)
        if not items:
            break
        first = re.search(r"Pr=(\d+)", items[0]).group(1)
        if first == seen_first:   # la página repite: se acabaron los resultados
            break
        seen_first = first if page == 1 else seen_first
        out.extend(items)
        if len(items) < PAGE_SIZE:
            break
        time.sleep(random.uniform(*PAUSE))
    return out


def main():
    queries = [sys.argv[1]] if len(sys.argv) > 1 else BASKET
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    session = net.new_session()
    session.headers.update(HEADERS)
    session.get(BASE + "/", timeout=30)   # abre sesión ASP
    print(f"[{CHAIN}]")
    for q in queries:
        try:
            items = search(session, q)
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
