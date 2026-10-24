import re, unicodedata
def norm(t): return unicodedata.normalize("NFD", t.lower()).encode("ascii","ignore").decode()
# palabra* = prefijo; "dos palabras" = frase
TOPICS = {
"Política": "massa manzur galmarini villarruel cambiemos juntos ucr elecciones reelecto reelecta reformas paritaria legislativo milei gobierno congreso diputad* senad* senador* casa rosada oposicion dnu ley leyes gobernador pullaro kicillof javkin intendente concejo concejal* elecciones electoral candidat* partido politico pj peronismo libertad avanza lla macri cristina kirchner kirchnerismo bullrich caputo ministro* ministra* gabinete presidente president* funcionari* legislatura legislador* reforma veto sesion interpelacion carrio cattalini denuncio penalmente ucr radical* libertario* espert merino taccetta oficialismo presupuesto comision proyecto de ley diputada senadora bloque encuesta* votacion votar votos",
"Economía y finanzas": "euro blue ceo negocios industria* fabrica* planta* ventas pyme* energia petroleo mineria litio vaca muerta ganancia* perdidas quiebra concurso acindar directorio data centers datacenter* cierra cierre empresario* inflacionario costos dolar* inflacion riesgo pais salario* salarial* bcra tasa* deuda* endeudamiento morosidad jubilacion* jubilado* pension* aguinaldo precio* combustible* nafta rigi indec pbi mercado* bono* bonos impuesto* ahorro* credito* prestamo* banco* bancos economia economico* consumo canasta paritaria* aumento* tarifa* subsidio* auh ansés anses fmi inversion* exportacion* importacion* empresa* petrolera comercio*",
"Seguridad y policiales": "asesinad* atrincher* amenaz* apunal* muerto hallaron muerto encontraron muerto cuchillo denunciante denunciado acoso abusador* violador* secuestrad* tiroteo narcomenudeo detencion operativo asesinato* asesinaron crimen* homicidio* robo* robos ladron* ladrones detenid* detuvieron arrestad* policia policial* allanamiento* allanaron balacera* baleado* balazos tiros narco* narcotrafico banda* sicario* secuestro* abuso* abusar violacion* femicidio* usurpar usurpacion estafa* estafador* fisherton comisaria* gendarmeria prision* preso* presos condenado* condenaron imputado* aprehend* procesad* procesaron lavado bunker cocaina marihuana droga* golpearon golpeo agresion agredi* desaparecid* sospechos* investigan hallado hallada cadaver",
"Justicia": "juez* jueces fiscal* fiscales tribunal* camara federal indagatoria causa* juicio* justicia corte suprema fallo* sentencia* cautelar amparo querella declararon procesado*",
"Fútbol": "futbol futbolista* central canalla* newells newell leproso* lepra afa libertadores sudamericana seleccion scaloni messi mundial eliminatorias boca river racing independiente estudiantes gimnasia velez lanus talleres belgrano banfield huracan arbitro* var dt tecnico goleada gol goles penal hinchas hincha barra barrabrava clausura apertura amistoso supercopa liga profesional copa argentina primera division tabla de posiciones san lorenzo argentinos juniors rosario central copa de la liga fecha fifa infantino real madrid barcelona premier champions liverpool porto flamengo bayern juventus psg chelsea arsenal manchester inter milan colon union newell rosario central torneo mundial de clubes penales hinchada estadio kompany",
"Otros deportes": "atp wta djokovic alcaraz sinner verstappen colapinto norris rally benavides nba euroliga masters roland garros wimbledon dakar pilotos escuderia carrera* motociclismo tenis rugby basquet voley hockey moto motogp moto3 f1 formula automovilismo maraton ironman atletismo natacion ciclismo golf boxeo juegos olimpicos olimpico* padel running pilotos piloto pumas leones leonas",
"Cultura": "libro* feria del libro literatura escritor* escritora* obra teatro teatral museo muestra arte artista* musica musical recital* concierto* festival cine pelicula* documental exposicion rock danza baile cultura autor poeta",
"Espectáculos": "romance noviazgo casamiento embarazo celebrity masterchef topo gigio levinton pareja bailando cantante* cantautor* musico* rock vox dei video viral tiktoker hollywood paramount warner estreno disney actor actriz serie netflix streaming disney tele television programa conductor* conductora* farandula famoso* famosa* separacion mirtha moria granata robbie williams pareja show espectaculo* estreno* youtuber influencer reality martin fierro kaczka prandi ninci wanda nara pettinato kusnetzoff tinelli susana pampita china suarez tini lali bisbal charly garcia stallone rocky infidelidad expareja confesion confeso revelacion",
"Salud": "osteoporosis nutricion dieta obesidad diabetes sindrome salud mental sueño sueno ejercicio kinesiologia dolor sintoma* alimentacion salud hospital* medic* anmat vacuna* sarampion dengue virus enfermedad* cancer tratamiento* obra social paciente* clinica sanatorio epidemia brote gripe discapacidad pami farmacia* medicamento* infectologo ameba tumor operado operacion quirofano psicologia",
"Educación": "escuela* colegio* universidad* universitari* docente* maestro* alumno* educacion clases ciclo lectivo paro docente ctera beca* examen*",
"Clima y ambiente": "nevadas nieve granizada helada* ola calor smn servicio meteorologico lluvias tormentas clima pronostico tormenta* lluvia* granizo temporal* alerta calor frio ola sequia inundacion* ambiente ambiental* incendio* contaminacion microplasticos el nino viento nevada llovio lloverá llovera crecida creciente rayo rayos humedad temperatura* pronostico extendido",
"Transporte y ciudad": "boleto colectivo* transporte transito vial ruta* rutas obra* obras tren* subte aeropuerto vuelos aerolinea* uber didi taxi* taxista* peaje estacionamiento bondi movilidad semaforo* bache* municipal* municipalidad",
"Tecnología": "notebooklm chip* software ciberataque* algoritmo gemini claude samsung internet starlink bitcoin cripto* gadget* smartphone inteligencia artificial ia whatsapp celular* iphone apple google tecnologia app aplicacion* ciberseguridad hackeo hackers redes sociales instagram tiktok elon musk openai chatgpt robot* drone* drones",
"Internacional": "netanyahu guatemala peru colombia petro marruecos japon corea india oriente medio londres paris madrid washington casa blanca maduro trump eeuu estados unidos rusia ucrania putin israel gaza hamas iran china brasil lula europa venezuela maduro chile uruguay bolivia paraguay mexico españa espana francia alemania italia reino unido onu otan guerra feijoo sanchez pp vox psoe moncloa ayuso cuba rubio cia republicanos democratas yemen huties saudi* arabia",
"Iglesia y religión": "iglesia papa leon xiv arzobispo* obispo* vaticano catolic* religion religioso* fieles misa cardenal",
"Trabajo y gremios": "trabajador* trabajadores empleo desempleo despido* despidos gremio* sindicato* cgt paro* huelga* convenio laboral* obrero* docentes",
"Sociedad y derechos": "pobreza desigualdad genero orgullo lgbt* mujer* mujeres violencia derechos vivienda jubilados inclusion migrante* inmigrante* adultos mayores ninez infancia adolescente* comunidad barrio* vecinos solidaridad desaparecidos identidad nietos abuelas carlotto malvinas homenaje",
"Accidentes y sucesos": "accidente* choque* choco vuelco vuelcos atropell* tragedia* incendio* electrocut* siniestro* explosion derrumbe colision* despiste murio murieron fallecio fallecieron herido* heridos grave gravisimo internado rescate rescataron bomberos",
"Estilo de vida y turismo": "bienestar yoga maquillaje jardineria jardin poda plantas plagas receta* recetas cocina chef gastronomia decoracion hogar moda viaje* viajes turismo vacaciones mascotas perros gatos horoscopo vida sana consejos cuidar lujo diseno refugio estilo belleza skincare perfume* maquillador* rejuvenecer limpieza heladera cocinero ensalada milanesa* kilos adelgazar recorridos visitas guiadas caminata",
"Loterías y juegos de azar": "loteria quiniela cartonazo quini sorteo numeros ganadores casino apuestas premio*",
"Agro": "soja campo agro agricult* ganader* cosecha trigo maiz retenciones granos cereal* siembra productor* productores exportadora* cultivo*",
"Tecnología y ciencia": "ciencia cientific* investigacion conicet nasa espacio astronomia satelite* descubrimiento",
}
def _comp(s):
    out=[]
    for k in s.split(" "):
        pass
    return out
