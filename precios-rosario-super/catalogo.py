"""Genera el catálogo que alimenta la interfaz web (web/data/catalogo.js y catalogo.json).

Cada producto agrupa las ofertas de todas las cadenas donde está (por EAN, o por matching de texto
en DAR), con categoría, precio por kg/litro, promoción interpretada, indicador de
anomalía e historial de precios. El contrato completo está en web/API_CONTRATO.md.

Uso:
    python catalogo.py
"""
import json
import os
import re
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import anomalies
import consulta
from matching import parse_pack, parse_size, unit_price

from chains import SQL_IN

HERE = Path(__file__).parent
DB_PATH = Path(os.environ.get("PRECIOS_DB") or HERE / "precios.db")
OUT_DIR = HERE / "web" / "data"
CHAIN_ORDER = ["carrefour", "coto", "jumbo", "lagallega", "dar"]   # preferencia para el nombre
HISTORY_DAYS = 30

# Categorías por palabras del título (en orden: gana la primera que coincide)
CATEGORY_RULES = [
    ("Galletitas y snacks", r"galletit|alfajor|snack|papas fritas|chocolate|golosina|caramelo|chicle|bizcocho|obleas?|turron|barra de cereal|tostada|mantecol"),
    ("Bebidas", r"cerveza|gaseosa|agua mineral|agua saborizada|agua con gas|\bjugo|\bvino|fernet|aperitivo|whisky|\bgin\b|vodka|champagne|espumante|energizante|isotonic|\bsoda\b|sidra|licor|tonica|bebida|coca cola|pepsi|sprite|fanta|seven up|manaos|gatorade|powerade|levite|cunnington|speed|schweppes"),
    ("Lácteos y huevos", r"\bleche|yogur|queso|manteca|crema de leche|dulce de leche|ricota|huevo|margarina|postre|\bflan\b|crema"),
    ("Frutas y verduras", r"fruta|verdura|hortaliza|verd"),
    ("Mascotas", r"mascota|perro|gato|alimento balanceado|arena sanitaria"),
    ("Almacén", r"aceite|arroz|fideo|tallarin|spaghetti|espagueti|harina|azucar|edulcor|yerb|caf+e|nescafe|dolca|cappuccino|\bte\b|mate cocido|\bsal\b|vinagre|conserva|atun|salsa|tomate|pure|lenteja|garbanzo|poroto|polenta|premezcla|cacao|mermelada|\bmiel\b|aderezo|mayonesa|mostaza|ketchup|cereal|avena|pan rallado|rebozador|caldo|sopa|legumbre"),
    ("Panificados", r"\bpan\b|facturas|pan lactal|tapas para"),
    ("Limpieza", r"lavandina|detergente|jabon en polvo|suavizante|limpiador|desinfectante|esponja|lavavajilla|insecticida|trapo|papel higienico|rollo de cocina|bolsas? de residuo|desodorante de ambiente"),
    ("Perfumería", r"shampoo|acondicionador|desodorante|\bjabon|pasta dental|cepillo|crema dental|toallita|panal|protector solar|afeitar|enjuague"),
    ("Carnes y fiambres", r"\bcarne|pollo|milanesa|\bjamon|salame|hamburguesa|chorizo|salchicha|fiambre|cerdo|pescado|bondiola"),
    ("Congelados", r"congelad|helado|prepizza|\bpizza"),
]


