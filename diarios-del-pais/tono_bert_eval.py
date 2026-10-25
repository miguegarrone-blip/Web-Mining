"""Compara modelos de tono sobre los titulares etiquetados a mano (muestra_300.json + tuyas_40.json).
Uso: python tono_bert_eval.py   (requiere torch, transformers, pysentimiento y scikit-learn; ver requirements-bert.txt)

Modelos:
  1. regresion logistica actual (nlp.feats) con validacion cruzada
  2. pysentimiento (RoBERTuito, tuits en espanol) sin entrenar
  3. XLM-RoBERTa de sentimiento (cardiffnlp, multilingue) sin entrenar
  4. embeddings de RoBERTuito + regresion logistica entrenada con nuestras etiquetas
  5. combinado: rasgos del modelo actual + probabilidades de pysentimiento
Las etiquetas siguen el criterio de la planilla de validacion: el hecho le hace bien o mal a los involucrados.
Si existe labels_activo.json (aprendizaje activo, ver tono_activo.py) esas etiquetas se suman a las 340 originales y
se compara el modelo 6 entrenado sin ellas ("antes") y con ellas ("despues") sobre los mismos pliegues del conjunto ampliado."""
import json, os, re, random
from collections import Counter
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction import DictVectorizer
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import accuracy_score, f1_score, recall_score, confusion_matrix
from scipy.sparse import hstack, csr_matrix
import nlp, tono_activo

AQUI = os.path.dirname(os.path.abspath(__file__))
CL = ["n", "0", "p"]

# ---------- datos ----------
U, T, Y, ORIG = tono_activo.etiquetadas()           # los 340 originales + labels_activo.json si existe
print("titulares etiquetados:", len(T), dict(Counter(Y.tolist())), f"({(~ORIG).sum()} de aprendizaje activo)" if (~ORIG).any() else "")

# la muestra de 300 se estratifico por el diccionario viejo: se repondera para estimar el acierto en la poblacion real
import sqlite3
pob = Counter(nlp.tone_dict(t) for (t,) in sqlite3.connect(os.path.join(os.environ.get("DATA_DIR", AQUI), "historico.db")).execute("SELECT titulo FROM items"))
POB = {k: v / sum(pob.values()) for k, v in pob.items()}
print("poblacion segun el diccionario:", {k: f"{v:.0%}" for k, v in POB.items()})
dic = [nlp.tone_dict(t) for t in T]
mc = Counter(dic); W = np.array([POB[d] / (mc[d] / len(T)) for d in dic])

skf = StratifiedKFold(5, shuffle=True, random_state=5)
def reporte(nombre, P, m=None):
    """m: mascara opcional para medir sobre un subconjunto (p. ej. solo los 340 originales)"""
    P = np.asarray(P); Y_, W_ = (Y, W) if m is None else (Y[m], W[m]); P = P if m is None else P[m]
    acc = accuracy_score(Y_, P); accw = float((W_ * (P == Y_)).sum() / W_.sum())
    f1 = f1_score(Y_, P, labels=CL, average="macro"); rn = recall_score(Y_, P, labels=["n"], average="macro")
    print(f"{nombre:44} acierto {acc:.0%} | ponderado {accw:.0%} | F1 macro {f1:.2f} | recall neg {rn:.0%}")
    return {"modelo": nombre, "acierto": round(acc, 3), "acierto_ponderado": round(accw, 3), "f1_macro": round(f1, 3), "recall_neg": round(rn, 3),
            "confusion": confusion_matrix(Y_, P, labels=CL).tolist()}
res = []

# ---------- 1. modelo actual ----------
dv = DictVectorizer(); Xlr = dv.fit_transform([nlp.feats(t) for t in T])
lr = LogisticRegression(C=3, max_iter=2000, class_weight="balanced")
res.append(reporte("1. regresion logistica actual (CV)", cross_val_predict(lr, Xlr, Y, cv=skf)))

# ---------- 2. pysentimiento ----------
from pysentimiento import create_analyzer
an = create_analyzer(task="sentiment", lang="es")
out = an.predict(T)
MAP = {"NEG": "n", "NEU": "0", "POS": "p"}
P2 = [MAP[o.output] for o in out]
PROB = np.array([[o.probas["NEG"], o.probas["NEU"], o.probas["POS"]] for o in out])
res.append(reporte("2. pysentimiento (sin entrenar)", P2))

# ---------- 3. XLM-RoBERTa ----------
import bert                      # el mismo modulo que usa build.py: probabilidades identicas en evaluacion y produccion
assert bert.disponible()
PROBX = np.array(bert.probas(T))
P3 = [CL[i] for i in PROBX.argmax(1)]
res.append(reporte("3. XLM-RoBERTa sentimiento (sin entrenar)", P3))

# ---------- 4. embeddings + regresion logistica ----------
import torch
tok, mod = an.tokenizer, an.model.base_model if hasattr(an.model, "base_model") else an.model
mod.eval(); E = []
with torch.no_grad():
    for i in range(0, len(T), 32):
        b = tok(T[i:i + 32], padding=True, truncation=True, max_length=64, return_tensors="pt")
        h = mod(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1)
        E.append(((h * m).sum(1) / m.sum(1)).numpy())