# compilar: separar por espacios pero respetar frases conocidas: las frases se declaran con guion bajo en el mapa de abajo
PHRASES = ["proyecto de ley","martin fierro","wanda nara","china suarez","charly garcia","visitas guiadas","mundial de clubes","casa rosada","riesgo pais","obra social","camara federal","corte suprema","feria del libro","inteligencia artificial","redes sociales","estados unidos","reino unido","adultos mayores","tabla de posiciones","san lorenzo","argentinos juniors","rosario central","copa de la liga","copa argentina","liga profesional","primera division","juegos olimpicos","el nino","fecha fifa","real madrid","papa leon xiv","leon xiv","paro docente","ciclo lectivo","partido politico","libertad avanza","elon musk","robbie williams","denuncio penalmente"]
STOP=set('de la el por con en y a los las un una que del al como mas ex pro ola casa mundo guia vida internacional frente su sus se es lo o u e'.split())
def compile_topics():
    res={}
    for name,txt in TOPICS.items():
        t=norm(txt); phr=[]
        for p in PHRASES:
            if p in t: phr.append(p); t=t.replace(p," ")
        words=[w for w in t.split() if w and w not in STOP]
        stems=tuple(w[:-1] for w in words if w.endswith("*"))
        exact=frozenset(w for w in words if not w.endswith("*"))
        res[name]=(exact,stems,tuple(phr))
    return res
