"""Scraper Coto Digital (Oracle ATG/Endeca, JSON) -> misma tabla que vtex_scraper.

Uso:
    python coto_scraper.py              # canasta por defecto
    python coto_scraper.py "leche"      # una búsqueda

Se usa la ruta JSON del sitio: /sitios/cdigi/browse?Ntt=<término>&Nrpp=<n>&No=<offset>&format=json
Precio base = lista de precios por defecto (priceList200). Coto también publica listas por
sucursal (sku.dtoPrice0NN); se guardan en raw_payload para analizarlas más adelante.
"""
import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from vtex_scraper import BASKET, DB_PATH, HEADERS, PAUSE, SCHEMA
import net
from store import save_rows

BASE = "https://www.coto.com.ar"
CHAIN = "coto"
PAGE_SIZE = 50
MAX_PAGES = 3


def first(attrs, key):
    v = attrs.get(key)
    return v[0] if v else None


def json_attr(attrs, key):
    raw = first(attrs, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def collect_products(node, found):
    """Recorre el árbol y junta registros hoja que traen eanPrincipal."""
    if isinstance(node, dict):
        attrs = node.get("attributes")
        if isinstance(attrs, dict) and "product.eanPrincipal" in attrs:
            found[first(attrs, "product.repositoryId")] = attrs
        for v in node.values():
            collect_products(v, found)
    elif isinstance(node, list):
        for v in node:
            collect_products(v, found)


def first_discount(attrs):
    """Primer descuento directo vigente: (texto, precio efectivo por unidad) o (None, None)."""
    for d in json_attr(attrs, "product.dtoDescuentos") or []:
        try:
            eff = float(d.get("precioDesc"))
        except (TypeError, ValueError):
            continue
        label = (d.get("textoDescuento") or "").strip() or "Dto"
        extra = (d.get("precioDescTextoAdicional") or "").strip()
        return (f"{label} {extra}".strip(), eff)
    return None, None


def payment_promos(attrs):
    out = []
    for d in json_attr(attrs, "product.dtoDescuentosMediosPago") or []:
        out.append(f"{d.get('cantidadCuotas', '?')} cuotas de {d.get('precioCuota', '?')}")
    return out


def parse(attrs, observed_at):
    # OJO: sku.dtoPrice.precio no es confiable (suele venir al doble de la lista cuando hay oferta).
    # El precio regular es precioLista y el efectivo por unidad con promo es dtoDescuentos.precioDesc.
    price = json_attr(attrs, "sku.dtoPrice") or {}
    list_price = price.get("precioLista")
    promo, effective = first_discount(attrs)
    sale = effective if effective is not None else list_price
    if not sale:
        return None
    pay = payment_promos(attrs)
    if pay:
        promo = " | ".join(filter(None, [promo, "Pago: " + "; ".join(pay)]))
    sku = first(attrs, "sku.repositoryId")
    store_prices = {k: v[0] for k, v in attrs.items() if k.startswith("sku.dtoPrice0")}
    return (observed_at, CHAIN, sku, first(attrs, "product.eanPrincipal"),
            first(attrs, "product.brand"), first(attrs, "product.displayName"),
            list_price, sale, 1, promo,
            first(attrs, "sku.unit_of_measure"), None,
            f"{BASE}/sitios/cdigi/productos?searchTerm=" + quote(first(attrs, "product.displayName") or ""),
            json.dumps({"price": price, "store_prices": store_prices,
                        "dtoDescuentos": json_attr(attrs, "product.dtoDescuentos"),
                        "dtoDescuentosMediosPago": json_attr(attrs, "product.dtoDescuentosMediosPago"),
                        "rubro": first(attrs, "product.LDEPAR"), "familia": first(attrs, "product.FAMILIA"),
                        "pesable": first(attrs, "product.unidades.esPesable"),
                        "formato": first(attrs, "product.cFormato")}, ensure_ascii=False))


def search(session, query):
    found = {}
    for page in range(MAX_PAGES):
        url = (f"{BASE}/sitios/cdigi/browse?Ntt={quote(query)}"
               f"&Nrpp={PAGE_SIZE}&No={page * PAGE_SIZE}&format=json")
        r = session.get(url, timeout=60)
        r.raise_for_status()
        before = len(found)
        collect_products(r.json(), found)
        if len(found) - before < PAGE_SIZE // 2:   # pocas novedades: última página
            break
        time.sleep(random.uniform(*PAUSE))
    return list(found.values())


def main():
    queries = [sys.argv[1]] if len(sys.argv) > 1 else BASKET
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    session = net.new_session()
    session.headers.update(HEADERS)
    print(f"[{CHAIN}]")
    for q in queries:
        try:
            products = search(session, q)
        except Exception as e:
            print(f"  {q!r}: ERROR {e}")
            continue
        rows = [r for r in (parse(a, observed_at) for a in products) if r]
        save_rows(db, rows)
        db.commit()
        print(f"  {q!r}: {len(rows)} productos")
        time.sleep(random.uniform(*PAUSE))
    db.close()


if __name__ == "__main__":
    main()
