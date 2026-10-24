"""Reconocimiento de entidades (NER) con spaCy para descubrir personas e instituciones que no estan en el
diccionario fijo de nlp.ENT. Modelo: es_core_news_md (~40 MB, vectores de palabras): en titulares argentinos
marca bastante menos ruido que el sm (que toma "Tambien", "Segun" o "Ademas" como personas y a "Milei" como lugar)
y tarda casi lo mismo. Si spaCy o el modelo no estan instalados, disponible() devuelve False y el pipeline sigue
sin la columna ner (igual que bert.py)."""
import re
from nlp import ENT, _pat
from topics import norm

MODELOS = ("es_core_news_md", "es_core_news_sm")   # el primero que este instalado
_nlp = None

def disponible():
    global _nlp
    if _nlp is None:
        _nlp = False
        try:
            import spacy
            for m in MODELOS:
                try:
                    # solo hace falta el NER: se apagan el parser y demas componentes para ir mas rapido
                    _nlp = spacy.load(m, exclude=["parser", "lemmatizer", "morphologizer", "attribute_ruler", "tagger", "senter"]); break
                except OSError: continue
            if not _nlp: print("NER no disponible: falta el modelo de spaCy (", ", ".join(MODELOS), ")")
        except Exception as e:
            print("NER no disponible:", str(e)[:120])
    return bool(_nlp)

# ---------- limpieza ----------
# nombres de medios y secciones (aparecen en bajadas y firmas); build.py suma los de su lista de medios
MEDIOS = {norm(x) for x in """TN;Olé;Clarín;La Nación;Infobae;Perfil;Ámbito;Página/12;Pagina 12;El Cronista;El Destape;C5N;A24;El Trece;
Canal 26;Cadena 3;Radio Mitre;Mitre;Radio 10;Continental;La Capital;Rosario3;Rosario 3;El Ciudadano;Conclusión;Rosarioplus;Aire de Santa Fe;
Aire Digital;El Litoral;La Voz;Los Andes;La Gaceta;El Tribuno;El Día;Río Negro;El Chubut;Diario Chaco;Misiones Online;Elonce;Eldoce;
La Nueva;Uno;Noticias Argentinas;NA;Télam;Telam;Telefe;América;America TV;TyC Sports;TyC;ESPN;Fox Sports;DSports;Google;Google News;
WhatsApp;Instagram;Facebook;YouTube;TikTok;X;Twitter;El País;El Mundo;CNN;BBC;EFE;AFP;Reuters;AP;Europa Press;Infocielo;Canal 13;
Radio Con Vos;Urbana Play;LN+;Big Bang News;Minuto Uno;Crónica;Diario Popular;Mundo Deportivo;Marca;AS""".replace("\n", "").split(";")}
_MESES = "enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre"
_DIAS = "lunes martes miercoles jueves viernes sabado domingo hoy ayer manana"
# palabras sueltas con mayuscula que el modelo confunde con nombres: comienzo de oracion, cargos, genericos, secciones del sitio
GENERICOS = set((_MESES + " " + _DIAS + """ gobierno gobiernos estado justicia policia fiscalia presidente presidenta gobernador gobernadora
intendente intendenta ministro ministra ministerio diputado diputada diputados senador senadora senado juez jueza tribunal camara
seleccion club equipo provincia ciudad pais nacion municipio municipalidad concejo legislatura congreso corte poder ejecutivo
tambien segun ademas asi como que cual cuando donde quien tras ante hasta desde mira mire seguilo seguila segui conoce entera enterate
leer ver video videos foto fotos fotogaleria galeria audio mapa vivo envivo urgente ultimo ultima ultimas ultimo momento minuto
espectaculos policiales policiales cartelera clasificados funebres deportes sociedad politica economia mundo internacionales opinion
informacion general cultura tecnologia salud turismo clima tiempo horoscopo loterias quiniela sorteo resultados resultado fixture
sitio portada home inicio newsletter suscribite suscripcion registrate publicidad contacto mas menos lo la el los las un una
ocurrio llego dijo fue hay hubo tengo tenes academia gol goles partido torneo campeonato fecha primera nacional liga copa
ia ai dt pp grosso libra dios santo san santa feliz atletico deportivo real inter clausura apertura profesional reserva division serie
paso dolar especialistas expertos vecinos leo podes consulta descubri elegi accede escucha proba sumate anotate business empresas reperfilar
lobo taladro millonario millonarios calamar xeneize xeneizes pincha tatengue sabalero globo halcon bicho tomba colchonero pumas merengue
blaugrana granate decano tiburon funebrero cuervo cuervos gallo matador pirata ciclon fortinero tricolor albiceleste celeste mls atp wta nba nfl
uefa motogp f1 gp premier league champions libertadores sudamericana mundial formula turismo carretera""").split())
_CARGOS = set("""presidente presidenta expresidente expresidenta vicepresidente vicepresidenta gobernador gobernadora exgobernador
intendente intendenta ministro ministra exministro diputado diputada senador senadora juez jueza fiscal dt tecnico entrenador
jugador delantero arquero defensor volante piloto cantante actor actriz conductor conductora periodista papa senor senora don dona
dr dra lic ing""".split())
_ART = {"el", "la", "los", "las", "un", "una"}
_COMPET = {"liga", "copa", "torneo", "serie", "premier", "campeonato", "gran", "gp", "mundial", "formula", "juegos", "superliga", "fecha", "clasico"}
_CONECT = {"de", "del", "la", "las", "los", "da", "do", "dos", "y", "e", "von", "van", "di"}

# alias del diccionario (sin comodines ni alias genericos) -> nombre canonico, para unificar con nlp.ENT
_GEN_ALIAS = {"central", "el papa", "visita del papa", "visita papal", "municipalidad", "intendente", "concejo", "policia", "policial",
              "gobierno provincial", "la seleccion", "canalla", "canallas", "leproso", "leprosos", "lepra"}
