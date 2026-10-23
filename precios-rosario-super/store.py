"""Guardado con validación: las filas inválidas no llegan a price_observation.

Cada fila es la tupla que arman los scrapers:
(observed_at, chain, external_sku, ean, brand, title, list_price, sale_price, in_stock, promo,
 measurement_unit, unit_multiplier, url, raw_payload)

Reglas (solo estructurales; los precios raros pero posibles los analiza anomalies.py):
  - título y SKU no vacíos
  - precio numérico y finito; > 0 si el producto tiene stock (sin stock, VTEX devuelve 0)
  - precio < MAX_PRICE (descarta errores de unidades)
  - EAN, si existe, de 8 a 14 dígitos
  - precio de lista, si existe, numérico y >= 0 (0 es normal en productos sin stock)
Las rechazadas quedan en la tabla rejected_rows con el motivo, para poder revisarlas.
"""
import math
import re
import sqlite3

MAX_PRICE = 5_000_000
EAN_RE = re.compile(r"^\d{8,14}$")

REJECTED_SCHEMA = """
CREATE TABLE IF NOT EXISTS rejected_rows (
    observed_at TEXT, chain TEXT, reason TEXT, external_sku TEXT, title TEXT, sale_price REAL, list_price REAL
)"""


def _number_ok(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate(row):
    """Devuelve None si la fila es válida, o el motivo del rechazo."""
    (_, _, sku, ean, _, title, list_price, sale, in_stock, *_rest) = row
    if not sku:
        return "sin_sku"
    if not (title or "").strip():
        return "sin_titulo"
    if not _number_ok(sale):
        return "precio_no_numerico"
    if sale < 0 or sale >= MAX_PRICE:
        return "precio_fuera_de_rango"
    if sale == 0 and in_stock:
        return "precio_cero_con_stock"
    if ean and not EAN_RE.match(str(ean)):
        return "ean_invalido"
    # Lista en 0 es normal en productos sin stock (VTEX); solo se rechaza si no es número o es negativa
    if list_price is not None and (not _number_ok(list_price) or list_price < 0):
        return "lista_invalida"
    return None


def save_rows(db, rows):
    """Inserta las filas válidas. Devuelve (insertadas, rechazadas) y avisa si hubo rechazos."""
    db.execute(REJECTED_SCHEMA)
    good, bad = [], []
    for row in rows:
        reason = validate(row)
        if reason:
            bad.append((row[0], row[1], reason, row[2], row[5], row[7], row[6]))
        else:
            good.append(row)
    db.executemany(
        "INSERT INTO price_observation (observed_at, chain, external_sku, ean, brand, title,"
        " list_price, sale_price, in_stock, promo, measurement_unit, unit_multiplier, url,"
        " raw_payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", good)
    if bad:
        db.executemany("INSERT INTO rejected_rows VALUES (?,?,?,?,?,?,?)", bad)
        reasons = {}
        for b in bad:
            reasons[b[2]] = reasons.get(b[2], 0) + 1
        print(f"    ! {len(bad)} filas rechazadas por validación: {reasons}")
    return len(good), len(bad)
