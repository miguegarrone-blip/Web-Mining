"""Prototipo: scraper VTEX (Carrefour, Vea) -> SQLite.

Uso:
    python vtex_scraper.py                    # canasta por defecto, todas las cadenas
    python vtex_scraper.py carrefour "leche"  # una cadena, una búsqueda
"""
import json
import os
import random
import re
import sqlite3
import sys
import time
from urllib.parse import quote
from datetime import datetime, timezone
from pathlib import Path

import requests

import net
from store import save_rows

DB_PATH = Path(os.environ.get("PRECIOS_DB") or Path(__file__).with_name("precios.db"))
PAGE_SIZE = 24          # tope de intelligent-search
PAUSE = (1.0, 2.0)      # segundos entre requests (jitter)
MAX_PAGES = 5           # por búsqueda, para el prototipo

CHAINS = {
    "carrefour": {"base": "https://www.carrefour.com.ar", "postal_code": "2013"},  # Hiper Rosario Pueyrredón
    # Jumbo (Cencosud): endpoint de regiones roto, se scrapea a nivel cadena. Vea y Disco se descartaron.
    "jumbo": {"base": "https://www.jumbo.com.ar", "postal_code": None},
}

BASKET = ["leche entera", "aceite de girasol", "arroz", "fideos", "yerba mate",
          "azucar", "harina de trigo", "gaseosa cola", "cafe molido", "huevos",
          # ampliación: el catálogo web cubre más categorías (bebidas, lácteos, limpieza, perfumería...)
          "cerveza", "agua mineral", "jugo", "vino", "fernet", "yogur", "queso cremoso", "manteca",
          "galletitas", "papas fritas", "detergente", "lavandina", "papel higienico", "shampoo",
          "jabon de tocador", "desodorante", "atun", "mayonesa"]

HEADERS = {"User-Agent": "Mozilla/5.0 (monitor-precios-rosario; uso analitico)",
           "Accept-Language": "es-AR,es;q=0.9"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_observation (
    obs_id INTEGER PRIMARY KEY,
    observed_at TEXT NOT NULL,
    chain TEXT NOT NULL,
    external_sku TEXT NOT NULL,
    ean TEXT,
    brand TEXT,
    title TEXT,
    list_price REAL,
    sale_price REAL,
    in_stock INTEGER,
    promo TEXT,
    measurement_unit TEXT,
    unit_multiplier REAL,
    url TEXT,
    raw_payload TEXT
);
CREATE INDEX IF NOT EXISTS ix_obs_sku ON price_observation (chain, external_sku, observed_at);
CREATE INDEX IF NOT EXISTS ix_obs_ean ON price_observation (ean, observed_at);
CREATE INDEX IF NOT EXISTS ix_obs_chain_ts ON price_observation (chain, observed_at);
"""


def get_region_id(session, chain):
    cfg = CHAINS[chain]
    if not cfg["postal_code"]:
        return None
    r = session.get(f"{cfg['base']}/api/checkout/pub/regions",
                    params={"country": "ARG", "postalCode": cfg["postal_code"]}, timeout=30)
    if r.ok:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]["id"]
    return None


def search(session, chain, query, region_id):
    """Pagina intelligent-search y devuelve la lista de productos."""
    base = CHAINS[chain]["base"]
    out = []
    for page in range(1, MAX_PAGES + 1):
        params = {"query": query, "count": PAGE_SIZE, "page": page}
        if region_id:
            params["regionId"] = region_id
        r = session.get(f"{base}/api/io/_v/api/intelligent-search/product_search",
                        params=params, timeout=30)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 + random.random() * 5)
            continue
        r.raise_for_status()
        products = r.json().get("products", [])
        out.extend(products)
        if len(products) < PAGE_SIZE:
            break
        time.sleep(random.uniform(*PAUSE))
    return out


def search_catalog(session, chain, query):
    """Fallback: API clásica (ft=), más tolerante que intelligent-search en algunos términos."""
    base = CHAINS[chain]["base"]
    out = []
    for start in range(0, MAX_PAGES * PAGE_SIZE, 50):
        # %20 a mano: con "+" (lo que genera requests) este endpoint devuelve vacío
        url = (f"{base}/api/catalog_system/pub/products/search"
               f"?ft={quote(query)}&_from={start}&_to={start + 49}")
        r = session.get(url, timeout=30)
        if r.status_code not in (200, 206) or not r.content:
            break
        products = r.json()
        out.extend(products)
        if len(products) < 50:
            break
        time.sleep(random.uniform(*PAUSE))
    return out


def promo_text(offer):
    teasers = offer.get("teasers") or offer.get("Teasers") or []
    highlights = offer.get("discountHighlights") or offer.get("DiscountHighLight") or []
    parts = [t.get("name", "") for t in teasers] + [t.get("name", "") for t in highlights]
    return " | ".join(p for p in parts if p) or None


def parse(chain, product, observed_at):
    item = product["items"][0]
    sellers = item.get("sellers") or []
    offer = sellers[0]["commertialOffer"] if sellers else {}
    link = product.get("link") or f"/{product.get('linkText', '')}/p"
    return (
        observed_at, chain, item.get("itemId"), item.get("ean") or None,
        product.get("brand"), product.get("productName"),
        offer.get("ListPrice"), offer.get("Price"),
        1 if offer.get("AvailableQuantity", 0) > 0 else 0,
        promo_text(offer),
        item.get("measurementUnit"), item.get("unitMultiplier"),
        CHAINS[chain]["base"] + link,
        json.dumps({"productId": product.get("productId"), "cat": (product.get("categories") or [None])[0], "offer": offer}, ensure_ascii=False),
    )


def main():
    chains = [sys.argv[1]] if len(sys.argv) > 1 else list(CHAINS)
    queries = [sys.argv[2]] if len(sys.argv) > 2 else BASKET
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    session = net.new_session()
    session.headers.update(HEADERS)

    for chain in chains:
        region_id = get_region_id(session, chain)
        print(f"[{chain}] regionId={'sí' if region_id else 'no'}")
        for q in queries:
            try:
                products = search(session, chain, q, region_id)
                if not products:
                    products = search_catalog(session, chain, q)
            except Exception as e:  # una búsqueda rota no frena el resto
                print(f"  {q!r}: ERROR {e}")
                continue
            rows = []
            for p in products:
                try:
                    rows.append(parse(chain, p, observed_at))
                except (KeyError, IndexError):
                    continue
            save_rows(db, rows)
            db.commit()
            print(f"  {q!r}: {len(rows)} productos")
            time.sleep(random.uniform(*PAUSE))
    db.close()


if __name__ == "__main__":
    main()
