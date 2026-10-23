"""Corre el pipeline completo: baja los medios, clasifica, actualiza historico.csv y regenera rosario.html.
Si algo falla, deja el detalle en archivar.log."""
import os, sys, runpy, traceback
from datetime import datetime
AQUI = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(AQUI, "archivar.log")

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")

# pythonw no tiene consola: sin esto, cualquier print puede fallar
if sys.stdout is None: sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None: sys.stderr = open(os.devnull, "w", encoding="utf-8")

try:
    os.chdir(AQUI)
    log(f"inicio python={sys.executable} user={os.environ.get('USERNAME')}")
    runpy.run_path(os.path.join(AQUI, "build.py"))
    log("ok")
except BaseException:
    log("ERROR\n" + traceback.format_exc())
    raise
