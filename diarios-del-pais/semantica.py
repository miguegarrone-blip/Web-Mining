"""Embeddings de oraciones (titulo + bajada) para "notas parecidas" y la busqueda por significado del tablero.
Modelo: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (multilingue, 384 dimensiones, ~120 MB).
Se usa transformers directo con mean pooling + normalizacion L2 (igual que sentence-transformers y que
transformers.js con {pooling:"mean", normalize:true}), asi los vectores de Python y del navegador son comparables.
Si torch/transformers no estan, disponible() devuelve False y el tablero sale sin notas parecidas."""
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_JS = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"   # el mismo modelo exportado a ONNX para transformers.js
DIM = 384
_m = None

def disponible():
    global _m
    if _m is None:
        try:
            import torch, numpy  # noqa: F401
            from transformers import AutoTokenizer, AutoModel
            _m = (AutoTokenizer.from_pretrained(MODELO), AutoModel.from_pretrained(MODELO).eval())
        except Exception as e:
            print("embeddings no disponibles, el tablero sale sin notas parecidas:", str(e)[:120])
            _m = False
    return bool(_m)

def texto(titulo, bajada):
    return titulo + (". " + bajada if bajada else "")

def vectores(textos, lote=64):
    """matriz numpy float32 (n, 384) con filas de norma 1, en el mismo orden que textos"""
    import torch, numpy as np
    tok, mod = _m
    out = []
    with torch.inference_mode():
        for i in range(0, len(textos), lote):
            enc = tok(list(textos[i:i + lote]), padding=True, truncation=True, max_length=128, return_tensors="pt")
            h = mod(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
            v = (h * m).sum(1) / m.sum(1).clamp(min=1e-9)                       # mean pooling sobre los tokens reales
            out.append(torch.nn.functional.normalize(v, dim=1).numpy())
    return np.concatenate(out) if out else np.zeros((0, DIM), np.float32)

def a_blob(v):                # se guarda en la base como BLOB float16 (768 bytes por nota)
    import numpy as np
    return np.asarray(v, np.float16).tobytes()

def de_blob(b):
    import numpy as np
    return np.frombuffer(b, np.float16).astype(np.float32)

def guardar_bin(ruta, hashes, M):
    """emb.bin para la busqueda por significado del navegador (se baja solo si el usuario activa el interruptor):
    "EMB1" | n (uint32 LE) | dim (uint32 LE) | n hashes de 8 bytes (el campo h de cada nota, en hex) | n x dim int8.
    Cada vector se escala a int8 por su maximo absoluto; el navegador lo vuelve a normalizar, asi que la escala no hace falta."""
    import numpy as np, struct
    M = np.asarray(M, np.float32)
    q = np.round(M / np.maximum(np.abs(M).max(1, keepdims=True), 1e-9) * 127).astype(np.int8)
    with open(ruta, "wb") as f:
        f.write(b"EMB1" + struct.pack("<II", len(hashes), M.shape[1]))
        f.write(b"".join(bytes.fromhex(h) for h in hashes))
        f.write(q.tobytes())

def vecinos(M, medios, k=5, umbral=0.7, caida=0.15):
    """para cada fila de M (normalizadas), hasta k notas de OTROS medios con similitud coseno >= umbral,
    a lo sumo una por medio (la mas parecida de cada uno). Si la mejor es muy parecida (la misma noticia),
    se descartan las que quedan a mas de `caida` de ella (suelen ser de otro tema). Devuelve [[(j, sim), ...], ...]
    El umbral 0.7 salio de mirar ejemplos: con este modelo, entre 0.5 y 0.65 aparecen muchas notas que solo
    comparten el genero (policiales, agenda cultural), no la noticia."""
    import numpy as np
    S = M @ M.T
    med = np.asarray(medios)
    S[med[:, None] == med[None, :]] = -1                                   # mismo medio (incluye la diagonal)
    res = []
    for i in range(len(M)):
        orden = np.argsort(-S[i])
        vis, fila = set(), []
        for j in orden:
            s = S[i, j]
            if s < umbral or len(fila) == k or (fila and s < fila[0][1] - caida): break
            if medios[j] in vis: continue
            vis.add(medios[j]); fila.append((int(j), float(s)))
        res.append(fila)
    return res
