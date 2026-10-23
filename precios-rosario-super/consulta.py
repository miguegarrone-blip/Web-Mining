"""Consulta en vivo: busca un término en las 8 cadenas y devuelve precios comparables.

No escribe en precios.db (los snapshots diarios quedan intactos).

Uso por consola:
    python consulta.py cervezas
"""
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

import net

import coto_scraper
import dar_scraper
import gallega_scraper
import vtex_scraper
from matching import parse_pack, parse_size, unit_price

vtex_scraper.MAX_PAGES = 8     # consulta interactiva: hasta ~190 productos por cadena VTEX
coto_scraper.MAX_PAGES = 4
gallega_scraper.MAX_PAGES = 5
dar_scraper.MAX_PAGES = 5

CHAIN_LABELS = {"carrefour": "Carrefour", "coto": "Coto", "jumbo": "Jumbo",
                "lagallega": "La Gallega", "dar": "DAR"}
_sitemap_cache = {}


def fold(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def singular(term):
    words = []
    for w in term.split():
        words.append(w[:-2] if w.endswith(("es",)) and len(w) > 5 and w[-3] in "cnrlsz" else
                     (w[:-1] if w.endswith("s") and len(w) > 3 else w))
    return " ".join(words)


def make_row(chain, title, brand, sale, lst, promo, url):
    up, basis = unit_price(sale, title or "")
    q, u = parse_size(title or "")
    return {"chain": chain, "chain_label": CHAIN_LABELS[chain], "title": (title or "").strip(),
            "brand": brand, "price": sale, "list_price": lst if lst and lst >= sale else None,
            "promo": promo, "unit_price": up, "basis": basis, "size": f"{q:g} {u}" if q else None,
            "pack": parse_pack(title or ""), "url": url}


def from_vtex(chain, term):
    s = net.new_session()
    s.headers.update(vtex_scraper.HEADERS)
    region = vtex_scraper.get_region_id(s, chain)
    products = vtex_scraper.search(s, chain, term, region) or vtex_scraper.search_catalog(s, chain, term)
    rows = []
    for p in products:
        try:
            item = p["items"][0]
            offer = item["sellers"][0]["commertialOffer"]
        except (KeyError, IndexError):
            continue
        price = offer.get("Price")
        if not price or offer.get("AvailableQuantity", 0) <= 0:     # sin stock: VTEX devuelve precio 0
            continue
        link = p.get("link") or f"/{p.get('linkText', '')}/p"
        lst = offer.get("ListPrice") if chain in ("carrefour",) else None   # Cencosud trae ListPrice roto
        rows.append(make_row(chain, p.get("productName"), p.get("brand"), price, lst,
                             vtex_scraper.promo_text(offer), vtex_scraper.CHAINS[chain]["base"] + link))
    return rows


def from_coto(term):
    s = net.new_session()
    s.headers.update(vtex_scraper.HEADERS)
    rows = []
    for attrs in coto_scraper.search(s, term):
        r = coto_scraper.parse(attrs, "")
        if r:   # (observed_at, chain, sku, ean, brand, title, list, sale, in_stock, promo, ...)
            rows.append(make_row("coto", r[5], r[4], r[7], r[6], r[9], r[12]))
    return rows


def from_gallega(term):
    s = net.new_session()
    s.headers.update(vtex_scraper.HEADERS)
    s.get(gallega_scraper.BASE + "/", timeout=30)
    rows = []
    for html in gallega_scraper.search(s, term):
        r = gallega_scraper.parse_item(html, "")
        if r:
            rows.append(make_row("lagallega", r[5], None, r[7], r[6], r[9], r[12]))
    return rows


def from_dar(term):
    s = dar_scraper.open_session()
    items = dar_scraper.search(s, term)
    if not items and " " in term:
        for word in sorted(term.split(), key=len, reverse=True):
            items = dar_scraper.search(s, word)
            if items:
                break
    rows = []
    for html in items:
        r = dar_scraper.parse_item(html, "")
        if r:
            rows.append(make_row("dar", r[5], None, r[7], None, r[9], r[12]))
    return rows


_NOISE_WORDS = {"lata", "latas", "botella", "botellas", "pack", "packs", "sachet", "sachets", "caja", "cajas",
                "bolsa", "bolsas", "tetra", "brik", "paquete", "unidad", "unidades", "un", "u", "x", "de", "del",
                "cc", "ml", "lt", "lts", "l", "litro", "litros", "kg", "kgs", "kilo", "kilos", "g", "gr", "grs", "gm"}
_SIZE_WORD = re.compile(r"^\d+(?:[.,]\d+)?(?:cc|ml|lt|lts|l|kg|kgs|g|gr|grs|gm|u|un)?$")


def clean_term(term):
    """Deja solo las palabras que nombran el producto para pedirlas a las cadenas.

    Los buscadores de los supermercados exigen todas las palabras y son sensibles al formato:
    "473 heineken lata" no encuentra "Cerveza Heineken Lata 473cc". Se les pide "heineken" y el
    filtro tolerante (web/search.js) se encarga de afinar por tamaño y envase en el resultado.
    """
    kept = [w for w in fold(term).split() if not _SIZE_WORD.match(w) and w not in _NOISE_WORDS]
    return " ".join(kept) or term


def buscar(term):
    """Devuelve {'term', 'search_term', 'rows', 'errors', 'at'} con los productos de las 8 cadenas."""
    term = " ".join(term.split())
    original, term = term, clean_term(term)       # a las cadenas se les pide solo lo esencial
    jobs = {c: (lambda c=c: from_vtex(c, term)) for c in ("carrefour", "jumbo")}
    jobs.update({"coto": lambda: from_coto(term), "lagallega": lambda: from_gallega(term),
                 "dar": lambda: from_dar(term)})
    rows, errors = [], {}

    def run(chain):
        try:
            got = jobs[chain]()
            if not got and singular(term) != term:        # "cervezas" -> "cerveza"
                alt = singular(term)
                got = {"carrefour": lambda: from_vtex("carrefour", alt), "jumbo": lambda: from_vtex("jumbo", alt),
                       "coto": lambda: from_coto(alt), "lagallega": lambda: from_gallega(alt),
                       "dar": lambda: from_dar(alt)}[chain]()
            return chain, got, None
        except Exception as e:
            return chain, [], f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        for chain, got, err in pool.map(run, jobs):
            rows.extend(got)
            if err:
                errors[chain] = err
    return {"term": original, "search_term": term, "rows": rows, "errors": errors,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main():
    term = " ".join(sys.argv[1:]) or "cervezas"
    res = buscar(term)
    rows = sorted(res["rows"], key=lambda r: (r["unit_price"] is None, r["unit_price"] or r["price"]))
    by_chain = {}
    for r in rows:
        by_chain[r["chain_label"]] = by_chain.get(r["chain_label"], 0) + 1
    print(f"'{res['term']}': {len(rows)} productos  {by_chain}")
    if res["errors"]:
        print("Errores:", res["errors"])
    for r in rows[:25]:
        up = f"${r['unit_price']:,.0f} {r['basis']}" if r["unit_price"] else "-"
        print(f"  {r['chain_label']:<11}{r['price']:>9,.0f}  {up:>14}  {r['title'][:60]}"
              + (f"  [{r['promo'][:30]}]" if r["promo"] else ""))


if __name__ == "__main__":
    main()
