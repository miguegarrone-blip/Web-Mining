import re
from topics import norm
NEG="murio muerte muertes muerto muertos asesin* crimen* robo* robos detenid* tragedia* accidente* herid* grave graves gravisimo crisis caida caen cae pierde perdio perdida* polemica escandalo denunci* acusa* acuso conflicto* guerra ataque* atac* violencia incidente* represion suspend* prohib* alerta riesgo amenaza* peligro pobreza desigualdad deuda* endeudamiento morosidad inflacion recorte* despido* quiebra cierra cierre paro huelga fraude estafa* corrup* derrota eliminad* lesion* lesionado expulsad* dolor tormenta* granizo temporal* incendio* explosion choque* vuelco atropell* abuso* femicidio* secuestro* balacera* balazos tiros narco* preso* condena* condenaron rechazo rechaz* critica* criticas critico fuerte duro durisimo tremendo escalo caos colapso falla* error* fracaso sufrio sufre victima* afecta* afectad* inundacion* sequia peor cuestion* repudio repudi* bronca enojo reclam* alarma sin gas sin luz robaron robar ladron* ladrones banda* usurpar atrincher* amenazo apunal* tension* crisis ruptura separacion separo denuncia desaparec* hallaron muerto naufrag* derrumb* descarril* aumenta suba subas sube tarifazo ajuste sobreprecio".split()
POS="gan* gano gana ganaron triunfo* victoria* campeon* campeona logro* logra celebr* fiesta record mejora mejoro crece crecen crecimiento recupera* recuper* premio* exito* gratis gratuito* gratuita* beneficio* apoyo homenaje sorpresa alegria avanza* aprueba* aprobo acuerdo* solidari* rescat* salvo salvaron esperanza innov* inaugur* inversion* invierte oportunidad* lider mejor mejores favorable destaca* destac* brilla* emocion* emotivo emotiva orgullo festej* festeja bienvenid* ayuda* donacion* reconocimiento reconocen distincion distinguido histor* despide? lanzan lanza lanzo nuevo? ".replace("?","").split()
# ampliado con los desacuerdos de la muestra validada a mano (2026-10-03)
NEG += "suben aumentaron aumentan aumento aumentos varado varados dramatic* sobrevivi* letal* letales inyecciones desalojo* insolito sismic* temblor*".split()
POS += "inolvidable inolvidables dedicatoria".split()
def comp(ws):
    ex=set(w for w in map(norm,ws) if not w.endswith("*") and w not in ("nuevo","despide","sin","gas","luz","fuerte","duro","grave"))
    st=tuple(w[:-1] for w in map(norm,ws) if w.endswith("*"))
    return ex,st
NE,NS=comp(NEG);PE,PS=comp(POS)
def tone_dict(title):
    toks=re.findall(r"[a-z0-9]+",norm(title))
    n=sum(1 for t in toks if t in NE or t.startswith(NS));p=sum(1 for t in toks if t in PE or t.startswith(PS))
    sc=p-n
    return "p" if sc>0 else ("n" if sc<0 else "0")
ENT={
"Javier Milei":["milei"],"Pablo Javkin":["javkin"],"Maximiliano Pullaro":["pullaro"],"Cristina Kirchner":["cristina kirchner","cristina fernandez","cfk"],
"Axel Kicillof":["kicillof"],"Patricia Bullrich":["bullrich"],"Luis Caputo":["caputo"],"Mauricio Macri":["macri"],"Sergio Massa":["massa"],"Victoria Villarruel":["villarruel"],
"Lionel Messi":["messi"],"Papa León XIV":["papa leon","leon xiv","el papa","visita del papa","visita papal"],"Donald Trump":["trump"],
"Rosario Central":["rosario central","canalla","canallas","central"],"Newell's":["newells","newell","leproso","leprosos","lepra"],"Boca":["boca juniors","boca"],"River":["river plate","river"],"Racing":["racing"],
"Selección Argentina":["seleccion argentina","la seleccion","scaloni"],"AFA":["afa","tapia"],
"BCRA":["bcra","banco central"],"FMI":["fmi","fondo monetario"],"YPF":["ypf"],"Mercado Libre":["mercado libre","mercadolibre"],"Uber":["uber","didi"],"ANSES":["anses","ansés"],
"Gobierno nacional":["gobierno nacional","casa rosada","gobierno de milei"],"Gobierno de Santa Fe":["gobierno santafesino","gobierno de santa fe","gobierno provincial"],"Municipalidad de Rosario":["municipalidad de rosario","municipalidad","intendente","concejo"],
"Universidades":["universidad*","universidades","uba"],"CGT":["cgt"],"Policía":["policia","policial"],
}
_pat={k:re.compile(r"(?<![a-z0-9])(?:"+"|".join(re.escape(norm(a)).replace(r"\*","[a-z]*") for a in al)+r")(?![a-z0-9])") for k,al in ENT.items()}
def ents(title):
    n=norm(title);out=[k for k,p in _pat.items() if p.search(n)]
    if "Rosario Central" in out and ("central cordoba" in n or "banco central" in n or "central norte" in n): out.remove("Rosario Central")
    if "Rosario Central" in out and "BCRA" in out and "banco central" in n: out.remove("Rosario Central")
    return out


