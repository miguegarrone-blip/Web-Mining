"""Homologación de productos entre cadenas + precio por unidad de medida.

Estrategia en cascada:
  1. EAN exacto (Carrefour, Coto, Vea, Jumbo, Disco, La Gallega) -> grupo = EAN.
  2. Sin EAN (DAR): se bloquea por tamaño (g/ml/un) y se puntúa la similitud del texto
     contra los productos con EAN. >= AUTO -> match automático; entre REVIEW y AUTO -> cola de revisión.

Uso:
    python matching.py            # matchea, guarda product_match / unit_price y valida con La Gallega
"""
import os
import re
import sqlite3
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from chains import SQL_IN

DB_PATH = Path(os.environ.get("PRECIOS_DB") or Path(__file__).with_name("precios.db"))
EAN_CHAINS = ["carrefour", "coto", "jumbo", "lagallega"]
NO_EAN_CHAINS = ["dar"]
AUTO, REVIEW, TIE_MARGIN = 0.80, 0.60, 0.03

ABBREV = {"ent": "entera", "desc": "descremada", "desn": "descremada", "parc": "parcialmente",
          "lv": "larga vida", "l v": "larga vida", "uat": "larga vida", "sach": "sachet",
          "gaseosa": "gaseosa", "sab": "sabor", "gsa": "gaseosa", "clas": "clasica",
          "tradic": "tradicional", "s p": "sin palo", "c p": "con palo", "bc": "blanco",
          "pet": "", "brik": "", "botella": "", "sachet": "", "caja": "", "paquete": "", "bolsa": "",
          "lata": "", "pack": "", "multipack": "", "marca": "", "x": ""}
STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "en", "y", "a", "al", "por", "para",
        "un", "una", "gr", "grs", "g", "gm", "gms", "kg", "kgs", "cc", "ml", "lt", "lts", "l",
        "litro", "litros", "unid", "unidades", "u", "classic", "clasica", "clasico"}

SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|kgs|kilo|kilos|k|gr|grs|g|gm|gms|gramos|cc|ml|lt|lts|l|litro|litros)\b")
PACK_RE = re.compile(r"(?:x|por|multipack\s*x?|pack\s*x?)\s*(\d{1,3})(?![.,]\d)\b(?!\s*(?:gr|g|kg|cc|ml|l|lt))", re.I)   # (?![.,]\d): "x 2,25 lt" no es un pack de 2


def fold(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = text.replace("\r", " ").replace("\n", " ")
    return re.sub(r"[^a-z0-9.,%\s]", " ", text)


MAX_SIZE = 50000    # 50 kg o 50 litros: más que eso en un supermercado es un error de carga


def parse_size(title):
    """Devuelve (cantidad en g/ml, 'g'|'ml') o (None, None). Si hay varias, usa la mayor unitaria."""
    t = fold(title)
    best = None
    for num, unit in SIZE_RE.findall(t):
        n = float(num.replace(",", "."))
        if unit in ("kg", "kgs", "kilo", "kilos", "k"):
            q, u = n * 1000, "g"
        elif unit in ("gr", "grs", "g", "gm", "gms", "gramos"):
            q, u = n, "g"
        elif unit in ("cc", "ml"):
            q, u = n, "ml"
        else:
            q, u = n * 1000, "ml"
        if q > MAX_SIZE:        # error de carga del comercio (ej. "x 500 Kg"): se ignora ese tamaño
            continue
        if best is None or q > best[0]:
            best = (q, u)
    return best if best else (None, None)


UNITS_RE = re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:u|un|uni|unid|unidad|unidades)\b", re.I)


LEADING_PACK_RE = re.compile(r"\s*(\d{1,3})\s*x\s+[a-z]")   # "6 x cerveza ..." (solo al comienzo del título)


def parse_pack(title):
    """Unidades del pack: "x6", "pack x 4", "6 Unidades", "6U". 1 si es una unidad."""
    t = fold(title)
    m = PACK_RE.search(t) or UNITS_RE.search(t) or LEADING_PACK_RE.match(t)
    return int(m.group(1)) if m else 1


def tokens(title):
    t = fold(title)
    t = SIZE_RE.sub(" ", t)
    t = PACK_RE.sub(" ", t)
    out = []
    for w in re.findall(r"[a-z0-9%]+", t):
        w = ABBREV.get(w, w)
        for piece in w.split():
            if piece in STOP or not piece:
                continue
            if len(piece) > 3 and piece.endswith("s"):
                piece = piece[:-1]
            out.append(piece)
    return out


