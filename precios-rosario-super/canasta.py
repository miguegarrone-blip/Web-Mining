"""Costo de tu canasta en cada cadena.

Tu canasta está en canasta.json y se arma desde el panel (botón "+ canasta" al buscar un producto).
Cada producto puede definirse de dos formas:
  - por título (lo que agrega el panel): "title" + "size" + "pack". En cada cadena se elige el más barato
    cuyo título se parezca al elegido (misma marca/variante) y tenga el mismo tamaño y pack.
  - por reglas manuales: "require" / "any" / "exclude" / "size" / "pack" (los 5 productos de ejemplo).

Uso:
    python canasta.py            # busca, guarda y muestra
    python canasta.py --export   # además escribe canasta_resultado.json y 'Mi canasta Rosario.html'
    python canasta.py --html-only # rehace el HTML con el último resultado, sin buscar
"""
import json
import os
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import consulta
from matching import parse_pack, parse_size, similarity, tokens

HERE = Path(__file__).parent
DB_PATH = Path(os.environ.get("PRECIOS_DB") or HERE / "precios.db")
CONFIG_PATH = Path(os.environ.get("CANASTA_JSON") or HERE / "canasta.json")
SIZE_TOLERANCE = 0.02
SIMILARITY_MIN = 0.45          # parecido mínimo de texto para considerar "el mismo producto"
_config_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS canasta_precios (
    run_at TEXT, item TEXT, chain TEXT, title TEXT, price REAL, list_price REAL, promo TEXT, url TEXT,
    PRIMARY KEY (run_at, item, chain)
)"""
HELP = ("Cada producto: name, query (qué se busca) y size ([cantidad, 'g' o 'ml']), pack (1 por defecto). "
        "Definido por 'title' (parecido de texto) o por reglas 'require' / 'any' / 'exclude'.")


# --- Configuración -------------------------------------------------------------------------------

def load_config():
    with _config_lock:
        if not CONFIG_PATH.exists():                 # primera vez: se parte del ejemplo (canasta.json es personal)
            example = HERE / "canasta.ejemplo.json"
            if example.exists():
                CONFIG_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config):
    with _config_lock:
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)


def norm(text):
    """Minúsculas, sin tildes ni signos, con espacios simples (para comparar marcas y frases)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", consulta.fold(text)).split())


_brand_vocab = []


def brand_vocab():
    """Marcas ya relevadas en la base (las cadenas con EAN las informan), de la más larga a la más corta."""
    if not _brand_vocab:
        try:
            db = sqlite3.connect(DB_PATH)
            names = {norm(b) for (b,) in db.execute(
                "SELECT DISTINCT brand FROM price_observation WHERE brand IS NOT NULL AND brand != ''")}
            db.close()
        except sqlite3.Error:
            names = set()
        _brand_vocab.extend(sorted((n for n in names if len(n) > 2), key=len, reverse=True))
    return _brand_vocab


def detect_brand(title):
    padded = f" {norm(title)} "
    return next((b for b in brand_vocab() if f" {b} " in padded), None)


def sin_phrases(title):
    """Frases tipo 'sin palo', 'sin tacc', 'sin azucar': si difieren, son productos distintos."""
    return set(re.findall(r"\bsin \w+", norm(title)))


def spec_from_title(title, brand=None):
    """Arma el producto de la canasta a partir de un título elegido en el panel."""
    qty, unit = parse_size(title)
    brand = norm(brand) if brand else detect_brand(title)
    words = [w for w in tokens(title) if not brand or w not in brand.split()]
    return {"name": " ".join(title.split()).strip(), "title": title, "brand": brand,
            "query": " ".join(words[:2] + ([brand] if brand else [])) or title,   # pocas palabras: los buscadores exigen todas
            "size": [qty, unit] if qty else None, "pack": parse_pack(title)}


def add_item(title, brand=None):
    """Agrega un producto (sin duplicar). Devuelve (item, agregado)."""
    config = load_config()
    key = consulta.fold(title).strip()
    for it in config["items"]:
        if consulta.fold(it.get("title") or it["name"]).strip() == key:
            return it, False
    item = spec_from_title(title, brand)
    config["items"].append(item)
    config["_ayuda"] = HELP
    save_config(config)
    return item, True


def remove_item(name):
    config = load_config()
    before = len(config["items"])
    config["items"] = [it for it in config["items"] if it["name"] != name]
    save_config(config)
    return before - len(config["items"])


def clear_items():
    config = load_config()
    config["items"] = []
    save_config(config)