E = np.vstack(E)
res.append(reporte("4. embeddings RoBERTuito + reg. logistica (CV)", cross_val_predict(LogisticRegression(C=1, max_iter=3000, class_weight="balanced"), E, Y, cv=skf)))

# ---------- 5. combinado ----------
Xc = hstack([Xlr, csr_matrix(PROB * 3)]).tocsr()
res.append(reporte("5. combinado: actual + probas pysentimiento (CV)", cross_val_predict(LogisticRegression(C=3, max_iter=2000, class_weight="balanced"), Xc, Y, cv=skf)))
Xc = hstack([Xlr, csr_matrix(PROBX * 3)]).tocsr()
P6 = cross_val_predict(LogisticRegression(C=3, max_iter=2000, class_weight="balanced"), Xc, Y, cv=skf)
res.append(reporte("6. combinado: actual + probas XLM-R (CV)", P6))
X6 = Xc
Xc = hstack([Xlr, csr_matrix(PROB * 3), csr_matrix(PROBX * 3)]).tocsr()
res.append(reporte("7. combinado: actual + ambos BERT (CV)", cross_val_predict(LogisticRegression(C=3, max_iter=2000, class_weight="balanced"), Xc, Y, cv=skf)))
res.append(reporte("8. solo probas de ambos BERT (CV)", cross_val_predict(LogisticRegression(C=1, max_iter=2000, class_weight="balanced"), np.hstack([PROB, PROBX]), Y, cv=skf)))

# ---------- aprendizaje activo: antes (sin labels_activo) vs despues (con), mismos pliegues del conjunto ampliado ----------
# en cada pliegue "antes" entrena solo con los originales del lado de entrenamiento y "despues" con todo; ambos predicen
# los mismos titulares de prueba. Se mide sobre el conjunto ampliado, sobre los 340 originales y sobre los activos.
if (~ORIG).any():
    PA, PD = np.empty(len(Y), dtype=Y.dtype), np.empty(len(Y), dtype=Y.dtype)
    for tr, te in skf.split(X6, Y):
        PA[te] = tono_activo.modelo().fit(X6[tr[ORIG[tr]]], Y[tr[ORIG[tr]]]).predict(X6[te])
        PD[te] = tono_activo.modelo().fit(X6[tr], Y[tr]).predict(X6[te])
    print(f"--- aprendizaje activo: {ORIG.sum()} originales + {(~ORIG).sum()} activos ---")
    for nom, m in (("ampliado", None), ("340 originales", ORIG), ("activos", ~ORIG)):
        for cual, P in (("antes", PA), ("despues", PD)):
            r = reporte(f"6{'a' if cual == 'antes' else 'b'}. {cual} activo, sobre {nom} (CV)", P, m)
            r.update({"activo": cual, "conjunto": nom, "n": int(len(Y) if m is None else m.sum())}); res.append(r)

json.dump(res, open(os.path.join(AQUI, "tono_comparacion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("resultados en tono_comparacion.json")

# ---------- produccion: el modelo 6 (rasgos actuales + probas XLM-R) entrenado con todo ----------
# mismo formato que modelo_tono.json; las probas entran como rasgos __bert_n/__bert_0/__bert_p (x3, ver nlp.feats_bert)
fin = LogisticRegression(C=3, max_iter=2000, class_weight="balanced").fit(X6, Y)
nombres = list(dv.get_feature_names_out()) + ["__bert_n", "__bert_0", "__bert_p"]
# el acierto y la calibracion se miden solo sobre los originales: es la muestra representativa de la poblacion
# (los de aprendizaje activo se eligieron por dificiles y sesgarian ambos numeros hacia abajo)
ACC = round(accuracy_score(Y[ORIG], P6[ORIG]), 4)
modelo = {"B": {c: float(b) for c, b in zip(fin.classes_, fin.intercept_)},
          "W": {c: {k: round(float(w), 4) for k, w in zip(nombres, fila) if abs(w) >= 0.01} for c, fila in zip(fin.classes_, fin.coef_)},
          "bert": bert.MODELO, "acierto_cv": ACC, "muestra": len(T), "activos": int((~ORIG).sum())}
json.dump(modelo, open(os.path.join(AQUI, "modelo_tono_bert.json"), "w", encoding="utf-8"), ensure_ascii=False)
# calibracion P(real | predicho) con las predicciones fuera de muestra, ponderadas a la poblacion 
cal = {}
for pc in CL:
    sel = (P6 == pc) & ORIG; tot = W[sel].sum()
    cal[pc] = {"n": int(sel.sum()), "p": {c: float(W[sel & (Y == c)].sum() / tot) if tot else 0.0 for c in CL}}
json.dump({"cal": cal, "muestra": len(T), "acierto_cv": ACC, "modelo": "rasgos + XLM-RoBERTa", "activos": int((~ORIG).sum())},
          open(os.path.join(AQUI, "calibracion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("modelo_tono_bert.json y calibracion.json guardados:", sum(len(v) for v in modelo["W"].values()), "pesos")