VARIANTS = {"spaghetti", "espagueti", "tallarin", "tirabuzon", "mostachol", "penne", "rigate", "fusilli",
            "codito", "moño", "moñito", "lazo", "fideo", "entera", "descremada", "parcialmente", "deslactosada",
            "light", "zero", "diet", "vainilla", "chocolate", "frutilla", "naranja", "limon", "lima", "pomelo",
            "uva", "manzana", "durazno", "tacc", "integral", "blanco", "negro", "tostado", "torrado", "molido",
            "grano", "sabor", "liviana", "multivit", "fortificada", "girasol", "maiz", "oliva", "mezcla",
            "comun", "tradicional", "suave", "cola", "negra"}


def conflict(a_tokens, b_tokens):
    """True si los títulos nombran variantes distintas (no pueden ser el mismo producto)."""
    a, b = set(a_tokens), set(b_tokens)
    va, vb = a & VARIANTS, b & VARIANTS
    if va and vb and not (va <= vb or vb <= va):
        return True
    pa = {t for t in a if "%" in t or t.replace(".", "").replace(",", "").isdigit()}
    pb = {t for t in b if "%" in t or t.replace(".", "").replace(",", "").isdigit()}
    return bool(pa and pb and pa != pb)


def similarity(a_tokens, b_tokens):
    if not a_tokens or not b_tokens or conflict(a_tokens, b_tokens):
        return 0.0
    a, b = set(a_tokens), set(b_tokens)
    jac = len(a & b) / len(a | b)
    contain = len(a & b) / min(len(a), len(b))
    seq = SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    return 0.4 * jac + 0.3 * contain + 0.3 * seq


def load_rows(db):
    cols = "obs_id, chain, external_sku, ean, brand, title, sale_price, list_price"
    q = f"""SELECT {cols} FROM price_observation
            WHERE observed_at = (SELECT MAX(observed_at) FROM price_observation p WHERE p.chain = price_observation.chain)
            AND chain IN {SQL_IN}"""
    return [dict(zip(cols.replace(" ", "").split(","), r)) for r in db.execute(q)]


def build_index(rows):
    """EAN -> {titles, tokens, size, pack}; índice por (unidad, tamaño redondeado)."""
    groups = {}
    for r in rows:
        if r["chain"] not in EAN_CHAINS or not r["ean"]:
            continue
        g = groups.setdefault(r["ean"], {"ean": r["ean"], "titles": [], "tok": [], "tokset": set(), "size": None, "pack": 1, "chains": set()})
        g["titles"].append(r["title"])
        tk = tokens(r["title"])
        g["tok"].append(tk)
        g["tokset"].update(tk)
        g["chains"].add(r["chain"])
        q, u = parse_size(r["title"])
        if q and not g["size"]:
            g["size"] = (q, u)
            g["pack"] = parse_pack(r["title"])
    by_size = defaultdict(list)
    for g in groups.values():
        if g["size"]:
            by_size[(g["size"][1], round(g["size"][0]))].append(g)
    return groups, by_size


def candidates(by_size, size, pack):
    q, u = size
    out = []
    for d in (0, -1, 1, -2, 2):
        out.extend(by_size.get((u, round(q) + d), []))
    return [g for g in out if g["pack"] == pack]


def match_row(row, by_size, exclude_chain=None):
    size = parse_size(row["title"])
    if not size[0]:
        return None, 0.0, "sin_tamano"
    tk = tokens(row["title"])
    tkset = set(tk)
    need = min(2, len(tkset))              # al menos 2 palabras en común (1 si el título tiene una sola)
    scored = []
    for g in candidates(by_size, size, parse_pack(row["title"])):
        if len(tkset & g["tokset"]) < need:
            continue                        # filtro barato: evita la comparación de texto con miles de grupos
        chains = g["chains"] - {exclude_chain} if exclude_chain else g["chains"]
        if chains:
            scored.append((max(similarity(tk, t) for t in g["tok"]), g["ean"]))
    if not scored:
        return None, 0.0, "sin_candidato"
    scored.sort(reverse=True)
    best_s, best_ean = scored[0]
    if best_s < REVIEW:
        return best_ean, best_s, "descartado"
    # Empate: otro EAN con casi el mismo puntaje -> no decidir solo
    if len(scored) > 1 and best_s - scored[1][0] < TIE_MARGIN:
        return best_ean, best_s, "revision"
    return best_ean, best_s, "auto" if best_s >= AUTO else "revision"


STANDARD_ML = (200, 237, 250, 269, 310, 330, 354, 355, 375, 410, 473, 500, 710, 750, 1000, 1500)


def is_standard(single_ml):
    return any(abs(single_ml - s) <= s * 0.01 for s in STANDARD_ML)


