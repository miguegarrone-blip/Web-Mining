"""Pruebas de las funciones de extraccion y limpieza: lo que se rompe cuando un sitio cambia de plantilla.
Correr desde diarios-del-pais/:  python -m pytest -q tests
No usan red ni modelos (spaCy, BERT): solo funciones puras y un requests simulado para robots.txt."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import enriquecer, nlp, topics, ner


# ---------- bajadas ----------
def test_bajada_descarta_codigo_y_css():
    assert enriquecer.depurar_bajada('1&&m.push(e.virtualSize-r)}if(o&&s.loop){const t=g[0]+x;') == ""
    assert enriquecer.depurar_bajada("kground-color 0.2s ease, color 0.2s ease; } .mol-google-pref-btn:hover") == ""
    assert enriquecer.depurar_bajada("function() { googletag.display('div-gpt-ad-1'); }); la nota") == ""

def test_bajada_repara_entidades_mojibake_y_sufijo():
    assert enriquecer.depurar_bajada("para &amp;quot;extorsionar&amp;quot; al Gobierno.") == 'para "extorsionar" al Gobierno.'
    assert enriquecer.depurar_bajada("cada participante podrÃ¡ llevar sus preguntas") == "cada participante podrá llevar sus preguntas"
    assert enriquecer.depurar_bajada("conservar esta fruta. (Video: eltrece) | eltrece") == "conservar esta fruta. (Video: eltrece)"

def test_bajada_respeta_texto_normal():
    t = "Mariano Werner y Norberto Fontana hicieron las delicias del público en bulevar Oroño."
    assert enriquecer.depurar_bajada(t) == t
    assert enriquecer.mojibake("Señor día “bien” ñandú") == "Señor día “bien” ñandú"
    assert enriquecer.mojibake("calificÃ³ como “una programaciÃ³n”") == "calificó como “una programación”"

def test_bajada_de_html_prefiere_og_y_saltea_scripts():
    html_og = '<meta property="og:description" content="La bajada que escribió el medio sobre la nota de hoy">'
    assert enriquecer.bajada_de_html(html_og) == "La bajada que escribió el medio sobre la nota de hoy"
    html_p = ('<script>var a = "<p>esto es codigo de un carrusel que no es una bajada de verdad, para nada</p>";</script>'
              '<path d="M0 0"/><p class="x">Este es el primer párrafo real de la nota, con suficientes palabras para contar.</p>')
    assert enriquecer.bajada_de_html(html_p).startswith("Este es el primer párrafo real")


# ---------- JSON-LD ----------
HTML_LD = '''<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage"},
 {"@type":"NewsArticle","author":[{"@type":"Person","name":"María Pérez"}],"articleSection":["Política","Nacional"],
  "keywords":["Milei","Congreso"],"dateModified":"2026-10-24T15:30:00-03:00","articleBody":"uno dos tres cuatro cinco"}]}</script>'''

def test_json_ld_newsarticle_en_graph():
    d = enriquecer.json_ld(HTML_LD)
    assert d["autor"] == "María Pérez" and d["seccion"] == "Política"
    assert d["claves"] == "Milei, Congreso" and d["largo"] == 5
    from datetime import datetime, timezone
    assert d["mod_ms"] == int(datetime(2026, 10, 24, 18, 30, tzinfo=timezone.utc).timestamp() * 1000)   # 15:30 -03:00

def test_json_ld_ausente_o_roto():
    assert enriquecer.json_ld("<html>sin datos</html>") == {}
    assert enriquecer.json_ld('<script type="application/ld+json">{roto</script>') == {}

def test_firmada():
    assert enriquecer.firmada("María Pérez", "Clarín") == 1
    assert enriquecer.firmada("Redacción Clarín", "Clarín") == 0
    assert enriquecer.firmada("Newsroom Infobae", "Infobae") == 0
    assert enriquecer.firmada("TN", "TN") == 0


# ---------- robots.txt (requests simulado, sin red) ----------
def test_robots_txt(monkeypatch):
    class R:
        status_code = 200
        text = "User-agent: *\nDisallow: /privado/\n"
    monkeypatch.setattr(enriquecer.requests, "get", lambda *a, **k: R())
    enriquecer._robots.clear()
    assert enriquecer.permitido("https://ejemplo.com.ar/nota/123") is True
    assert enriquecer.permitido("https://ejemplo.com.ar/privado/nota") is False


# ---------- titulos: cebo, entidades, temas ----------
def test_cebo():
    assert nlp.cebo("El gobierno presentó el presupuesto 2027") == 0
    assert set(nlp.cebo_rasgos("¡Bomba! Lo que nadie te contó: ¿por qué pasó?")) >= {"exclamación", "pregunta", "adjetivo exagerado", "intriga"}

def test_entidades_desambiguan_central():
    assert "Rosario Central" in nlp.ents("Central ganó el clásico en el Gigante")
    assert "Rosario Central" not in nlp.ents("El Banco Central subió la tasa")
    assert "BCRA" in nlp.ents("El Banco Central subió la tasa")

def test_temas():
    assert "Seguridad y justicia" in topics.tag("Detuvieron a dos hombres por un robo en zona sur")
    assert topics.tag("asdf qwer zxcv") == ["Otros"]


# ---------- NER: limpieza de entidades (sin cargar spaCy) ----------
def test_ner_limpiar():
    assert ner.limpiar("El presidente Javier Milei") == "Javier Milei"
    assert ner.limpiar("Según") == ""
    assert ner.en_diccionario("Milei")
