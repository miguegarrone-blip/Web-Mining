"""Entrena y evalua clasificadores de tono sobre las notas clasificadas a mano.
Solo libreria estandar. Genera modelo_tono.json (si mejora) y calibracion.json."""
import json, os, re, math, random, sqlite3
from collections import Counter, defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
import nlp
from topics import norm

# ---------- etiquetas de la muestra de 300 (criterio de Claude) ----------
TENS = """p 0 n 0 0 n n n n p | p 0 n 0 0 p p 0 n p | 0 0 n 0 p 0 0 p 0 0 | n 0 0 n 0 0 n 0 p 0 | p n 0 p 0 0 0 n n n |
n p p 0 0 n p n n n | n 0 0 n 0 p n n n n | n 0 p p p n 0 0 0 p | 0 n n 0 n n n 0 0 n | 0 0 0 n 0 0 n p n 0 |
0 n p 0 0 p n p n 0 | p 0 0 n n n n 0 n 0 | 0 n 0 p n p 0 0 0 0 | n n 0 0 p n 0 0 0 n | n 0 0 n 0 0 0 n 0 p |
0 0 p 0 n p 0 0 n n | 0 n 0 p 0 p 0 0 0 n | 0 0 0 0 0 0 0 0 0 0 | n n p 0 0 n n n 0 0 | 0 n 0 p 0 0 n p n n |
p 0 n n 0 0 p p 0 0 | 0 p p n p 0 p 0 0 0 | n n 0 n 0 0 n 0 0 0 | n 0 p n n n 0 p p p | 0 p 0 n 0 0 n p n n |
0 0 p n 0 0 0 0 n n | 0 0 0 n n n 0 0 n 0 | p p n 0 0 p n p p 0 | n 0 0 0 0 0 0 0 n 0 | 0 0 0 n 0 0 0 p n 0"""
mias300 = [t for t in TENS.replace("|", " ").split()]
assert len(mias300) == 300, len(mias300)

muestra = json.load(open(os.path.join(AQUI, "muestra_300.json"), encoding="utf-8"))
LB = json.load(open(os.path.join(AQUI, "labels.json"), encoding="utf-8"))
db = sqlite3.connect(os.path.join(os.environ.get("DATA_DIR", AQUI), "historico.db"))

# ---------- conjunto etiquetado: (titulo, clase, origen) ----------
DATA, vistos = [], set()
for m, e in zip(muestra, mias300):
    DATA.append((m["t"], e, "mias300")); vistos.add(m["u"])
for u, (k, s) in LB.items():
    if u in vistos: continue
    r = db.execute("select titulo from items where url=?", (u,)).fetchone()
    if r: DATA.append((r[0], s, "previas")); vistos.add(u)
print("etiquetadas:", len(DATA), dict(Counter(c for _, c, _ in DATA)))

# ---------- poblacion: clase segun diccionario viejo, para reponderar el muestreo estratificado ----------
pop = Counter(nlp.tone_dict(t) for (t,) in db.execute("select titulo from items"))
mues = Counter(nlp.tone_dict(t) for t, _, _ in DATA)
PESO = {k: pop[k] / mues[k] for k in pop if mues[k]}
print("poblacion segun diccionario:", dict(pop), "| peso por clase:", {k: round(v, 1) for k, v in PESO.items()})

# ---------- caracteristicas ----------
STOP = set("de la el en y a los las un una por con para que del al se su sus es lo como mas sobre tras ante este esta ya no si le les o u e entre hasta desde sin".split())
def toks(t): return [w for w in re.findall(r"[a-z0-9]+", norm(t)) if len(w) >= 3 and w not in STOP and not w.isdigit()]
def feats(t):
    f = Counter(toks(t))
    f = {w: 1.0 for w in f}                      # presencia
    ws = toks(t)
    bi = ["%s_%s" % (a, b) for a, b in zip(ws, ws[1:])]
    for b in bi: f[b] = 1.0
    d = nlp.tone_dict(t)
    f["__dict_" + d] = 1.0                       # lo que dice el diccionario actual
    return f
CL = ["n", "0", "p"]

# ---------- modelos ----------
def train_lr(X, y, w, epochs=60, lr=0.2, l2=0.01, seed=0):
    rnd = random.Random(seed); W = {c: defaultdict(float) for c in CL}; B = {c: 0.0 for c in CL}
    idx = list(range(len(X)))
    for ep in range(epochs):
        rnd.shuffle(idx)
        for i in idx:
            z = {c: B[c] + sum(W[c][k] * v for k, v in X[i].items()) for c in CL}
            m = max(z.values()); e = {c: math.exp(z[c] - m) for c in CL}; s = sum(e.values())
            for c in CL:
                g = (e[c] / s) - (1.0 if y[i] == c else 0.0)
                B[c] -= lr * g * w[i]
                for k, v in X[i].items(): W[c][k] -= lr * (g * v * w[i] + l2 * W[c][k])
    return W, B
