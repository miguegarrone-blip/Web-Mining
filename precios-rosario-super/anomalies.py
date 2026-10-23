"""Detección de anomalías de precio y alertas.

Solo se analizan productos con stock y precio > 0 (sin stock, VTEX devuelve precio 0).

Tres detectores (de más a menos confiable):
  1. mercado   : precio efectivo muy por debajo (o por encima) de la mediana de las otras cadenas
                 para el mismo producto (requiere >= MIN_CHAINS cadenas con matching).
  2. historia  : salto abrupto contra la observación anterior de la misma cadena/SKU. Con >= MIN_HISTORY
                 observaciones usa z-score robusto (mediana y MAD) sobre variaciones %; con menos, umbral fijo.
  3. reglas    : precio <= 0, oferta > lista (solo cadenas con lista confiable).

Clasificación: si el producto trae una promo declarada y la caída es coherente, es "oferta"
(informativa); caída fuerte sin promo declarada -> "posible_error" (alerta alta).

Notificación: consola siempre; Telegram si existen las variables de entorno
TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (nunca se guardan en el código). Se deduplica por
(cadena, sku, tipo, día) en la tabla alerts_sent.

Uso:
    python anomalies.py            # detecta y muestra
    python anomalies.py --send     # además envía por Telegram las alertas nuevas
"""
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from chains import SQL_IN

DB_PATH = Path(os.environ.get("PRECIOS_DB") or Path(__file__).with_name("precios.db"))
RELIABLE_LIST = {"carrefour", "coto", "lagallega"}   # Jumbo trae ListPrice basura
MIN_CHAINS = 3
MIN_HISTORY = 5
DROP_ERROR = 0.50      # < 50 % de la mediana de mercado
DROP_WARN = 0.70
SPIKE = 2.0            # > 2x la mediana de mercado
HIST_DROP = 0.40       # caída > 40 % vs observación anterior
Z_LIMIT = 3.5


def latest_per_chain(db):
    return db.execute("""
        SELECT o.chain, o.external_sku, o.title, o.sale_price, o.list_price, o.promo, o.observed_at,
               COALESCE(m.ean, o.ean) AS ean, COALESCE(m.method, 'ean') AS method
        FROM price_observation o
        LEFT JOIN product_match m ON m.chain = o.chain AND m.external_sku = o.external_sku
        WHERE o.observed_at = (SELECT MAX(observed_at) FROM price_observation p WHERE p.chain = o.chain)
          AND o.sale_price > 0 AND o.in_stock = 1 AND o.chain IN """ + SQL_IN).fetchall()


def market_alerts(rows):
    by_ean = {}
    for chain, sku, title, sale, lst, promo, ts, ean, method in rows:
        if ean and method in ("ean", "auto"):
            by_ean.setdefault(ean, []).append((chain, sku, title, sale, promo, method))
    out = []
    for ean, items in by_ean.items():
        chains = {i[0] for i in items}
        if len(chains) < MIN_CHAINS:
            continue
        for chain, sku, title, sale, promo, method in items:
            others = [i[3] for i in items if i[0] != chain and i[3] and i[3] > 0]
            if len(others) < MIN_CHAINS - 1 or not sale:
                continue
            med = statistics.median(others)
            ratio = sale / med
            if ratio <= DROP_WARN:
                # "posible_error" solo si el producto está confirmado por EAN (no por matching de texto)
                severe = ratio <= DROP_ERROR and method == "ean"
                tipo = "oferta" if promo else ("posible_error" if severe else "bajo_mercado")
                out.append(dict(chain=chain, sku=sku, title=title, kind="mercado", tipo=tipo, price=sale,
                                ref=med, ratio=ratio, ean=ean, promo=promo,
                                detail=f"{ratio:.0%} de la mediana de {len(others)} cadenas ({med:,.0f})"))
            elif ratio >= SPIKE:
                out.append(dict(chain=chain, sku=sku, title=title, kind="mercado",
                                tipo="posible_error" if method == "ean" else "salto", price=sale,
                                ref=med, ratio=ratio, ean=ean, promo=promo,
                                detail=f"{ratio:.1f}x la mediana de {len(others)} cadenas ({med:,.0f})"))
    return out


