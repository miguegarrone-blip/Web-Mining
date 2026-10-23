"""Sesión HTTP común: reintentos con espera creciente ante errores transitorios.

Reintenta 429 y 5xx (respetando Retry-After) hasta 4 veces con esperas de 1.5s, 3s, 6s, 12s.
Los errores 403/404 no se reintentan: indican un cambio real del sitio y los detecta el control de salud.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Mozilla/5.0 (monitor-precios-rosario; uso analitico)"


def new_session():
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "POST"}), respect_retry_after_header=True,
                  raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-AR,es;q=0.9"})
    return session