def unit_price(price, title):
    """Precio por kg o por litro. Con packs ("x 6 Un.") evita doble conteo cuando el título ya
    trae el volumen total (ej. "x 6 Un. x 2838 cc": 2838 / 6 = 473, un tamaño estándar)."""
    q, u = parse_size(title)
    pack = parse_pack(title)
    if not (price and q):
        return None, None
    total = q
    if pack > 1:
        already_total = u == "ml" and q > 1500 and is_standard(q / pack)
        if not already_total and q * pack < 30000:
            total = q * pack
    return round(price / (total / 1000), 2), ("$/kg" if u == "g" else "$/l")


def validate(rows, groups, by_size):
    """Oculta el EAN de La Gallega, matchea por texto contra las otras cadenas y mide aciertos."""
    pool_rows = [r for r in rows if r["chain"] != "lagallega"]
    _, pool_by_size = build_index(pool_rows)
    pool_eans = {r["ean"] for r in pool_rows if r["ean"]}
    tested = [r for r in rows if r["chain"] == "lagallega" and r["ean"] in pool_eans]
    tested = tested[:: max(1, len(tested) // 800)]      # muestra de ~800 (con todo el catálogo tardaría minutos)
    stats = defaultdict(int)
    wrong = []
    for r in tested:
        ean, score, status = match_row(r, pool_by_size)
        if status == "auto":
            stats["auto_ok" if ean == r["ean"] else "auto_mal"] += 1
            if ean != r["ean"]:
                wrong.append((r["title"], score, ean))
        elif status == "revision":
            stats["rev_ok" if ean == r["ean"] else "rev_mal"] += 1
        else:
            stats["sin_match"] += 1
    n = len(tested)
    auto = stats["auto_ok"] + stats["auto_mal"]
    print(f"\nValidación (La Gallega sin EAN vs resto, {n} productos con equivalente real):")
    print(f"  auto (>= {AUTO}): {auto}  correctos {stats['auto_ok']}  incorrectos {stats['auto_mal']}"
          f"  -> precisión {stats['auto_ok'] / auto:.1%}" if auto else "  sin matches automáticos")
    print(f"  revisión manual ({REVIEW}-{AUTO}): {stats['rev_ok'] + stats['rev_mal']}"
          f"  (correctos {stats['rev_ok']})")
    print(f"  sin match: {stats['sin_match']}  -> cobertura automática {stats['auto_ok'] / n:.1%}")
    for w in wrong[:6]:
        print("   ✗", w)


def main():
    db = sqlite3.connect(DB_PATH)
    rows = load_rows(db)
    groups, by_size = build_index(rows)
    print(f"Grupos por EAN: {len(groups)}  (en 2+ cadenas: {sum(len(g['chains']) > 1 for g in groups.values())})")

    validate(rows, groups, by_size)

    db.executescript("""
        DROP TABLE IF EXISTS product_match;
        CREATE TABLE product_match (chain TEXT, external_sku TEXT, ean TEXT, score REAL, method TEXT,
                                    PRIMARY KEY (chain, external_sku));
        DROP TABLE IF EXISTS unit_price;
        CREATE TABLE unit_price (chain TEXT, external_sku TEXT, unit_price REAL, basis TEXT,
                                 PRIMARY KEY (chain, external_sku));
    """)
    summary = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["chain"] in EAN_CHAINS and r["ean"]:
            db.execute("INSERT OR REPLACE INTO product_match VALUES (?,?,?,?,?)",
                       (r["chain"], r["external_sku"], r["ean"], 1.0, "ean"))
            summary[r["chain"]]["ean"] += 1
        elif r["chain"] in NO_EAN_CHAINS:
            ean, score, status = match_row(r, by_size)
            summary[r["chain"]][status] += 1
            if status in ("auto", "revision"):
                db.execute("INSERT OR REPLACE INTO product_match VALUES (?,?,?,?,?)",
                           (r["chain"], r["external_sku"], ean, round(score, 3), status))
        up, basis = unit_price(r["sale_price"], r["title"])
        if up:
            db.execute("INSERT OR REPLACE INTO unit_price VALUES (?,?,?,?)",
                       (r["chain"], r["external_sku"], up, basis))
    db.commit()
    print("\nResultado por cadena:")
    for chain, d in summary.items():
        print(f"  {chain:<10}", dict(d))
    print("\nProductos comparables en N cadenas (con matching):")
    for n, c in db.execute("""SELECT k, COUNT(*) FROM (SELECT ean, COUNT(DISTINCT chain) k FROM product_match GROUP BY ean) GROUP BY k ORDER BY k"""):
        print(f"  {n} cadenas: {c}")
    db.close()


if __name__ == "__main__":
    main()
