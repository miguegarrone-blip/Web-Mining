"""Probabilidades de sentimiento de XLM-RoBERTa (cardiffnlp/twitter-xlm-roberta-base-sentiment) para el modelo de tono.
Son una entrada mas del modelo combinado (ver tono_bert_eval.py y nlp.tone). Si torch/transformers no estan
instalados, disponible() devuelve False y el pipeline sigue con el modelo de tono anterior."""
MODELO = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
_pipe = None

def disponible():
    global _pipe
    if _pipe is None:
        try:
            from transformers import pipeline
            _pipe = pipeline("sentiment-analysis", model=MODELO, top_k=None, truncation=True, max_length=128)
        except Exception as e:
            print("BERT no disponible, se usa el modelo de tono anterior:", str(e)[:120])
            _pipe = False
    return bool(_pipe)

def probas(textos, lote=32):
    """[[p_neg, p_neu, p_pos], ...] en el mismo orden que textos"""
    out = []
    if not textos: return out                     # transformers falla con una lista vacia
    for r in _pipe(list(textos), batch_size=lote):
        d = {z["label"]: z["score"] for z in r}
        out.append([round(d["negative"], 4), round(d["neutral"], 4), round(d["positive"], 4)])
    return out

def a_texto(p): return ",".join("%.4f" % x for x in p)        # se guarda en la base como "n,0,p"
def de_texto(s): return [float(x) for x in s.split(",")] if s else None