def history_alerts(db):
    out = []
    keys = db.execute("""SELECT chain, external_sku FROM price_observation
                         GROUP BY chain, external_sku HAVING COUNT(DISTINCT observed_at) >= 2""").fetchall()
    for chain, sku in keys:
        obs = db.execute("""SELECT observed_at, sale_price, promo, title FROM price_observation
                            WHERE chain=? AND external_sku=? AND sale_price > 0
                            GROUP BY observed_at ORDER BY observed_at""", (chain, sku)).fetchall()
        if len(obs) < 2:
            continue
        prices = [o[1] for o in obs]
        changes = [(b - a) / a for a, b in zip(prices, prices[1:])]
        last = changes[-1]
        z = None
        if len(changes) >= MIN_HISTORY:
            hist = changes[:-1]
            med = statistics.median(hist)
            mad = statistics.median(abs(c - med) for c in hist) or 1e-9
            z = 0.6745 * (last - med) / mad
        triggered = (z is not None and abs(z) > Z_LIMIT and abs(last) > 0.10) or (z is None and (last <= -HIST_DROP or last >= 1.0))
        if triggered:
            promo = obs[-1][2]
            tipo = "oferta" if promo and last < 0 else ("posible_error" if abs(last) >= 0.5 else "salto")
            out.append(dict(chain=chain, sku=sku, title=obs[-1][3], kind="historia", tipo=tipo, price=prices[-1],
                            ref=prices[-2], ratio=prices[-1] / prices[-2], ean=None, promo=promo,
                            detail=f"{last:+.0%} vs observación anterior ({prices[-2]:,.0f} -> {prices[-1]:,.0f})"
                                   + (f", z={z:.1f}" if z is not None else "")))
    return out


def rule_alerts(rows):
    out = []
    for chain, sku, title, sale, lst, promo, ts, ean, method in rows:
        if sale <= 0:
            out.append(dict(chain=chain, sku=sku, title=title, kind="regla", tipo="posible_error", price=sale,
                            ref=None, ratio=None, ean=ean, promo=promo, detail="precio <= 0"))
        elif chain in RELIABLE_LIST and lst and sale > lst * 1.01 and not promo:
            out.append(dict(chain=chain, sku=sku, title=title, kind="regla", tipo="inconsistencia", price=sale,
                            ref=lst, ratio=sale / lst, ean=ean, promo=promo,
                            detail=f"precio {sale:,.0f} > lista {lst:,.0f} sin promo"))
    return out


def format_alert(a):
    icon = {"posible_error": "🚨", "bajo_mercado": "⚠️", "oferta": "🏷️", "salto": "📈", "inconsistencia": "❓"}.get(a["tipo"], "•")
    promo = f" | promo: {a['promo'][:50]}" if a.get("promo") else ""
    return f"{icon} [{a['tipo']}] {a['chain']}: {a['title'][:70]} — ${a['price']:,.0f}\n   {a['detail']}{promo}"


def send_telegram(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[:4000]}, timeout=30)
    return r.ok


def main():
    send = "--send" in sys.argv
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS alerts_sent (chain TEXT, sku TEXT, tipo TEXT, day TEXT,
                  PRIMARY KEY (chain, sku, tipo, day))""")
    rows = latest_per_chain(db)
    alerts = market_alerts(rows) + history_alerts(db) + rule_alerts(rows)
    order = {"posible_error": 0, "inconsistencia": 1, "bajo_mercado": 2, "salto": 3, "oferta": 4}
    alerts.sort(key=lambda a: (order.get(a["tipo"], 9), a["ratio"] if a["ratio"] is not None else 0))

    counts = {}
    for a in alerts:
        counts[a["tipo"]] = counts.get(a["tipo"], 0) + 1
    print("Alertas por tipo:", counts)
    for a in [x for x in alerts if x["tipo"] != "oferta"][:15]:
        print(format_alert(a))

    if send:
        today = datetime.now(timezone.utc).date().isoformat()
        candidates = [a for a in alerts if a["tipo"] in ("posible_error", "bajo_mercado", "inconsistencia")]
        new = [a for a in candidates if not db.execute(
            "SELECT 1 FROM alerts_sent WHERE chain=? AND sku=? AND tipo=? AND day=?",
            (a["chain"], a["sku"], a["tipo"], today)).fetchone()]
        if not new:
            print("Sin alertas nuevas para enviar.")
        elif send_telegram("Monitor de precios - alertas nuevas:\n\n"
                           + "\n\n".join(format_alert(a) for a in new[:10])):
            # Solo se marcan como enviadas las que efectivamente salieron (las primeras 10)
            db.executemany("INSERT OR IGNORE INTO alerts_sent VALUES (?,?,?,?)",
                           [(a["chain"], a["sku"], a["tipo"], today) for a in new[:10]])
            db.commit()
            print(f"Enviadas {min(len(new), 10)} alertas por Telegram ({len(new) - 10 if len(new) > 10 else 0} quedan para la próxima).")
        else:
            print(f"{len(new)} alertas nuevas sin enviar: falta configurar TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.")
    db.close()


if __name__ == "__main__":
    main()