def pred_lr(model, f):
    W, B = model; z = {c: B[c] + sum(W[c].get(k, 0.0) * v for k, v in f.items()) for c in CL}
    return max(z, key=z.get), z
def train_nb(X, y):
    cnt = {c: Counter() for c in CL}; n = Counter(y); V = set()
    for f, c in zip(X, y):
        for k in f:
            if not k.startswith("__"): cnt[c][k] += 1; V.add(k)
    return cnt, n, V
def pred_nb(m, f):
    cnt, n, V = m; N = sum(n.values()); best, bs = None, -1e18
    for c in CL:
        tot = sum(cnt[c].values()); s = math.log((n[c] + 1) / (N + 3))
        for k in f:
            if k.startswith("__"): continue
            s += math.log((cnt[c][k] + 0.5) / (tot + 0.5 * len(V) + 1))
        if s > bs: best, bs = c, s
    return best

# ---------- validacion cruzada estratificada (5 pliegues) ----------
rnd = random.Random(5); idx = list(range(len(DATA))); rnd.shuffle(idx)
folds = [idx[i::5] for i in range(5)]
X = [feats(t) for t, _, _ in DATA]; Y = [c for _, c, _ in DATA]
Wt = [PESO.get(nlp.tone_dict(t), 1.0) for t, _, _ in DATA]
mean_w = sum(Wt) / len(Wt)
Wn = [w / mean_w for w in Wt]       # pesos normalizados para entrenar

def evalua(nombre, predictor):
    P = [None] * len(DATA)
    for k in range(5):
        te = folds[k]; tr = [i for j in range(5) if j != k for i in folds[j]]
        pf = predictor([X[i] for i in tr], [Y[i] for i in tr], [Wn[i] for i in tr])
        for i in te: P[i] = pf(X[i])
    ok = sum(1 for i in range(len(DATA)) if P[i] == Y[i]) / len(DATA)
    okw = sum(Wt[i] for i in range(len(DATA)) if P[i] == Y[i]) / sum(Wt)
    # recall de negativos
    neg = [i for i in range(len(DATA)) if Y[i] == "n"]; rec = sum(1 for i in neg if P[i] == "n") / len(neg)
    # reparto predicho vs real (ponderado)
    tw = sum(Wt); real = {c: sum(Wt[i] for i in range(len(DATA)) if Y[i] == c) / tw for c in CL}
    prd = {c: sum(Wt[i] for i in range(len(DATA)) if P[i] == c) / tw for c in CL}
    print(f"{nombre:34} acierto {ok:.0%} | ponderado {okw:.0%} | recall neg {rec:.0%} | reparto predicho n/0/p {prd['n']:.0%}/{prd['0']:.0%}/{prd['p']:.0%} (real {real['n']:.0%}/{real['0']:.0%}/{real['p']:.0%})")
    return P, ok

evalua("diccionario actual", lambda Xt, yt, wt: (lambda f: nlp.tone_dict_only_from_feats(f)) if False else (lambda f: [c for c in CL if "__dict_" + c in f][0]))
_, a_nb = evalua("Naive Bayes", lambda Xt, yt, wt: (lambda m: (lambda f: pred_nb(m, f)))(train_nb(Xt, yt)))
res = {}
for l2 in (0.003, 0.01, 0.03):
    nombre = f"Regresion logistica l2={l2}"
    P, a = evalua(nombre, lambda Xt, yt, wt, l2=l2: (lambda m: (lambda f: pred_lr(m, f)[0]))(train_lr(Xt, yt, wt, l2=l2)))
    res[l2] = (a, P)
mejor = max(res, key=lambda k: res[k][0])
print("mejor l2:", mejor, f"({res[mejor][0]:.0%})")

# ---------- calibracion con las predicciones fuera de muestra del mejor modelo ----------
P = res[mejor][1]; M = {p: {c: 0.0 for c in CL} for p in CL}; Ncnt = Counter()
for i in range(len(DATA)):
    M[P[i]][Y[i]] += Wt[i]; Ncnt[P[i]] += 1
cal = {}
for p in CL:
    tot = sum(M[p].values())
    cal[p] = {"n": Ncnt[p], "p": {c: (M[p][c] / tot if tot else 0.0) for c in CL}}
print("calibracion P(real | predicho):", {p: {c: round(v, 2) for c, v in cal[p]["p"].items()} for p in CL}, "n:", dict(Ncnt))
json.dump({"cal": cal, "muestra": len(DATA), "acierto_cv": res[mejor][0]}, open(os.path.join(AQUI, "calibracion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- modelo final con todo y guardado (poda: solo pesos relevantes) ----------
W, B = train_lr(X, Y, Wn, l2=mejor)
out = {"B": B, "W": {c: {k: round(v, 4) for k, v in W[c].items() if abs(v) >= 0.05} for c in CL}, "acierto_cv": res[mejor][0], "muestra": len(DATA)}
json.dump(out, open(os.path.join(AQUI, "modelo_tono.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("modelo_tono.json guardado:", sum(len(v) for v in out["W"].values()), "pesos")
