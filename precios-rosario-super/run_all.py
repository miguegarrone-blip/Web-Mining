"""Corrida diaria completa: respaldo -> scrapers -> salud -> matching -> alertas -> resumen.

Uso: python run_all.py
"""
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = Path(os.environ.get("PRECIOS_DB") or HERE / "precios.db")
BACKUP_DIR = DB_PATH.parent / "backups"   # junto a la base usada (así una prueba con copia no pisa los respaldos reales)
KEEP_BACKUPS = 3        # cada respaldo pesa lo mismo que la base (varios GB)
KEEP_DAYS = 30
JOBS = [
    ["asp_full.py"],             # La Gallega y DAR: catálogo completo (~15.000 productos, 1 min)
    ["coto_full.py"],            # Coto: rubros de supermercado (~15.500 productos, ~5 min)
    ["vtex_full.py"],            # Carrefour y Jumbo: todas las categorías (~30 min, en paralelo)
    ["health.py", "--send"],     # detecta scrapers rotos o con pocos productos
    ["matching.py"],             # homologación + precio por unidad
    ["anomalies.py", "--send"],  # alertas (Telegram si hay variables de entorno)
    ["catalogo.py"],             # catálogo para la interfaz web (web/data)
    ["canasta.py", "--export"],  # costo de tu canasta (canasta.json) y su historial
]


def backup():
    """Copia consistente de la base antes de escribir; conserva las últimas KEEP_BACKUPS."""
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    target = BACKUP_DIR / f"precios_{datetime.now():%Y-%m-%d}.db"
    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    for old in sorted(BACKUP_DIR.glob("precios_*.db"))[:-KEEP_BACKUPS]:
        old.unlink()
    print(f"Respaldo: {target.name} ({target.stat().st_size / 1e6:.1f} MB)", flush=True)


def prune():
    """Mantiene la base acotada: ~200.000 filas nuevas por día. Se conservan 30 días (para el historial);
    de lo que tiene más de 2 días se descarta el texto crudo (raw_payload), que es lo que más pesa."""
    from datetime import timedelta, timezone
    if not DB_PATH.exists():
        return
    now = datetime.now(timezone.utc)
    db = sqlite3.connect(DB_PATH, timeout=120)
    gone = db.execute("DELETE FROM price_observation WHERE observed_at < ?", ((now - timedelta(days=KEEP_DAYS)).isoformat(),)).rowcount
    slim = db.execute("UPDATE price_observation SET raw_payload = NULL WHERE raw_payload IS NOT NULL AND observed_at < ?",
                      ((now - timedelta(days=2)).isoformat(),)).rowcount
    db.commit()
    page, free = db.execute("PRAGMA page_count").fetchone()[0], db.execute("PRAGMA freelist_count").fetchone()[0]
    if page and free / page > 0.3:                  # más de 30 % de espacio vacío: se compacta el archivo
        print(f"Compactando la base ({free / page:.0%} de espacio libre)…", flush=True)
        db.execute("VACUUM")
    db.close()
    print(f"Limpieza: {gone} filas de más de {KEEP_DAYS} días eliminadas, {slim} sin texto crudo", flush=True)


def main():
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}   # el log se escribe en vivo
    backup()
    prune()
    failed = []
    for job in JOBS:
        print(f"\n=== {' '.join(job)} ===", flush=True)
        t0 = time.time()
        code = subprocess.run([sys.executable, *job], cwd=HERE, env=env, check=False).returncode
        print(f"--- {job[0]}: {time.time() - t0:.0f}s, código {code}", flush=True)
        if code and job[0] != "health.py":   # health devuelve 1 si hay cadenas con problemas: ya lo informa
            failed.append(job[0])

    db = sqlite3.connect(DB_PATH)
    print("\n=== Resumen de la última corrida ===")
    print(f"{'cadena':<11}{'filas':>7}{'EAN únicos':>12}{'con promo':>11}")
    for chain, n, eans, promos in db.execute(
        """SELECT chain, COUNT(*), COUNT(DISTINCT ean), SUM(promo IS NOT NULL)
           FROM price_observation
           WHERE observed_at = (SELECT MAX(observed_at) FROM price_observation p2 WHERE p2.chain = price_observation.chain)
           GROUP BY chain ORDER BY chain"""):
        print(f"{chain:<11}{n:>7}{eans:>12}{promos:>11}")
    if failed:
        print(f"\n!! Pasos con error: {', '.join(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