ALIAS = {}
for k, al in ENT.items():
    ALIAS[norm(k)] = k
    for a in al:
        if "*" not in a and norm(a) not in _GEN_ALIAS: ALIAS[norm(a)] = k
ALIAS.update({"leo messi": "Lionel Messi", "javier gerardo milei": "Javier Milei", "cristina fernandez de kirchner": "Cristina Kirchner"})

def en_diccionario(nombre):
    """True si el nombre es una figura de nlp.ENT (canonico o alias, coincidencia completa)"""
    n = norm(nombre)
    return n in ALIAS or nombre in ENT or any(p.fullmatch(n) for p in _pat.values())

def limpiar(texto, excluir=frozenset()):
    """normaliza una entidad: saca cargos y articulos del comienzo, conectores sueltos y ruido.
    Devuelve el nombre limpio o '' si no sirve"""
    t = re.sub(r"\s+", " ", texto.strip(" \t\n\"'“”‘’«»:;,.-–—()[]¿?¡!|/")).strip()
    t = re.sub(r"'s$|’s$", "", t)
    ws = t.split(" ")
    if norm(t) in MEDIOS: return ""
    while ws and (norm(ws[0]) in _CARGOS or (norm(ws[0]) in _ART and len(ws) > 1 and (ws[1][:1].islower() or norm(ws[1]) in _CARGOS))):
        ws = ws[1:]                                              # "El presidente Javier Milei" -> "Javier Milei" (pero "La Plata" queda)
    while ws and norm(ws[-1]) in _CONECT: ws = ws[:-1]          # "Torneo Clausura de" -> "Torneo Clausura"
    if not ws or len(ws) > 4: return ""                          # mas de 4 palabras: casi siempre menues del sitio
    t = " ".join(ws); n = norm(t)
    if len(re.sub(r"[^a-z0-9]", "", n)) < 2 or n in excluir or n in MEDIOS: return ""
    if not t[0].isupper() and not t[0].isdigit(): return ""      # entidad que empieza en minuscula ("llegó", "río Paraná")
    if re.search(r"\d", t) and not re.search(r"[A-Za-zÀ-ÿ]{3}", t): return ""
    if any(w.isupper() and len(w) > 5 for w in ws): return ""     # palabras en mayusculas sostenidas: volantas ("GROSSO", "URGENTE")
    lleno = [w for w in ws if norm(w) not in _CONECT]
    if not lleno or norm(lleno[0]) in _COMPET: return ""                       # competencias: "La Liga de España", "Copa Libertadores", "Gran Premio de ..."
    if all(norm(w) in GENERICOS for w in lleno): return ""          # todas genericas: "Gobierno", "La Justicia", "Primera Nacional"
    if not all(w[:1].isupper() or w[:1].isdigit() for w in lleno): return ""   # "El procedimiento", "Ladrón y mentiroso"
    return ALIAS.get(n, t)                                       # alias conocido -> nombre canonico del diccionario

def extraer(textos, excluir=(), lote=128, etiquetas=("PER", "ORG")):
    """lista (misma longitud que textos) de listas de entidades limpias y sin duplicados. Ademas de PER y ORG,
    un LOC que coincide con una figura del diccionario se conserva (el modelo a veces marca "Milei" como lugar)"""
    ex = frozenset(norm(x) for x in excluir)
    out = []
    for d in _nlp.pipe(textos, batch_size=lote):
        vis, r = set(), []
        for e in d.ents:
            if e.label_ not in etiquetas and e.label_ != "LOC": continue
            c = limpiar(e.text, ex)
            if not c or (e.label_ not in etiquetas and c not in ENT): continue
            k = norm(c)
            if k not in vis: vis.add(k); r.append(c)
        out.append(r)
    return out

def unificar(conteo):
    """conteo {nombre: menciones} -> {nombre: nombre_unificado}. Junta variantes de mayusculas/tildes
    ("Flávio Bolsonaro" / "Flavio Bolsonaro", se queda con la mas frecuente) y formas cortas con la forma mas larga
    vista que empieza o termina igual ("Colapinto" -> "Franco Colapinto", "Lula" -> "Lula da Silva",
    "Martínez de Giorgi" -> "Marcelo Martínez de Giorgi") cuando el candidato es claro: junta al menos 2/3 de las
    menciones de los candidatos y no es mucho menos frecuente que la forma corta (evita "Meloni" -> otro Meloni)"""
    grupos = {}
    for n, c in conteo.items(): grupos.setdefault(norm(n), []).append((c, n))
    rep = {k: max(v)[1] for k, v in grupos.items()}                       # forma mas frecuente de cada clave
    tot = {k: sum(c for c, _ in v) for k, v in grupos.items()}
    # forma corta (prefijo o sufijo de palabras completas) -> formas mas largas que la contienen
    cand = {}
    for k in grupos:
        ws = k.split()
        for i in range(1, len(ws)):
            for c in (" ".join(ws[:i]), " ".join(ws[i:])):
                if len(c) >= 4 and c in grupos: cand.setdefault(c, []).append(k)
    dest = {}
    for k in sorted(grupos, key=lambda z: -len(z)):                       # primero las largas: los destinos ya estan resueltos
        d = k
        if k in cand and k not in ALIAS:
            cs = sorted(cand[k], key=lambda z: -tot[z]); s = sum(tot[z] for z in cs); c0 = cs[0]
            if tot[c0] >= 2 * (s - tot[c0]) and tot[c0] >= 3 and 3 * tot[c0] >= tot[k]: d = dest.get(c0, c0)
        dest[k] = d
    return {n: rep[dest[norm(n)]] for n in conteo}