C=compile_topics()
# temas que se muestran juntos (los chicos o casi duplicados se fusionan en uno)
MERGE={"Tecnología y ciencia":"Tecnología","Loterías y juegos de azar":"Estilo de vida y turismo","Agro":"Economía y trabajo","Economía y finanzas":"Economía y trabajo","Trabajo y gremios":"Economía y trabajo","Iglesia y religión":"Sociedad y derechos","Justicia":"Seguridad y justicia","Seguridad y policiales":"Seguridad y justicia"}
def merge_tema(k): return MERGE.get(k,k)
def tag(title, medio=""):
    n=norm(title); toks=re.findall(r"[a-z0-9]+",n); ts=set(toks); hits={}
    for name,(ex,st,ph) in C.items():
        c=len(ts&ex)+sum(1 for t in toks if t.startswith(st) and t not in ex if st)+sum(1 for p in ph if p in n)
        if c: hits[name]=c
    if "voley" in ts and "Fútbol" in hits and "central" in ts: hits.pop("Fútbol",None); hits.setdefault("Otros deportes",1)
    if medio=="Olé" and "Otros deportes" not in hits: hits["Fútbol"]=hits.get("Fútbol",0)+2
    if medio=="Olé" and "Otros deportes" in hits: hits.pop("Fútbol",None)
    mh={}
    for k,v in hits.items(): mh[merge_tema(k)]=mh.get(merge_tema(k),0)+v
    hits=mh
    tags=[k for k,_ in sorted(hits.items(),key=lambda x:-x[1])][:2]
    return tags or ["Otros"]

# ---------- respaldo con modelo: Naive Bayes entrenado con lo que ya clasificaron las reglas ----------
# Supervision debil: las notas con tema por palabras clave son el set de entrenamiento; el modelo
# solo asigna tema a las notas "Otros" cuando la probabilidad del tema ganador supera UMBRAL.
import math
from collections import Counter
UMBRAL = 0.90
_STOP_NB = STOP | set("para sobre tras este esta fue son hay mas muy como cuando donde quien cual desde hasta entre".split())
def _toks_nb(t): return [w for w in re.findall(r"[a-z0-9]+", norm(t)) if len(w) >= 3 and w not in _STOP_NB and not w.isdigit()]
def entrenar_nb(docs):
    """docs: [(texto, tema)]. Devuelve el modelo (conteos por tema)."""
    cnt, n, V = {}, Counter(), set()
    for txt, tema in docs:
        n[tema] += 1; c = cnt.setdefault(tema, Counter())
        for w in set(_toks_nb(txt)): c[w] += 1; V.add(w)
    tot = {k: sum(c.values()) for k, c in cnt.items()}
    return {"cnt": cnt, "n": n, "tot": tot, "V": len(V), "N": sum(n.values())}
def predecir_nb(m, txt):
    """(tema, probabilidad) o (None, 0) si no hay palabras conocidas"""
    ws = [w for w in set(_toks_nb(txt)) if any(w in c for c in m["cnt"].values())]
    if len(ws) < 2: return None, 0.0
    lp = {k: math.log(m["n"][k] / m["N"]) + sum(math.log((c[w] + 0.5) / (m["tot"][k] + 0.5 * m["V"])) for w in ws) for k, c in m["cnt"].items()}
    mx = max(lp.values()); z = sum(math.exp(v - mx) for v in lp.values())
    k = max(lp, key=lp.get)
    return k, 1.0 / z
