"""Relevamiento COMPLETO de las tiendas VTEX (Carrefour y Jumbo): recorre todas las categorías hoja.

A diferencia de vtex_scraper.py (28 búsquedas por palabra, tope de unos cientos de productos cada una), acá se
baja el árbol de categorías de la tienda y se pagina cada categoría hasta el final, así que el resultado es el
catálogo entero. Guarda en price_observation con el mismo formato (un snapshot por cadena y corrida).

Uso:
    python vtex_full.py                  # carrefour y jumbo, en paralelo
    python vtex_full.py jumbo            # una sola
    python vtex_full.py carrefour --max-leaves 5     # prueba rápida
"""
import random
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import net
from store import save_rows
from vtex_scraper import CHAINS, DB_PATH, SCHEMA, parse

PAGE = 50
MAX_OFFSET = 2450            # VTEX no entrega más allá de 2500 resultados por consulta
PAUSE = (0.2, 0.6)           # el servidor ya tarda ~1.5 s por pedido
# Rubros que no son de supermercado (se comparan por nombre, sin tildes ni mayúsculas)
SKIP_ROOTS = ("test category", "electro", "tecnologia", "hogar", "textil", "indumentaria", "deporte",
              "jugueteria", "juguetes", "automotor", "libreria", "bazar", "muebles", "aire libre", "colchones")


def fold(text):
    import unicodedata
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def leaves(node, path=()):
    here = path + (node["id"],)
    if not node.get("children"):
        yield node["name"], here
    for child in node.get("children", []):
        yield from leaves(child, here)


def category_paths(session, base):
    tree = session.get(f"{base}/api/catalog_system/pub/category/tree/3", timeout=60).json()
    out = []
    for root in tree:
        if any(skip in fold(root["name"]) for skip in SKIP_ROOTS):
            continue
        out.extend(leaves(root))
    return out


WORKERS = 4                  # categorías que se piden a la vez por tienda


def fetch_leaf(chain, base, name, path, observed_at):
    """Baja todas las páginas de una categoría hoja y devuelve las filas (no escribe en la base)."""
    session = net.new_session()
    fq = "C:/" + "/".join(map(str, path)) + "/"
    rows, start = [], 0
    while start <= MAX_OFFSET:
        r = session.get(f"{base}/api/catalog_system/pub/products/search",
                        params={"fq": fq, "_from": start, "_to": start + PAGE - 1}, timeout=60)
        if r.status_code not in (200, 206):
            raise RuntimeError(f"HTTP {r.status_code}")
        products = r.json()
        for p in products:
            try:
                rows.append(parse(chain, p, observed_at))
            except (KeyError, IndexError):
                continue
        if len(products) < PAGE:
            break
        start += PAGE
        time.sleep(random.uniform(*PAUSE))
    return rows


def crawl(chain, max_leaves=None):
    base = CHAINS[chain]["base"]
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    cats = category_paths(net.new_session(), base)
    if max_leaves:
        cats = random.Random(1).sample(cats, min(max_leaves, len(cats)))
    seen, saved, failed, done, t0 = set(), 0, [], 0, time.time()
    print(f"[{chain}] {len(cats)} categorías hoja ({WORKERS} en paralelo)", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_leaf, chain, base, name, path, observed_at): name for name, path in cats}
        for fut in as_completed(futures):             # el guardado ocurre en este hilo: una sola escritura a la vez
            done += 1
            try:
                fresh = []
                for row in fut.result():
                    key = (row[2], row[5])             # sku + título: un producto está en varias categorías
                    if key not in seen:
                        seen.add(key)
                        fresh.append(row)
                if fresh:
                    saved += save_rows(db, fresh)[0]
                    db.commit()
            except Exception as e:                     # una categoría rota no frena el resto
                failed.append((futures[fut], str(e)[:80]))
            if done % 40 == 0:
                print(f"[{chain}] {done}/{len(cats)} categorías, {saved} productos, {time.time() - t0:.0f}s", flush=True)
    db.close()
    print(f"[{chain}] LISTO: {saved} productos en {time.time() - t0:.0f}s, {len(failed)} categorías con error", flush=True)
    for name, err in failed[:5]:
        print(f"    ! {name}: {err}")
    return chain, saved, len(failed)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chains = args or list(CHAINS)
    max_leaves = None
    if "--max-leaves" in sys.argv:
        max_leaves = int(sys.argv[sys.argv.index("--max-leaves") + 1])
        chains = [c for c in chains if c in CHAINS]
    with ThreadPoolExecutor(max_workers=len(chains)) as pool:
        results = list(pool.map(lambda c: crawl(c, max_leaves), chains))
    if any(saved == 0 for _, saved, _ in results):
        sys.exit(1)             # una cadena sin productos es una falla: que run_all lo informe


if __name__ == "__main__":
    main()