# --- Cálculo -------------------------------------------------------------------------------------

def matches(row, item):
    size_ok = True
    if item.get("size"):
        want_qty, want_unit = item["size"]
        qty, unit = parse_size(row["title"])
        size_ok = bool(qty) and unit == want_unit and abs(qty - want_qty) <= want_qty * SIZE_TOLERANCE
    if not size_ok or parse_pack(row["title"]) != item.get("pack", 1):
        return False
    if item.get("title"):
        if item.get("brand") and f" {item['brand']} " not in f" {norm(row['title'])} ":
            return False          # otra marca: no es el producto elegido
        if sin_phrases(item["title"]) != sin_phrases(row["title"]):
            return False          # "con palo" vs "sin palo", "sin tacc", etc.
        return similarity(tokens(item["title"]), tokens(row["title"])) >= SIMILARITY_MIN
    title = consulta.fold(row["title"])
    if not all(consulta.fold(w) in title for w in item.get("require", [])):
        return False
    if item.get("any") and not any(consulta.fold(w) in title for w in item["any"]):
        return False
    return not any(consulta.fold(w) in title for w in item.get("exclude", []))


def resolve(item):
    res = consulta.buscar(item["query"])
    best = {}
    for r in res["rows"]:
        if matches(r, item) and (r["chain"] not in best or r["price"] < best[r["chain"]]["price"]):
            best[r["chain"]] = r
    return best, res["errors"]


def calcular(items):
    """Busca todos los productos (3 en paralelo) y devuelve el resultado listo para el tablero."""
    result = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "chains": list(consulta.CHAIN_LABELS.values()), "items": []}
    with ThreadPoolExecutor(max_workers=3) as pool:
        resolved = list(pool.map(resolve, items))
    for item, (best, errors) in zip(items, resolved):
        entry = {"name": item["name"], "options": {}, "errors": list(errors)}
        for r in best.values():
            entry["options"][r["chain_label"]] = {"title": r["title"], "price": r["price"],
                                                  "list_price": r["list_price"], "promo": r["promo"], "url": r["url"]}
        result["items"].append(entry)
    return result


# --- Salida --------------------------------------------------------------------------------------

def build_html(result):
    """HTML autónomo (se abre con doble clic) a partir de templates/canasta.html."""
    tpl = (HERE / "templates" / "canasta.html").read_text(encoding="utf-8")
    data = json.dumps(result, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    head, body = tpl.replace("__DATA__", data).split("</style>", 1)
    return ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + head + "</style>\n<style>body{margin:0}</style></head><body>" + body + "</body></html>")


def write_html(result):
    out = HERE / "Mi canasta Rosario.html"
    out.write_text(build_html(result), encoding="utf-8")
    return out


def main():
    if "--html-only" in sys.argv:
        print("HTML generado:", write_html(json.loads((HERE / "canasta_resultado.json").read_text(encoding="utf-8"))))
        return
    items = load_config()["items"]
    if not items:
        print("La canasta está vacía. Agregá productos desde el panel (botón '+ canasta').")
        return
    result = calcular(items)
    db = sqlite3.connect(DB_PATH)
    db.execute(SCHEMA)
    for entry in result["items"]:
        found = sorted(entry["options"].items(), key=lambda kv: kv[1]["price"])
        print(f"\n{entry['name']}  ({len(found)}/8 cadenas" +
              (f", sin respuesta: {entry['errors']}" if entry["errors"] else "") + ")")
        for label, o in found:
            print(f"  {label:<11}${o['price']:>8,.0f}  {o['title'][:62]}")
            db.execute("INSERT OR REPLACE INTO canasta_precios VALUES (?,?,?,?,?,?,?,?)",
                       (result["run_at"], entry["name"], label, o["title"], o["price"], o["list_price"], o["promo"], o["url"]))
    db.commit()
    db.close()

    n_items = len(result["items"])
    totals = {}
    for label in result["chains"]:
        got = [e["options"][label]["price"] for e in result["items"] if label in e["options"]]
        totals[label] = (sum(got), len(got))
    print("\nTotal de la canasta por cadena:")
    for label, (total, n) in sorted(totals.items(), key=lambda kv: (kv[1][1] < n_items, kv[1][0])):
        print(f"  {label:<11}${total:>9,.0f}  ({n}/{n_items} productos)")
    if "--export" in sys.argv:
        (HERE / "canasta_resultado.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print("HTML generado:", write_html(result))


if __name__ == "__main__":
    main()
