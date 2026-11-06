"""Genera metricas.json: ancho de avance de cada caracter (en milesimas de em) de las fuentes de los recortes.

presentacion.js lo usa para cortar los titulares en renglones y ubicar las marcas de birome roja sobre la palabra exacta,
sin depender de tener las fuentes al generar. Solo hace falta correrlo si se cambia la fuente de los recortes.
Las fuentes de Office que se bajan de la nube (Bodoni MT) quedan en %LOCALAPPDATA%\\Microsoft\\FontCache\\4\\CloudFonts
despues de usarlas una vez en PowerPoint.
"""
import glob
import json
import os

from PIL import ImageFont

NUBE = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\FontCache\4\CloudFonts")
WIN = r"C:\Windows\Fonts"


def buscar(familia, estilo):
    for f in glob.glob(os.path.join(NUBE, "*", "*.*")) + glob.glob(os.path.join(WIN, "*.tt*")):
        try:
            if ImageFont.truetype(f, 10).getname() == (familia, estilo):
                return f
        except OSError:
            pass
    raise SystemExit(f"no encuentro {familia} {estilo}: abrir la presentacion una vez en PowerPoint para que la baje")


FUENTES = {"Bodoni MT Condensed|b": ("Bodoni MT", "Condensed Bold"), "Bodoni MT Condensed": ("Bodoni MT", "Condensed"),
           "Cambria": ("Cambria", "Regular"), "Cambria|b": ("Cambria", "Bold")}
CHARS = [chr(c) for c in range(32, 127)] + [chr(c) for c in range(160, 256)] + list("“”‘’«»—–…•€$")

out = {}
for clave, (fam, est) in FUENTES.items():
    f = ImageFont.truetype(buscar(fam, est), 1000)
    out[clave] = {c: round(f.getlength(c)) for c in CHARS}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "metricas.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("metricas.json:", ", ".join(out))