# ---------- modelo entrenado (regresion logistica, ver tono_entrenar.py) ----------
import json, os
_M = None
def _modelo():
    global _M
    if _M is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_tono.json")
        try: _M = json.load(open(p, encoding="utf-8"))
        except Exception: _M = False
    return _M
_STOP = set("de la el en y a los las un una por con para que del al se su sus es lo como mas sobre tras ante este esta ya no si le les o u e entre hasta desde sin".split())
def _toks(t): return [w for w in re.findall(r"[a-z0-9]+", norm(t)) if len(w) >= 3 and w not in _STOP and not w.isdigit()]
def feats(t):
    ws = _toks(t); f = {w: 1.0 for w in set(ws)}
    for a, b in zip(ws, ws[1:]): f["%s_%s" % (a, b)] = 1.0
    f["__dict_" + tone_dict(t)] = 1.0
    return f
_MB = None
def _modelo_bert():
    global _MB
    if _MB is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_tono_bert.json")
        try: _MB = json.load(open(p, encoding="utf-8"))
        except Exception: _MB = False
    return _MB
def tone(title, pb=None):
    """tono n/0/p. Con pb (probabilidades [neg, neu, pos] de XLM-RoBERTa, ver bert.py) usa el modelo combinado;
    sin pb, la regresion logistica solo con palabras"""
    m = _modelo_bert() if pb else _modelo()
    if not m: return tone_dict(title)
    f = feats(title)
    if pb: f.update({"__bert_n": 3 * pb[0], "__bert_0": 3 * pb[1], "__bert_p": 3 * pb[2]})
    z = {c: m["B"][c] + sum(m["W"][c].get(k, 0.0) * v for k, v in f.items()) for c in ("n", "0", "p")}
    return max(z, key=z.get)


# ---------- cebo (clickbait): rasgos de titulo que buscan el clic mas que informar ----------
# Cada rasgo presente suma 1. Con 2 o mas se considera titulo "cebo". Ver tambien la "alarma" en build.py:
# titulo negativo cuando la bajada (el resumen de la propia nota) no lo es.
_CEBO = {
 "pregunta": re.compile(r"[?¿]"),
 "exclamacion": re.compile(r"[!¡]"),
 "exagera": re.compile(r"\b(?:impactante|insolito|increible|bomba|escandalo|escandaloso|furia|brutal|picante|tremend[oa]|terrible|dramatic[oa]|polemic[oa]|explosiv[oa]|estallo|exploto|durisim[oa]|lapidari[oa]|contundente|sin filtro|filtr(?:o|aron)|destapo|desopilante|letal|alarmante|shock|viral|furor|bochorn\w*|escandal\w*|bombazo|inesperad[oa]|sorpresiv[oa])\b"),
 "intriga": re.compile(r"(?:^|[\s:.,\"“])(?:lo que|la razon|el motivo|el truco|el secreto|la verdad|nadie|esto es|asi (?:es|fue|quedo|son|luce)|que es|por que|quien es|quienes son|cual es|cuales son|como (?:es|hacer|saber|evitar)|el dato|la clave|lo que (?:hay|tenes|nadie))\b"),
 "segunda_persona": re.compile(r"\b(?:tenes|podes|debes|sabias|mira|descubri|enterate|conoce|evita|hace esto|tu|vos)\b"),
 "lista": re.compile(r"^(?:las?|los)?\s*\d{1,2}\s+(?:claves|cosas|razones|consejos|trucos|errores|alimentos|senales|pasos|formas|motivos|datos|lugares|frases|preguntas|beneficios|habitos)\b"),
}
def cebo(title):
    n = norm(title)
    return sum(1 for rx in _CEBO.values() if rx.search(n if rx.pattern[0] != "[" else title))
_NOMBRE_CEBO = {"pregunta": "pregunta", "exclamacion": "exclamación", "exagera": "adjetivo exagerado", "intriga": "intriga",
                "segunda_persona": "segunda persona", "lista": "lista"}
def cebo_rasgos(title):
    """nombres de los rasgos de cebo presentes en el titulo (para mostrarlos en el tablero)"""
    n = norm(title)
    return [_NOMBRE_CEBO[k] for k, rx in _CEBO.items() if rx.search(n if rx.pattern[0] != "[" else title)]
