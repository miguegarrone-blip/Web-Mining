"""Control de salud de las corridas: detecta scrapers rotos o que dejaron de traer productos.

Para cada cadena compara la última corrida contra la mediana de las corridas anteriores
(hasta BASELINE_RUNS) y registra el resultado en la tabla run_health.

Estados:
  OK        : trajo al menos MIN_RATIO de lo habitual
  BAJO      : trajo menos de MIN_RATIO (posible cambio parcial del sitio o bloqueo)
  ROTO      : 0 productos o la cadena no corrió en la última corrida
  NUEVO     : todavía no hay corridas previas para comparar
Las filas rechazadas por validación suman un aviso si superan el 5 % de la corrida.

Uso:
    python health.py            # evalúa y muestra
    python health.py --send     # además avisa por Telegram si hay problemas (si está configurado)
"""
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("PRECIOS_DB") or Path(__file__).with_name("precios.db"))
CHAINS = ["carrefour", "coto", "dar", "jumbo", "lagallega"]
BASELINE_RUNS = 7
MIN_RATIO = 0.70
MAX_REJECT_RATIO = 0.05
STALE_HOURS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS run_health (
    checked_at TEXT, chain TEXT, run_at TEXT, n_rows INTEGER, baseline REAL, n_rejected INTEGER, status TEXT, detail TEXT
)"""


def evaluate(db):
    db.executescript(SCHEMA)
    now = datetime.now(timezone.utc)
    results = []
    for chain in CHAINS:
        runs = db.execute("""SELECT observed_at, COUNT(*) FROM price_observation WHERE chain=?
                             GROUP BY observed_at ORDER BY observed_at DESC LIMIT ?""",
                          (chain, BASELINE_RUNS + 1)).fetchall()
        if not runs:
            results.append((chain, None, 0, None, 0, "ROTO", "sin ninguna corrida registrada"))
            continue
        run_at, n = runs[0]
        prev = [c for _, c in runs[1:]]
        rejected = 0
        try:
            rejected = db.execute("SELECT COUNT(*) FROM rejected_rows WHERE chain=? AND observed_at=?",
                                  (chain, run_at)).fetchone()[0]
        except sqlite3.OperationalError:
            pass
        age = now - datetime.fromisoformat(run_at)
        baseline = statistics.median(prev) if prev else None
        if n == 0:
            status, detail = "ROTO", "0 productos"
        elif age > timedelta(hours=STALE_HOURS):
            status, detail = "ROTO", f"no corrió hace {age.days * 24 + age.seconds // 3600} h"
        elif baseline is None:
            status, detail = "NUEVO", "sin historial para comparar"
        elif n < baseline * MIN_RATIO:
            status, detail = "BAJO", f"{n} productos vs {baseline:.0f} habituales ({n / baseline:.0%})"
        else:
            status, detail = "OK", f"{n} productos ({n / baseline:.0%} de lo habitual)"
        if status in ("OK", "NUEVO") and n and rejected / (n + rejected) > MAX_REJECT_RATIO:
            status, detail = "BAJO", detail + f"; {rejected} filas rechazadas por validación"
        results.append((chain, run_at, n, baseline, rejected, status, detail))
    stamp = now.isoformat(timespec="seconds")
    db.executemany("INSERT INTO run_health VALUES (?,?,?,?,?,?,?,?)",
                   [(stamp, c, r, n, b, rej, s, d) for c, r, n, b, rej, s, d in results])
    db.commit()
    return results


def main():
    send = "--send" in sys.argv
    db = sqlite3.connect(DB_PATH)
    results = evaluate(db)
    print("Salud de la última corrida:")
    for chain, run_at, n, baseline, rejected, status, detail in results:
        print(f"  {chain:<10} {status:<6} {detail}" + (f"  [{rejected} rechazadas]" if rejected else ""))
    problems = [r for r in results if r[5] in ("ROTO", "BAJO")]
    if problems:
        print(f"\n!! {len(problems)} cadenas con problemas: " + ", ".join(p[0] for p in problems))
        if send:
            from anomalies import send_telegram
            text = "Monitor de precios - revisar scrapers:\n" + "\n".join(f"- {p[0]}: {p[5]} ({p[6]})" for p in problems)
            if not send_telegram(text):
                print("   (Telegram no configurado: el aviso queda solo en el log)")
    db.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
