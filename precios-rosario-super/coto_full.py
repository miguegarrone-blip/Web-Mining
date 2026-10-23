"""Relevamiento COMPLETO de Coto Digital: recorre todos los rubros de supermercado.

Los rubros se leen de la propia tienda (refinamientos del listado), así que no dependen de códigos fijos.
Se excluyen Textil, Hogar, Electro y Aire Libre (no son de supermercado). Mismo formato que coto_scraper.py.

Uso:
    python coto_full.py                  # todos los rubros (unos 15.500 productos, ~5 min)
    python coto_full.py --only Congelados   # un rubro (prueba rápida)
"""
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import net
from coto_scraper import BASE, collect_products, parse
from store import save_rows
from vtex_scraper import DB_PATH, SCHEMA

LIST_URL = f"{BASE}/sitios/cdigi/browse"
PAGE = 50
PAUSE = (0.2, 0.5)
WANTED = ("almacen", "bebidas", "frescos", "congelados", "limpieza", "perfumeria")


def fold(text):
    import unicodedata
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def find_all(node, key, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                out.append(v)
            find_all(v, key, out)
    elif isinstance(node, list):
        for v in node:
            find_all(v, key, out)


def rubros(session):
    """{nombre: (código N, cantidad)} de los rubros de supermercado, leídos del listado."""
    data = session.get(LIST_URL, params={"Nrpp": 1, "No": 0, "format": "json"}, timeout=90).json()
    groups = []
    find_all(data, "refinements", groups)
    found = {}
    for group in groups:
        for ref in group if isinstance(group, list) else []:
            if not isinstance(ref, dict):
                continue
            name, state = ref.get("label"), ref.get("navigationState") or ""
            m = re.search(r"/N-([a-z0-9]+)", state)
            if name and m and fold(name) in WANTED and name not in found:
                found[name] = (m.group(1), ref.get("count"))
    return found


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    session = net.new_session()
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.executescript(SCHEMA)
    todo = rubros(session)
    if only:
        todo = {k: v for k, v in todo.items() if fold(k) == fold(only)}
    if not todo:
        print("[coto] no se encontraron los rubros: la tienda cambió su listado", flush=True)
        sys.exit(1)
    print(f"[coto] rubros: " + ", ".join(f"{k} ({v[1]})" for k, v in todo.items()), flush=True)
    seen, saved, errors, t0 = set(), 0, [], time.time()
    for name, (code, count) in todo.items():
        start, n_rubro = 0, 0
        while True:
            try:
                data = session.get(LIST_URL, params={"N": code, "Nrpp": PAGE, "No": start, "format": "json"}, timeout=90).json()
            except Exception as e:                     # una página rota no frena el rubro
                errors.append(f"{name} No={start}: {str(e)[:60]}")
                start += PAGE
                if start > (count or 0) + PAGE:
                    break
                continue
            page = {}
            collect_products(data, page)
            rows = []
            for attrs in page.values():
                row = parse(attrs, observed_at)
                if row and (row[2], row[5]) not in seen:
                    seen.add((row[2], row[5]))
                    rows.append(row)
            if rows:
                n = save_rows(db, rows)[0]
                saved += n
                n_rubro += n
                db.commit()
            start += PAGE
            if len(page) < PAGE or (count and start >= count):
                break
            time.sleep(random.uniform(*PAUSE))
        print(f"[coto] {name}: {n_rubro} productos ({time.time() - t0:.0f}s)", flush=True)
    db.close()
    print(f"[coto] LISTO: {saved} productos en {time.time() - t0:.0f}s, {len(errors)} páginas con error", flush=True)
    for e in errors[:5]:
        print("    !", e)
    if saved == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