def bucket_of(item_id):
    """Reparto del detalle en 256 archivos. El navegador usa el mismo cálculo (FNV-1a de 32 bits)."""
    h = 2166136261
    for byte in item_id.encode("utf-8"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return f"{h % 256:02x}"


def _match(text):
    text = consulta.fold(text)
    for name, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return name
    return None


def category_of(title, store_category=None):
    """La categoría que la propia tienda asigna (si la guardó) manda; si no alcanza, las palabras del título."""
    return (_match(store_category) if store_category else None) or _match(title) or "Otros"


def promo_info(promo, price, list_price):
    """Interpreta el texto de promo: tipo, etiqueta corta y % de descuento."""
    p = consulta.fold(promo or "")
    kind = label = None
    pct = None
    if m := re.search(r"\b(\d)\s*x\s*(\d)\b", p):
        kind, label = "nxm", f"{m.group(1)}x{m.group(2)}"
    elif m := re.search(r"(\d{2})\s*%\s*(?:en\s*la\s*)?2da|2da\s*(?:al\s*)?(\d{2})\s*%", p):
        kind, label = "pct_nth", f"{m.group(1) or m.group(2)}% 2da"
    elif m := re.search(r"llevando\s*(\d+)", p):
        kind, label = "bulk", f"Llevando {m.group(1)}"
    elif "tarjeta" in p:
        kind, label = "card", (re.search(r"tarjeta[^|]*", promo or "", re.I).group(0).strip())[:28]
    elif "cuotas" in p:
        kind, label = "installments", "Cuotas"
    elif m := re.search(r"(\d{1,2})\s*%\s*dto", p):
        kind, label, pct = "pct", f"{m.group(1)}% Dto", int(m.group(1))
    elif "oferta" in p:
        kind, label = "offer", "Oferta"
    discount = None
    if list_price and price and list_price > price:
        discount = round((list_price - price) / list_price * 100)
    elif pct:
        discount = pct
    return kind, label, discount


def size_text(title):
    q, u = parse_size(title)
    if not q:
        return None
    if q >= 1000:
        return f"{q / 1000:g} {'kg' if u == 'g' else 'l'}"
    return f"{q:g} {u}"


def pretty(text):
    text = " ".join((text or "").replace("\r", " ").replace("\n", " ").split())
    return text.title() if text.isupper() else text


def main():
    db = sqlite3.connect(DB_PATH)
    chain_label = {c: l for c, l in zip(consulta.CHAIN_LABELS.keys(), consulta.CHAIN_LABELS.values())}

    cur = db.execute("""
        SELECT o.chain, o.external_sku, o.title, o.brand, o.sale_price, o.list_price, o.promo, o.url, o.ean,
               o.raw_payload, m.ean, m.method
        FROM price_observation o
        LEFT JOIN product_match m ON m.chain = o.chain AND m.external_sku = o.external_sku
        WHERE o.observed_at = (SELECT MAX(observed_at) FROM price_observation p WHERE p.chain = o.chain)
          AND o.sale_price > 0 AND o.in_stock = 1 AND o.chain IN """ + SQL_IN)
    groups = defaultdict(lambda: {"rows": {}, "keys": set()})
    for chain, sku, title, brand, sale, lst, promo, url, ean, raw, m_ean, m_method in cur:
        key = ean or (m_ean if m_method == "auto" else None)
        key = f"ean:{key}" if key else f"{chain}:{sku}"
        g = groups[key]
        g["keys"].add((chain, sku))
        prev = g["rows"].get(chain)
        if prev is None or sale < prev["price"]:        # varias publicaciones del mismo producto: la más barata
            ruta = None
            try:
                extra = json.loads(raw)
                ruta = extra.get("ruta") or extra.get("cat") or " ".join(filter(None, [extra.get("rubro"), extra.get("familia")])) or None
            except (TypeError, ValueError, AttributeError):
                pass
            g["rows"][chain] = {"sku": sku, "title": pretty(title), "brand": brand, "price": sale, "list": lst,
                                "promo": promo, "url": url, "ruta": ruta, "ean": ean}

    # Anomalías de mercado (mismas reglas que las alertas diarias)
    flagged = defaultdict(list)
    for a in anomalies.market_alerts(anomalies.latest_per_chain(db)):
        if a["tipo"] in ("posible_error", "bajo_mercado") and a.get("ean"):
            flagged[f"ean:{a['ean']}"].append(a)

    # Historial: último precio de cada día por (cadena, sku)
    wanted = {k for g in groups.values() for k in g["keys"]}
    daily = defaultdict(dict)           # (chain, sku) -> {date: price}
    for chain, sku, ts, price in db.execute(
            "SELECT chain, external_sku, observed_at, sale_price FROM price_observation "
            "WHERE sale_price > 0 AND in_stock = 1 ORDER BY observed_at"):
        if (chain, sku) in wanted:
            daily[(chain, sku)][ts[:10]] = price

    items = []
    for key, g in groups.items():
        rows = g["rows"]
        best_chain = next((c for c in CHAIN_ORDER if c in rows), next(iter(rows)))
        name = rows[best_chain]["title"]
        brand = next((r["brand"] for c in CHAIN_ORDER if c in rows and (r := rows[c])["brand"]), None)
        offers = []
        for chain, r in rows.items():
            up, basis = unit_price(r["price"], r["title"])
            kind, label, discount = promo_info(r["promo"], r["price"], r["list"] if chain in anomalies.RELIABLE_LIST else None)
            offers.append({"chain": chain, "chain_label": chain_label.get(chain, chain), "title": r["title"],
                           "price": round(r["price"]), "list_price": round(r["list"]) if r["list"] and r["list"] > r["price"] and chain in anomalies.RELIABLE_LIST else None,
                           "unit_price": round(up) if up else None, "basis": basis, "promo": r["promo"] and r["promo"][:60],
                           "promo_type": kind, "promo_label": label, "discount_pct": discount, "url": r["url"]})
        basis = next((o["basis"] for o in offers if o["basis"]), None)
        offers.sort(key=lambda o: (o["unit_price"] is None or o["basis"] != basis, o["unit_price"] or o["price"]))
        priced = [o["unit_price"] for o in offers if o["unit_price"] and o["basis"] == basis]
        prices = [o["price"] for o in offers]
        ruta = next((r["ruta"] for r in rows.values() if r["ruta"]), None)

        hist = defaultdict(dict)
        for chain, sku in g["keys"]:
            for day, price in daily.get((chain, sku), {}).items():
                hist[day][chain] = round(price)
        history = [{"d": d, "min": min(v.values()), "by_chain": v} for d, v in sorted(hist.items())][-HISTORY_DAYS:]

        anomaly = None
        if key in flagged:
            worst = min(flagged[key], key=lambda a: a["ratio"] or 1)
            anomaly = {"type": worst["tipo"], "chain": chain_label.get(worst["chain"], worst["chain"]),
                       "ratio": round(worst["ratio"], 2) if worst["ratio"] else None, "detail": worst["detail"]}
        for o in offers:
            o["flag"] = bool(anomaly and anomaly["chain"] == o["chain_label"])

        best_discount = max((o["discount_pct"] or 0 for o in offers), default=0)
        items.append({
            "id": key, "name": name, "brand": pretty(brand) if brand else None,
            "category": category_of(name, ruta), "size_text": size_text(name), "pack": parse_pack(name),
            "ean": key[4:] if key.startswith("ean:") else None, "basis": basis,
            "offers": offers,
            "stats": {"n_chains": len(offers), "min_price": min(prices), "max_price": max(prices),
                      "min_unit": min(priced) if priced else None, "max_unit": max(priced) if priced else None,
                      "spread_pct": round((max(priced) - min(priced)) / min(priced) * 100) if len(priced) > 1 else 0,
                      "best_chain": offers[0]["chain_label"], "best_discount": best_discount,
                      "aggressive": best_discount >= 30 or any(o["promo_type"] in ("nxm", "pct_nth", "bulk") for o in offers)},
            "anomaly": anomaly, "history": history,
        })
    items.sort(key=lambda i: (-i["stats"]["n_chains"], i["name"]))

    cats = defaultdict(int)
    for i in items:
        cats[i["category"]] += 1
    categories = [{"name": n, "count": c} for n, c in sorted(cats.items(), key=lambda kv: -kv[1])]
    cat_index = {c["name"]: k for k, c in enumerate(categories)}
    chain_ids = list(chain_label)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1) Índice liviano (se baja una vez y se busca/filtra en el navegador): una fila por producto.
    #    precios por cadena en el orden de "chains" (0 = no la tiene); unit = precio / denom (kg o litros).
    rows = []
    for i in items:
        first = next((o for o in i["offers"] if o["unit_price"]), None)
        denom = round(first["price"] / first["unit_price"], 4) if first else 0
        prices = [next((o["price"] for o in i["offers"] if o["chain"] == c), 0) for c in chain_ids]
        flags = (1 if i["stats"]["aggressive"] else 0) | (2 if i["anomaly"] else 0)
        rows.append([i["id"], i["name"], i["brand"] or "", i["size_text"] or "", cat_index[i["category"]], denom,
                     {"$/kg": 1, "$/l": 2}.get(i["basis"], 0), prices, flags, i["stats"]["best_discount"],
                     i["stats"]["n_chains"], i["stats"]["spread_pct"]])
    index = {"generated_at": now, "chains": [{"id": c, "label": chain_label[c]} for c in chain_ids],
             "categories": categories,
             "fields": ["id", "name", "brand", "size_text", "cat", "denom", "basis", "prices", "flags", "max_discount", "n_chains", "spread_pct"],
             "rows": rows}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 1) Índice liviano: un script que define window.CATALOGO_INDEX (funciona abriendo el HTML con doble clic).
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (OUT_DIR / "index.js").write_text("window.CATALOGO_INDEX=" + payload + ";\n", encoding="utf-8")

    # 2) Detalle completo repartido en 256 archivos (por hash del id): el navegador lee solo los que necesita.
    #    Se omiten los campos vacíos y los que el cliente deduce (etiqueta de cadena, base del precio unitario).
    shard_dir = OUT_DIR / "d"
    shard_dir.mkdir(exist_ok=True)
    for old in shard_dir.glob("*.js"):
        old.unlink()
    for stale in ("index.json", "detalle.db", "catalogo.js", "catalogo.json"):
        try:
            (OUT_DIR / stale).unlink()
        except FileNotFoundError:
            pass
    buckets = defaultdict(dict)
    for i in items:
        slim = dict(i)
        slim["offers"] = [{k: v for k, v in o.items() if v not in (None, False) and k not in ("chain_label", "basis")}
                          for o in i["offers"]]
        buckets[bucket_of(i["id"])][i["id"]] = slim
    for name, group in buckets.items():
        body = json.dumps(group, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (shard_dir / f"{name}.js").write_text(f'window.__shard&&window.__shard("{name}",{body});\n', encoding="utf-8")
    shard_bytes = sum(f.stat().st_size for f in shard_dir.glob("*.js"))

    multi = sum(i["stats"]["n_chains"] > 1 for i in items)
    print(f"Catálogo: {len(items)} productos ({multi} en 2+ cadenas), {sum(1 for i in items if i['anomaly'])} con anomalía, "
          f"{sum(1 for i in items if i['stats']['aggressive'])} con oferta fuerte")
    print("Categorías:", {c["name"]: c["count"] for c in categories})
    print(f"Índice: {(OUT_DIR / 'index.js').stat().st_size / 1e6:.1f} MB | Detalle: {len(buckets)} archivos, {shard_bytes / 1e6:.1f} MB")

if __name__ == "__main__":
    main()
