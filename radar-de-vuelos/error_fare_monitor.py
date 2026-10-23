"""
error_fare_monitor.py — Script base de detección de "error fares" desde Argentina.

Qué hace:
  1. Consulta precios (proveedor real vía API, o modo DEMO con datos sintéticos).
  2. Normaliza a USD "all-in" comparable (equipaje estimado para LCC, tasas, percepción AR).
  3. Compara contra un baseline histórico robusto por ruta × mes de salida × cabina.
  4. Marca anomalías con doble regla (z-score robusto + caída vs P10) y filtros anti falso positivo.
  5. Envía alerta a Telegram con ruta, aerolínea, precio, link y TTL estimado.

Uso:
  python error_fare_monitor.py                 # un barrido real (Google Flights, gratis) + feeds de ofertas
  python error_fare_monitor.py --serve         # panel local en http://localhost:8765 con botón "Buscar ahora"
  python error_fare_monitor.py --demo --serve  # lo mismo con datos sintéticos, para probar
  Telegram (opcional): variables TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID

Dependencias: pip install httpx pandas numpy fast-flights
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sqlite3
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pandas as pd

# ───────────────────────── Configuración ─────────────────────────
def _env_list(name: str, default: str) -> list[str]:
    return [x.strip().upper() for x in os.getenv(name, default).split(",") if x.strip()]

# Cada combinación origen × destino × fecha × cabina = 1 request pago (Ignav: USD 2 cada 1.000).
# Defaults pensados para ~90 requests por barrido. Ajustalos con variables de entorno.
ORIGINS = _env_list("FARES_ORIGINS", "EZE,COR,ROS")
DESTINATIONS = _env_list("FARES_DESTINATIONS", "MIA,MAD,BCN,JFK,FCO,GRU,SCL,CUN,PUJ,BRC")
CABINS = _env_list("FARES_CABINS", "ECONOMY")
N_DATES = int(os.getenv("FARES_N_DATES", "3"))
DOMESTIC_AR = {"EZE", "AEP", "ROS", "COR", "BRC", "USH", "IGR", "MDZ", "FTE", "SLA", "NQN"}

# Aerolíneas cuyo precio base excluye valija: se les suma un costo estimado para comparar manzanas con manzanas.
LCC_BAGGAGE_USD = {"FO": 45, "JA": 40, "H2": 40, "G3": 35, "AD": 30, "NK": 60, "F9": 60}

Z_THRESHOLD = -2.5          # z-score robusto (mediana/MAD)
P10_DROP_THRESHOLD = 0.60   # precio ≥60% por debajo del P10 histórico
MIN_HISTORY = 30            # observaciones mínimas para confiar en el baseline
MIN_ABS_SAVING_USD = 150    # descarta "anomalías" de rutas baratas (ej. AEP-COR a USD 40 vs 70)
PERCEPCION_GANANCIAS = 0.30 # RG 5617/2024 — vigente a oct-2026, verificar antes de producción

DB_PATH = os.getenv("FARES_DB", "fares.sqlite")


@dataclass
class Fare:
    origin: str
    destination: str
    depart_date: str
    return_date: str | None
    cabin: str               # ECONOMY | PREMIUM | BUSINESS | FIRST
    carrier: str             # código IATA de la marketing carrier
    price: float
    currency: str            # USD | ARS
    taxes_included: bool
    stops: int
    booking_url: str
    source: str
    observed_at: str = ""


# ───────────────────────── Tipo de cambio ─────────────────────────
async def fetch_usd_ars(client: httpx.AsyncClient) -> dict:
    """Oficial vendedor + dólar tarjeta (oficial × 1.30). Fallback si la API no responde."""
    try:
        r = await client.get("https://dolarapi.com/v1/dolares/oficial", timeout=10)
        r.raise_for_status()
        oficial = float(r.json()["venta"])
    except Exception:
        oficial = float(os.getenv("USD_ARS_FALLBACK", "1450"))
    return {"oficial": oficial, "tarjeta": oficial * (1 + PERCEPCION_GANANCIAS)}


# ───────────────────────── Proveedores ─────────────────────────
class FareProvider:
    name = "base"

    async def search(self, client, origin, dest, depart) -> list[Fare]:
        raise NotImplementedError


class IgnavProvider(FareProvider):
    """Ignav (https://ignav.com/docs): búsqueda one-way + links de compra por itinerario.
    Cobra por request exitoso, así que el link de compra se pide SOLO cuando hay alerta."""
    name = "ignav"
    SEARCH = "https://ignav.com/api/fares/one-way"
    LINKS = "https://ignav.com/api/fares/booking-links"

    def __init__(self, api_key: str, max_rps: float = 2.0, market: str = "AR"):
        self.api_key = api_key
        self.market = market
        self._sem = asyncio.Semaphore(4)
        self._min_interval = 1.0 / max_rps
        self.requests = 0

    async def _post(self, client, url, body) -> dict | None:
        async with self._sem:
            for attempt in range(4):  # backoff exponencial ante 429/5xx
                r = await client.post(url, headers={"X-Api-Key": self.api_key}, json=body, timeout=45)
                if r.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2 ** attempt + random.random())
                    continue
                if r.status_code >= 400:
                    print(f"  ! {url.rsplit('/', 1)[-1]} {body.get('origin', '')}-{body.get('destination', '')} "
                          f"→ HTTP {r.status_code}: {r.text[:160]}")
                    return None
                self.requests += 1
                await asyncio.sleep(self._min_interval)
                return r.json()
        return None

    async def search(self, client, origin, dest, depart) -> list[Fare]:
        out = []
        for cabin in CABINS:
            data = await self._post(client, self.SEARCH, {
                "origin": origin, "destination": dest, "departure_date": depart,
                "cabin_class": cabin.lower()})
            if data:
                out += self._parse(data, origin, dest, depart, cabin)
        return out

    def _parse(self, data: dict, origin, dest, depart, cabin) -> list[Fare]:
        out = []
        for it in data.get("itineraries", []):
            price = it.get("price") or {}
            segs = (it.get("outbound") or {}).get("segments") or []
            if not segs or price.get("amount") is None:
                continue
            if it.get("requires_self_transfer"):
                continue  # conexiones "armadas" sin protección: fuente típica de falsos positivos
            out.append(Fare(
                origin=origin, destination=dest, depart_date=depart, return_date=None,
                cabin=(it.get("cabin_class") or cabin).upper(),
                carrier=segs[0].get("marketing_carrier_code") or "??",
                price=float(price["amount"]), currency=(price.get("currency") or "USD").upper(),
                taxes_included=True, stops=len(segs) - 1,
                booking_url=f"ignav:{it.get('ignav_id', '')}", source=self.name,
            ))
        # Nos quedamos con el itinerario más barato por aerolínea: el baseline mide el "piso" del mercado.
        best: dict[str, Fare] = {}
        for f in out:
            if f.carrier not in best or f.price < best[f.carrier].price:
                best[f.carrier] = f
        return list(best.values())

    async def resolve_link(self, client, f: Fare) -> str:
        """Convierte 'ignav:<id>' en el link directo de compra más barato (1 request extra)."""
        if not f.booking_url.startswith("ignav:"):
            return f.booking_url
        data = await self._post(client, self.LINKS, {"ignav_id": f.booking_url[6:]})
        links = [l for o in (data or {}).get("booking_options", []) for l in o.get("links", []) if l.get("url")]
        if not links:
            return ""
        best = min(links, key=lambda l: (l.get("price") or {}).get("amount") or 1e12)
        return best["url"]


class GoogleFlightsProvider(FareProvider):
    """Google Flights vía la librería no oficial `fast-flights` (gratis, sin API key).
    Uso personal y a bajo volumen: búsquedas secuenciales con pausas, sin proxies.
    Pide la tarifa CON 1 valija despachada, así las low-cost quedan comparables."""
    name = "google"
    SEAT = {"ECONOMY": "economy", "PREMIUM": "premium-economy", "BUSINESS": "business", "FIRST": "first"}

    def __init__(self, pause_s: tuple[float, float] = (4.0, 9.0)):
        from fast_flights import FlightQuery, create_query, get_flights  # import diferido: solo si se usa
        self._FlightQuery, self._create_query, self._get_flights = FlightQuery, create_query, get_flights
        self.pause_s = pause_s
        self._lock = asyncio.Lock()  # una búsqueda por vez: ritmo de una persona, no de un bot
        self.requests = 0
        self.errors = 0
        self.empty = 0  # rutas/fechas sin vuelos publicados (no es un error)

    def _query(self, origin, dest, depart, cabin):
        return self._create_query(
            flights=[self._FlightQuery(date=depart, from_airport=origin, to_airport=dest)],
            seat=self.SEAT.get(cabin, "economy"), trip="one-way",
            currency="USD", language="es-419",
            checked_bags=1 if cabin == "ECONOMY" else 0,
            hide_separate_and_self_transfer=True,
        )

    async def search(self, client, origin, dest, depart) -> list[Fare]:
        out = []
        for cabin in CABINS:
            q = self._query(origin, dest, depart, cabin)
            async with self._lock:
                try:
                    res = await asyncio.to_thread(self._get_flights, q)
                    self.requests += 1
                except (TypeError, IndexError):
                    # fast-flights falla así cuando Google no devuelve vuelos para esa ruta/fecha
                    self.empty += 1
                    res = []
                except Exception as e:
                    self.errors += 1
                    print(f"  ! Google Flights {origin}-{dest} {depart} {cabin}: {type(e).__name__}: {str(e)[:120]}")
                    res = []
                await asyncio.sleep(random.uniform(*self.pause_s))
            best: dict[str, Fare] = {}
            for fl in res or []:
                if not fl.price:
                    continue
                code = fl.type if fl.type and fl.type != "multi" else "MULTI"
                f = Fare(origin, dest, depart, None, cabin, code, float(fl.price), "USD", True,
                         max(len(fl.flights) - 1, 0), q.url(), self.name)
                if code not in best or f.price < best[code].price:
                    best[code] = f  # el más barato por aerolínea
            out += best.values()
        return out


def load_tp_token() -> str | None:
    """Token de Travelpayouts: variable de entorno, o el .env de esta carpeta o de radar-multifuente."""
    if os.getenv("TRAVELPAYOUTS_TOKEN"):
        return os.getenv("TRAVELPAYOUTS_TOKEN").strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, ".env"), os.path.join(here, "..", "radar-multifuente", ".env")):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                for line in fh:
                    if line.strip().startswith("TRAVELPAYOUTS_TOKEN="):
                        tok = line.split("=", 1)[1].strip().strip('"')
                        if tok:
                            return tok
        except OSError:
            continue
    return None


class TravelpayoutsSource:
    """Aviasales Data API: los precios más baratos de TODO el mes por ruta (caché de búsquedas reales)."""
    name = "travelpayouts"
    API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    KEEP_PER_QUERY = 10  # las 10 más baratas por ruta y mes alcanzan para comparar

    def __init__(self, token: str):
        self.token = token
        self.marker = os.getenv("TRAVELPAYOUTS_MARKER", "").strip()
        self._sem = asyncio.Semaphore(4)
        self.done = 0
        self.errors = 0

    async def fetch(self, client, origin, dest, month) -> list[Fare]:
        async with self._sem:
            for attempt in range(4):
                try:
                    r = await client.get(self.API, headers={"X-Access-Token": self.token}, timeout=30, params={
                        "origin": origin, "destination": dest, "departure_at": month, "one_way": "true",
                        "currency": "usd", "sorting": "price", "limit": self.KEEP_PER_QUERY})
                except httpx.TransportError:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if r.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2 ** attempt + random.random())
                    continue
                break
            else:
                r = None
            await asyncio.sleep(0.25)
            self.done += 1
        if r is None or r.status_code != 200:
            self.errors += 1
            if r is not None:
                print(f"  ! Travelpayouts {origin}-{dest} {month}: HTTP {r.status_code} {r.text[:120]}")
            return []
        out = []
        for it in (r.json().get("data") or []):
            if it.get("price") is None or not it.get("departure_at"):
                continue
            link = "https://www.aviasales.com" + it["link"] if it.get("link") else ""
            if link and self.marker:
                link += ("&" if "?" in link else "?") + "marker=" + self.marker
            out.append(Fare(
                origin=it.get("origin_airport") or origin, destination=it.get("destination_airport") or dest,
                depart_date=it["departure_at"][:10], return_date=None, cabin="ECONOMY",
                carrier=it.get("airline") or "??", price=float(it["price"]), currency="USD",
                taxes_included=True, stops=int(it.get("transfers") or 0), booking_url=link, source=self.name))
        return out


def tp_months(horizon_days=180) -> list[str]:
    today = date.today()
    out = []
    for i in range(horizon_days // 30 + 1):
        y, m = divmod(today.month - 1 + i, 12)
        out.append(f"{today.year + y}-{m + 1:02d}")
    return out


class DemoProvider(FareProvider):
    """Genera precios sintéticos realistas e inyecta algunos error fares para probar el pipeline."""
    name = "demo"
    BASE_USD = {"MIA": 750, "MAD": 1100, "BCN": 1150, "JFK": 900, "FCO": 1250, "GRU": 320,
                "SCL": 260, "CUN": 850, "PUJ": 900, "BRC": 140, "USH": 180, "IGR": 120}
    CARRIERS = ["AR", "LA", "AA", "IB", "UX", "AZ", "G3", "FO", "JA", "CM"]

    def __init__(self, inject_rate=0.03, seed=7):
        self.rng = random.Random(seed)
        self.inject_rate = inject_rate

    def sample(self, origin, dest, depart, cabin="ECONOMY") -> Fare:
        base = self.BASE_USD[dest] * (3.2 if cabin == "BUSINESS" else 1.0)
        month = int(depart[5:7])
        season = 1.25 if month in (1, 2, 7, 12) else 1.0
        price = base * season * self.rng.lognormvariate(0, 0.12)
        carrier = self.rng.choice(self.CARRIERS)
        if carrier in LCC_BAGGAGE_USD:
            price *= 0.82  # LCC: más barato pero sin valija → no debería disparar alerta sola
        if self.rng.random() < self.inject_rate:
            price *= self.rng.uniform(0.12, 0.30)  # "error fare" inyectado
        return Fare(origin, dest, depart, None, cabin, carrier, round(price, 2), "USD", True,
                    self.rng.choice([0, 1, 1, 2]), f"https://example.com/book/{origin}-{dest}/{depart}",
                    self.name)

    async def search(self, client, origin, dest, depart) -> list[Fare]:
        return [self.sample(origin, dest, depart, c) for c in ("ECONOMY", "ECONOMY", "BUSINESS")]


# ───────────────────────── Persistencia ─────────────────────────
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS fares (
        origin TEXT, destination TEXT, depart_date TEXT, return_date TEXT, cabin TEXT,
        carrier TEXT, price REAL, currency TEXT, taxes_included INT, stops INT,
        booking_url TEXT, source TEXT, observed_at TEXT, usd_allin REAL)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_route ON fares(origin, destination, cabin, depart_date)")
    con.execute("""CREATE TABLE IF NOT EXISTS alerts (
        key TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, usd_allin REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS alerts_log (
        found_at TEXT, origin TEXT, destination TEXT, depart_date TEXT, cabin TEXT, carrier TEXT,
        stops INT, usd_allin REAL, ars_cost REAL, median REAL, p10 REAL, z REAL, drop_vs_p10 REAL,
        saving_usd REAL, kind TEXT, severity TEXT, ttl_hours REAL, booking_url TEXT,
        google_flights TEXT, skyscanner TEXT, kayak TEXT)""")
    ensure_semantic_layer(con)
    return con


def save(con, fares: list[Fare], usd_allin: list[float]):
    rows = [(*asdict(f).values(), u) for f, u in zip(fares, usd_allin)]
    con.executemany(f"INSERT INTO fares VALUES ({','.join('?' * 14)})", rows)
    con.commit()


# ───────────────────────── Normalización ─────────────────────────
def to_usd_allin(f: Fare, fx: dict) -> float:
    """Precio comparable en USD: convierte ARS al oficial, suma valija a LCC.
    La percepción del 30% NO se suma aquí (es igual para todas las tarifas internacionales y
    distorsionaría la comparación con fuentes en USD); se reporta aparte en la alerta."""
    usd = f.price / fx["oficial"] if f.currency == "ARS" else f.price
    if f.cabin == "ECONOMY" and f.source != "google":  # Google ya incluye la valija (checked_bags=1)
        usd += LCC_BAGGAGE_USD.get(f.carrier, 0)
    return usd


def ars_cost(f: Fare, usd_allin: float, fx: dict) -> float:
    international = not ({f.origin, f.destination} <= DOMESTIC_AR)
    rate = fx["tarjeta"] if international else fx["oficial"]
    return usd_allin * rate


# ───────────────────────── Baseline y detección ─────────────────────────
def baseline(con, f: Fare, lookback_days=180) -> dict | None:
    """Baseline robusto por ruta × cabina × mes de salida (± ventana de 45 días de salida)."""
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    d = date.fromisoformat(f.depart_date)
    lo, hi = (d - timedelta(days=45)).isoformat(), (d + timedelta(days=45)).isoformat()
    s = pd.read_sql_query(
        """SELECT usd_allin FROM fares WHERE origin=? AND destination=? AND cabin=? AND source=?
           AND depart_date BETWEEN ? AND ? AND observed_at >= ?""",
        con, params=(f.origin, f.destination, f.cabin, f.source, lo, hi, since))["usd_allin"]
    if len(s) < MIN_HISTORY:
        return None
    med = float(s.median())
    mad = float((s - med).abs().median()) * 1.4826 or float(s.std()) or 1.0
    return {"n": len(s), "median": med, "mad": mad, "p10": float(s.quantile(0.10))}


def classify(f: Fare, usd: float, b: dict) -> dict | None:
    z = (usd - b["median"]) / b["mad"]
    drop_vs_p10 = 1 - usd / b["p10"]
    saving = b["median"] - usd
    hits = [z <= Z_THRESHOLD, drop_vs_p10 >= P10_DROP_THRESHOLD]
    if not any(hits) or saving < MIN_ABS_SAVING_USD:
        return None
    # Sospecha de tipo de error (heurística, para priorizar)
    if f.cabin in ("BUSINESS", "FIRST") and usd < b["median"] * 0.35:
        kind = "cabina mal tarifada"
    elif drop_vs_p10 > 0.80:
        kind = "posible falta de YQ/YR (fuel surcharge) o tasas"
    elif f.currency == "ARS":
        kind = "posible descalce cambiario (tarifa en ARS desactualizada)"
    else:
        kind = "tarifa anómala"
    severity = "🔴 CRÍTICA" if all(hits) else "🟠 ALTA"
    return {"z": round(z, 2), "drop_vs_p10": round(drop_vs_p10, 3),
            "saving_usd": round(saving), "kind": kind, "severity": severity}


def search_links(f: Fare) -> dict:
    """Links directos de búsqueda en metabuscadores para verificar y comprar la tarifa."""
    d = f.depart_date
    yymmdd = d[2:4] + d[5:7] + d[8:10]
    cabin_kayak = {"BUSINESS": "/business", "FIRST": "/first", "PREMIUM": "/premium"}.get(f.cabin, "")
    cabin_gf = {"BUSINESS": "%20business%20class", "FIRST": "%20first%20class"}.get(f.cabin, "")
    return {
        "google_flights": (f"https://www.google.com/travel/flights?q=Flights%20to%20{f.destination}"
                           f"%20from%20{f.origin}%20on%20{d}%20oneway{cabin_gf}&curr=USD&hl=es-419"),
        "skyscanner": (f"https://www.skyscanner.com.ar/transporte/vuelos/{f.origin.lower()}/"
                       f"{f.destination.lower()}/{yymmdd}/"
                       + ("?cabinclass=business" if f.cabin == "BUSINESS" else "")),
        "kayak": f"https://www.kayak.com.ar/flights/{f.origin}-{f.destination}/{d}{cabin_kayak}?sort=price_a",
    }


def ttl_hours(kind: str, ts_found: datetime) -> float:
    hours = 6.0
    if kind.startswith("posible descalce"):
        hours = 24
    if kind.startswith("cabina"):
        hours = 3
    local_hour = (ts_found.astimezone(timezone(timedelta(hours=-3)))).hour
    if local_hour >= 22 or local_hour < 7 or ts_found.weekday() >= 5:
        hours *= 1.6
    return round(hours, 1)


def estimate_ttl(f: Fare, kind: str, ts_found: datetime) -> str:
    """Heurística de vida útil. Reemplazar por un modelo de supervivencia cuando haya datos
    propios (tiempo entre primera y última observación de cada alerta en la tabla alerts)."""
    hours = 6.0
    if kind.startswith("posible descalce"):
        hours = 24       # suelen durar hasta el próximo refresh de tipo de cambio
    if kind.startswith("cabina"):
        hours = 3        # las premium se vigilan más
    local_hour = (ts_found.astimezone(timezone(timedelta(hours=-3)))).hour
    if local_hour >= 22 or local_hour < 7 or ts_found.weekday() >= 5:
        hours *= 1.6     # noches y fines de semana: equipos de revenue con menos guardia
    return f"~{hours:.0f} h (heurística, baja confianza)"


# ───────────────────────── Alertas ─────────────────────────
async def send_telegram(client, text: str):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("\n" + text + "\n" + "─" * 60)
        return
    await client.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=15)


def dedupe_key(f: Fare) -> str:
    return f"{f.origin}-{f.destination}-{f.depart_date}-{f.cabin}-{f.carrier}"


def should_alert(con, f: Fare, usd: float) -> bool:
    """Evita spam: re-alerta sólo si es nueva o bajó otro 10%."""
    k, now = dedupe_key(f), datetime.now(timezone.utc).isoformat()
    row = con.execute("SELECT usd_allin FROM alerts WHERE key=?", (k,)).fetchone()
    if row and usd > row[0] * 0.90:
        con.execute("UPDATE alerts SET last_seen=? WHERE key=?", (now, k))
        con.commit()
        return False
    con.execute("INSERT OR REPLACE INTO alerts VALUES (?, COALESCE((SELECT first_seen FROM alerts WHERE key=?), ?), ?, ?)",
                (k, k, now, now, usd))
    con.commit()
    return True


def format_alert(f: Fare, usd: float, ars: float, b: dict, c: dict, ttl: str) -> str:
    intl = not ({f.origin, f.destination} <= DOMESTIC_AR)
    return (
        f"{c['severity']} — {c['kind']}\n"
        f"✈️ <b>{f.origin} → {f.destination}</b> · {f.depart_date} · {f.cabin} · {f.carrier} · {f.stops} escala(s)\n"
        f"💵 USD {usd:,.0f} all-in (mediana histórica USD {b['median']:,.0f}, P10 {b['p10']:,.0f})\n"
        f"🇦🇷 ≈ ARS {ars:,.0f} {'(incluye 30% percepción, recuperable)' if intl else '(oficial)'}\n"
        f"📉 z={c['z']} · {c['drop_vs_p10']:.0%} bajo P10 · ahorro ≈ USD {c['saving_usd']}\n"
        f"⏳ Vida estimada: {ttl}\n"
        f"🔗 {f.booking_url}\n"
        f"🔎 <a href=\"{search_links(f)['google_flights']}\">Google Flights</a> · "
        f"<a href=\"{search_links(f)['skyscanner']}\">Skyscanner</a> · "
        f"<a href=\"{search_links(f)['kayak']}\">Kayak</a>\n"
        f"⚠️ No reserves hoteles no reembolsables hasta tener el e-ticket emitido."
    )


# ───────────────────────── Orquestación ─────────────────────────
def search_grid(n_dates=N_DATES, horizon_days=180) -> list[tuple[str, str, str]]:
    today = date.today()
    dates = [(today + timedelta(days=int(d))).isoformat()
             for d in np.linspace(21, horizon_days, n_dates).astype(int)]
    return [(o, d, dt) for o in ORIGINS for d in DESTINATIONS if o != d for dt in dates]


async def sweep(provider: FareProvider, con, client, fx, tp: "TravelpayoutsSource | None" = None):
    grid = search_grid()
    jobs = [provider.search(client, o, d, dt) for o, d, dt in grid]
    if tp:
        jobs += [tp.fetch(client, o, d, m) for o in ORIGINS for d in DESTINATIONS if o != d for m in tp_months()]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    now = datetime.now(timezone.utc)
    fares = [f for r in results if isinstance(r, list) for f in r]
    for f in fares:
        f.observed_at = now.isoformat()
    usds = [to_usd_allin(f, fx) for f in fares]

    alerts = 0
    for f, usd in zip(fares, usds):
        b = baseline(con, f)
        if b is None:
            continue
        c = classify(f, usd, b)
        if c and should_alert(con, f, usd):
            ttl = estimate_ttl(f, c["kind"], now)
            ars = ars_cost(f, usd, fx)
            if hasattr(provider, "resolve_link"):
                f.booking_url = await provider.resolve_link(client, f) or search_links(f)["google_flights"]
            await send_telegram(client, format_alert(f, usd, ars, b, c, ttl))
            links = search_links(f)
            con.execute(f"INSERT INTO alerts_log VALUES ({','.join('?' * 21)})", (
                now.isoformat(), f.origin, f.destination, f.depart_date, f.cabin, f.carrier, f.stops,
                round(usd, 2), round(ars), round(b["median"], 2), round(b["p10"], 2), c["z"],
                c["drop_vs_p10"], c["saving_usd"], c["kind"], c["severity"], ttl_hours(c["kind"], now),
                f.booking_url, links["google_flights"], links["skyscanner"], links["kayak"]))
            con.commit()
            alerts += 1
    save(con, fares, usds)  # se guarda DESPUÉS de evaluar, para que la anomalía no contamine su propio baseline
    paid = getattr(provider, "requests", None)
    print(f"[{now:%H:%M:%S}] {len(grid)} búsquedas Google" + (f" + {tp.done} Travelpayouts ({tp.errors} con error)" if tp else "")
          + f" · {len(fares)} tarifas evaluadas · {alerts} alertas"
          + (f" · {paid} requests pagos acumulados" if paid is not None else "")
          + f" · USD/ARS oficial {fx['oficial']:.0f}")


def export_dashboard_data(con, out_dir="dashboard_data"):
    """Exporta CSVs para el dashboard: alertas con links y serie de precios por ruta."""
    os.makedirs(out_dir, exist_ok=True)
    pd.read_sql_query("SELECT * FROM alerts_log ORDER BY found_at DESC, saving_usd DESC", con) \
        .to_csv(f"{out_dir}/alerts.csv", index=False)
    daily = pd.read_sql_query(
        """SELECT substr(observed_at,1,10) AS fecha, origin || '-' || destination AS ruta, cabin,
                  MIN(usd_allin) AS min_usd, AVG(usd_allin) AS avg_usd, COUNT(*) AS n
           FROM fares GROUP BY 1,2,3 ORDER BY 1""", con)
    daily.round(2).to_csv(f"{out_dir}/price_history.csv", index=False)
    print(f"Datos del dashboard exportados a {out_dir}/")


def seed_demo_history(con, provider: DemoProvider, fx, days=120):
    """Puebla historia sintética para que el baseline tenga datos en modo demo."""
    clean = DemoProvider(inject_rate=0.0, seed=1)
    rows, usds = [], []
    for back in range(days, 0, -2):
        obs = (datetime.now(timezone.utc) - timedelta(days=back)).isoformat()
        for o, d, dt in search_grid():
            for cabin in ("ECONOMY", "BUSINESS"):
                f = clean.sample(o, d, dt, cabin)
                f.observed_at = obs
                rows.append(f)
                usds.append(to_usd_allin(f, fx))
    save(con, rows, usds)


# ───────────────────────── Feeds de ofertas (gratis) ─────────────────────────
FEEDS = {
    "Secret Flying": "https://www.secretflying.com/feed/",
    "Promociones Aéreas": "https://www.promociones-aereas.com.ar/feed/",
    "Fly4free": "https://www.fly4free.com/feed/",
}
FEED_KEYWORDS = ("argentina", "buenos aires", "rosario", "córdoba", "cordoba",
                 "eze", "aep", " ros ", " cor ", "ezeiza", "aeroparque")


async def fetch_feeds(con, client) -> int:
    """Lee RSS de sitios de ofertas, filtra las que salen de Argentina y avisa las nuevas."""
    import xml.etree.ElementTree as ET
    con.execute("""CREATE TABLE IF NOT EXISTS feed_items (
        link TEXT PRIMARY KEY, source TEXT, title TEXT, published TEXT, seen_at TEXT)""")
    new = 0
    for source, url in FEEDS.items():
        try:
            r = await client.get(url, timeout=20, follow_redirects=True)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:
            print(f"  ! feed {source}: {type(e).__name__}")
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            text = f" {title} {item.findtext('description') or ''} ".lower()
            if not link or not any(k in text for k in FEED_KEYWORDS):
                continue
            if con.execute("SELECT 1 FROM feed_items WHERE link=?", (link,)).fetchone():
                continue
            con.execute("INSERT INTO feed_items VALUES (?,?,?,?,?)",
                        (link, source, title, item.findtext("pubDate") or "",
                         datetime.now(timezone.utc).isoformat()))
            new += 1
            await send_telegram(client, f"📰 <b>{source}</b>\n{title}\n🔗 {link}")
    con.commit()
    return new


# ───────────────────────── Ejecución ─────────────────────────
def make_provider(demo: bool) -> FareProvider:
    if demo:
        return DemoProvider(seed=random.randint(0, 10**6))
    if os.getenv("FARES_PROVIDER", "google").lower() == "ignav":
        return IgnavProvider(os.environ["FARES_API_KEY"])
    return GoogleFlightsProvider()


STATUS = {"running": False, "last_run": None, "message": "Listo.",
          "progress": 0, "total": 0}


async def run_once(demo: bool, export: bool = False):
    con = db()
    provider = make_provider(demo)
    tok = None if demo else load_tp_token()
    tp = TravelpayoutsSource(tok) if tok else None
    n_tp = len([1 for o in ORIGINS for d in DESTINATIONS if o != d]) * len(tp_months()) if tp else 0
    STATUS.update(running=True, progress=0, tp=tp, total=len(search_grid()) * (3 if demo else len(CABINS)) + n_tp,
                  message="Buscando…", provider=provider,
                  started_at=datetime.now(timezone.utc).isoformat())
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 error-fare-monitor/0.2"}) as client:
            fx = await fetch_usd_ars(client)
            if demo and con.execute("SELECT COUNT(*) FROM fares").fetchone()[0] == 0:
                print("Sembrando historia sintética…")
                seed_demo_history(con, provider, fx)
            before = con.execute("SELECT COUNT(*) FROM alerts_log").fetchone()[0]
            await sweep(provider, con, client, fx, tp)
            n_alerts = con.execute("SELECT COUNT(*) FROM alerts_log").fetchone()[0] - before
            n_feed = 0 if demo else await fetch_feeds(con, client)
            if export:
                export_dashboard_data(con)
        errs, empty = getattr(provider, "errors", 0), getattr(provider, "empty", 0)
        STATUS["message"] = (f"{n_alerts} alerta(s) nueva(s), {n_feed} oferta(s) nueva(s) de feeds"
                             + (f" · {empty} ruta/fecha(s) sin vuelos" if empty else "")
                             + (f" · {errs} búsqueda(s) fallaron" if errs else ""))
    except Exception as e:
        STATUS["message"] = f"Error: {type(e).__name__}: {e}"
        raise
    finally:
        STATUS.update(running=False, last_run=datetime.now(timezone.utc).isoformat())
        STATUS.pop("provider", None)
        STATUS.pop("tp", None)
        con.close()


# ───────────────────────── Capa semántica para el panel ─────────────────────────
# código → (ciudad, país, continente)
DEST_META = {
    "MIA": ("Miami", "Estados Unidos", "América del Norte"), "JFK": ("Nueva York", "Estados Unidos", "América del Norte"),
    "MCO": ("Orlando", "Estados Unidos", "América del Norte"), "LAX": ("Los Ángeles", "Estados Unidos", "América del Norte"),
    "SLC": ("Salt Lake City", "Estados Unidos", "América del Norte"), "LAS": ("Las Vegas", "Estados Unidos", "América del Norte"),
    "MEX": ("Ciudad de México", "México", "América del Norte"), "CUN": ("Cancún", "México", "América del Norte"),
    "PUJ": ("Punta Cana", "República Dominicana", "Caribe"), "SDQ": ("Santo Domingo", "República Dominicana", "Caribe"),
    "HAV": ("La Habana", "Cuba", "Caribe"), "AUA": ("Aruba", "Aruba", "Caribe"),
    "MAD": ("Madrid", "España", "Europa"), "BCN": ("Barcelona", "España", "Europa"), "FCO": ("Roma", "Italia", "Europa"),
    "LIS": ("Lisboa", "Portugal", "Europa"), "CDG": ("París", "Francia", "Europa"), "LHR": ("Londres", "Reino Unido", "Europa"),
    "GRU": ("San Pablo · Sao Paulo", "Brasil", "América del Sur"), "GIG": ("Río de Janeiro", "Brasil", "América del Sur"),
    "FLN": ("Florianópolis", "Brasil", "América del Sur"), "SSA": ("Salvador de Bahía", "Brasil", "América del Sur"),
    "SCL": ("Santiago de Chile", "Chile", "América del Sur"), "LIM": ("Lima", "Perú", "América del Sur"),
    "BOG": ("Bogotá", "Colombia", "América del Sur"), "MVD": ("Montevideo", "Uruguay", "América del Sur"),
    "BRC": ("Bariloche", "Argentina", "Argentina (nacional)"), "USH": ("Ushuaia", "Argentina", "Argentina (nacional)"),
    "IGR": ("Iguazú", "Argentina", "Argentina (nacional)"), "MDZ": ("Mendoza", "Argentina", "Argentina (nacional)"),
    "FTE": ("El Calafate", "Argentina", "Argentina (nacional)"), "SLA": ("Salta", "Argentina", "Argentina (nacional)"),
    "NQN": ("Neuquén", "Argentina", "Argentina (nacional)"), "AEP": ("Buenos Aires (Aeroparque)", "Argentina", "Argentina (nacional)"),
    "EZE": ("Buenos Aires (Ezeiza)", "Argentina", "Argentina (nacional)"), "ROS": ("Rosario", "Argentina", "Argentina (nacional)"),
    "COR": ("Córdoba", "Argentina", "Argentina (nacional)"),
}
DEST_NAMES = {k: v[0] for k, v in DEST_META.items()}
CHEAP_LEG = -0.15  # un tramo es "barato" si está 15% o más bajo lo normal (o en su mínimo histórico)
MIN_SAMPLES = 3
SOURCE_LABEL = {"google": "Google Flights", "travelpayouts": "Aviasales", "demo": "demo"}
BUY_LABEL = {"google": "Google Flights", "travelpayouts": "Comprar en Aviasales", "demo": "Ver vuelo"}  # búsquedas con precio necesarias antes de mostrar la variación


def ensure_semantic_layer(con):
    """Índices y vista base de todas las métricas: el mínimo por ruta en cada búsqueda."""
    con.execute("CREATE INDEX IF NOT EXISTS ix_observed ON fares(observed_at)")
    con.execute("""CREATE VIEW IF NOT EXISTS v_route_sweep_src AS
        SELECT origin, destination, cabin, source, observed_at, MIN(usd_allin) AS min_usd
        FROM fares GROUP BY origin, destination, cabin, source, observed_at""")
    con.execute("""CREATE VIEW IF NOT EXISTS v_route_sweep AS
        SELECT origin, destination, cabin, observed_at, MIN(usd_allin) AS min_usd
        FROM fares GROUP BY origin, destination, cabin, observed_at""")
    con.execute("CREATE TABLE IF NOT EXISTS feed_items (link TEXT PRIMARY KEY, source TEXT, "
                "title TEXT, published TEXT, seen_at TEXT)")
    con.commit()


def route_summary(con, cabin="ECONOMY") -> tuple[list[dict], str | None]:
    """Por ruta: precio de la última búsqueda, mediana previa, mínimo visto, muestras y variación."""
    last = con.execute("SELECT MAX(observed_at) FROM fares WHERE cabin=?", (cabin,)).fetchone()[0]
    if not last:
        return [], None
    sweeps = pd.read_sql_query("SELECT * FROM v_route_sweep_src WHERE cabin=?", con, params=(cabin,))
    # última búsqueda: puede tener Google Flights y Travelpayouts con el mismo observed_at
    cur = pd.read_sql_query("SELECT * FROM fares WHERE observed_at=? AND cabin=?", con, params=(last, cabin))
    counts = cur.groupby(["origin", "destination"]).size().to_dict()
    best = cur.sort_values("usd_allin").drop_duplicates(["origin", "destination"])
    out = []
    for r in best.itertuples():
        hist = sweeps[(sweeps.origin == r.origin) & (sweeps.destination == r.destination) & (sweeps.source == r.source)]
        prev = hist[hist.observed_at < last].min_usd
        n = int(len(prev))
        median = float(prev.median()) if n else None
        min_prev = float(prev.min()) if n else None
        var = (r.usd_allin / median - 1) if n >= MIN_SAMPLES and median else None
        f = Fare(r.origin, r.destination, r.depart_date, None, r.cabin, r.carrier, r.price, r.currency,
                 True, int(r.stops), r.booking_url, r.source)
        links = search_links(f)
        out.append({
            "origin": r.origin, "destination": r.destination,
            "dest_name": DEST_NAMES.get(r.destination, r.destination),
            "country": DEST_META.get(r.destination, (None, "Otros", "Otros"))[1],
            "continent": DEST_META.get(r.destination, (None, "Otros", "Otros"))[2],
            "trip": "ida" if not r.return_date else "ida y vuelta",
            "depart_date": r.depart_date, "carrier": r.carrier, "stops": int(r.stops),
            "usd": round(float(r.usd_allin), 2), "median": round(median, 2) if median else None,
            "min_seen": round(min(min_prev, r.usd_allin), 2) if min_prev else round(float(r.usd_allin), 2),
            "is_record": bool(n >= MIN_SAMPLES and r.usd_allin <= min_prev),
            "samples": n, "variation": round(var, 4) if var is not None else None,
            "options": int(counts.get((r.origin, r.destination), 0)),
            "spark": [round(float(x), 2) for x in hist.sort_values("observed_at").min_usd.tail(20)],
            "google_flights": links["google_flights"],
            "source": r.source, "source_label": SOURCE_LABEL.get(r.source, r.source),
            "buy_url": r.booking_url if str(r.booking_url).startswith("http") else links["google_flights"],
            "buy_label": BUY_LABEL.get(r.source, "Ver vuelo"),
            "skyscanner": links["skyscanner"], "kayak": links["kayak"],
        })
    for o in out:
        o["cheap_leg"] = bool(o["variation"] is not None and (o["variation"] <= CHEAP_LEG or (o["is_record"] and o["variation"] <= -0.05)))
    return out, last


def build_summary(con) -> dict:
    routes, last = route_summary(con)
    with_var = [r for r in routes if r["variation"] is not None]
    best = min(with_var, key=lambda r: r["variation"]) if with_var else None
    if best and best["variation"] > -0.05:
        best = None  # nada realmente más barato que lo normal: mejor decirlo que mostrar un "= normal"
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    alerts = pd.read_sql_query("SELECT * FROM alerts_log WHERE found_at >= ? ORDER BY saving_usd DESC",
                               con, params=(since,))
    alerts = alerts.drop_duplicates(["origin", "destination", "depart_date", "cabin", "carrier"])
    alerts["dest_name"] = alerts.destination.map(lambda c: DEST_NAMES.get(c, c))
    feed = pd.read_sql_query("SELECT * FROM feed_items ORDER BY seen_at DESC LIMIT 30", con)
    n_sweeps = con.execute("SELECT COUNT(DISTINCT observed_at) FROM fares").fetchone()[0]
    by_src = dict(con.execute("SELECT source, COUNT(*) FROM fares WHERE observed_at=? GROUP BY source", (last,)).fetchall()) if last else {}
    total_hist = con.execute("SELECT COUNT(*) FROM fares").fetchone()[0]
    nxt = (datetime.fromisoformat(last) + timedelta(hours=6)).isoformat() if last else None
    return {
        "kpis": {
            "last_sweep": last, "next_sweep_approx": nxt, "sweeps": n_sweeps,
            "routes": len(routes), "below_normal": sum(1 for r in with_var if r["variation"] <= -0.05),
            "cheap_legs": sum(1 for r in routes if r["cheap_leg"]),
            "alerts": int(len(alerts)), "feed": int(len(feed)), "min_samples": MIN_SAMPLES,
            "flights_last": int(sum(by_src.values())), "flights_by_source": {SOURCE_LABEL.get(k, k): int(v) for k, v in by_src.items()},
            "flights_total": int(total_hist),
        },
        "best": best, "routes": routes,
        "alerts": json.loads(alerts.to_json(orient="records")),
        "feed": json.loads(feed.to_json(orient="records")),
    }


def route_detail(con, origin, dest, source="google", cabin="ECONOMY") -> dict:
    h = pd.read_sql_query(
        """SELECT observed_at, min_usd FROM v_route_sweep_src
           WHERE origin=? AND destination=? AND cabin=? AND source=? ORDER BY observed_at""",
        con, params=(origin, dest, cabin, source))
    return {"history": json.loads(h.round(2).to_json(orient="records"))}


def live_status() -> dict:
    prov = STATUS.get("provider")
    st = {k: v for k, v in STATUS.items() if k != "provider"}
    st.pop("tp", None)
    if prov:
        st["progress"] = getattr(prov, "requests", 0) + getattr(prov, "errors", 0) + getattr(prov, "empty", 0)
        if STATUS.get("tp"):
            st["progress"] += STATUS["tp"].done
    return st


# ───────────────────────── Panel local ─────────────────────────
PANEL_HTML = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Radar de vuelos</title>
<style>
:root{--bg:#f6f5f1;--panel:#fff;--sunk:#efede8;--fg:#1d1c1a;--muted:#6b6862;--faint:#9a968e;--line:#e2dfd8;
--acc:#1f5fd6;--acc-soft:#e7eefc;--good:#13804b;--good-soft:#e3f3ea;--bad:#b4401a;--bad-soft:#fbeae3;--warn:#946200;
--r:14px;--shadow:0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.04)}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--panel:#1d1c1b;--sunk:#252422;--fg:#eceae4;--muted:#a6a29a;--faint:#77736c;
--line:#33312e;--acc:#7aa7ff;--acc-soft:#1d2a44;--good:#4fd18b;--good-soft:#16301f;--bad:#ff8a5c;--bad-soft:#3a1f15;--warn:#f0b54a;--shadow:none}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;font-variant-numeric:tabular-nums}
button,input{font:inherit;color:inherit}a{color:inherit}
.wrap{max-width:1120px;margin:0 auto;padding:20px 16px 120px}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
h1{font:600 22px/1.2 "Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;margin:0;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin-top:2px}
.btn{border:0;border-radius:12px;padding:0 18px;min-height:44px;font-weight:600;cursor:pointer;background:var(--fg);color:var(--bg);display:inline-flex;align-items:center;gap:8px;white-space:nowrap}
.btn[disabled]{cursor:progress;opacity:.85}.btn.ghost{background:var(--sunk);color:var(--fg)}
.prog{height:3px;border-radius:3px;background:var(--line);overflow:hidden;margin-top:6px}.prog i{display:block;height:100%;width:0;background:var(--acc);transition:width .6s}
.kpis{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;margin-top:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:16px;box-shadow:var(--shadow)}
.k-label{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.k-val{font:600 28px/1.1 "Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;margin-top:8px}
.k-note{font-size:13px;color:var(--muted);margin-top:4px}
.hero{display:flex;flex-direction:column;justify-content:space-between;gap:10px;border-color:transparent;background:linear-gradient(0deg,var(--panel),var(--panel)) padding-box,linear-gradient(135deg,var(--acc),transparent 60%) border-box;border:1.5px solid transparent}
.hero .route{font-size:17px;font-weight:600}.hero .k-val{font-size:34px}
.pill{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:2px 9px;font-size:12.5px;font-weight:600}
.pill.down{background:var(--good-soft);color:var(--good)}.pill.up{background:var(--bad-soft);color:var(--bad)}.pill.flat{background:var(--sunk);color:var(--muted)}.pill.rec{background:var(--acc-soft);color:var(--acc)}
.tabs{display:flex;gap:6px;margin:24px 0 12px;border-bottom:1px solid var(--line)}
.tab{border:0;background:none;padding:10px 12px;min-height:44px;cursor:pointer;color:var(--muted);font-weight:600;border-bottom:2px solid transparent;margin-bottom:-1px}
.tab[aria-selected=true]{color:var(--fg);border-color:var(--fg)}.tab .n{font-weight:500;color:var(--faint);margin-left:4px}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:0 14px;min-height:36px;cursor:pointer;font-size:14px}
.chip[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.search{flex:1;min-width:180px;border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:0 12px;min-height:40px}
.sort{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:0 10px;min-height:40px}
.list{display:flex;flex-direction:column;gap:8px}
.row{display:grid;grid-template-columns:minmax(150px,1.4fr) 1fr 110px 92px 90px 20px;gap:12px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-height:60px;cursor:pointer;text-align:left;width:100%}
.row:hover{border-color:var(--faint)}.row:focus-visible,.btn:focus-visible,.chip:focus-visible,.tab:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.r-route{font-weight:600}.r-dest{font-size:13px;color:var(--muted)}.r-meta{font-size:13px;color:var(--muted)}
.r-price{font-weight:600;font-size:16px;text-align:right}.r-var{text-align:right}.chev{color:var(--faint)}
.spark{width:90px;height:28px}
.grp{display:flex;align-items:baseline;justify-content:space-between;margin:18px 2px 4px;font-weight:600}.grp:first-child{margin-top:0}.grp span{font-weight:500;color:var(--muted);font-size:13px}
.pill.trip{background:var(--sunk);color:var(--muted);font-weight:500}.pill.cheap{background:var(--good);color:var(--panel)}
.empty{background:var(--panel);border:1px dashed var(--line);border-radius:var(--r);padding:28px 20px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--fg);font-size:16px;margin-bottom:6px}
.sk{background:linear-gradient(90deg,var(--sunk),var(--line),var(--sunk));background-size:200% 100%;animation:sk 1.2s infinite;border-radius:8px;color:transparent!important}
@keyframes sk{to{background-position:-200% 0}}
.banner{display:none;margin-top:16px;padding:12px 14px;border-radius:12px;background:var(--bad-soft);color:var(--bad);font-size:14px}
.banner.show{display:block}
.feed-item,.alert-item{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;text-decoration:none}
.feed-item:hover{border-color:var(--faint)}.feed-src{font-size:12px;color:var(--muted);margin-top:4px}
.links{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.links a{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:10px;border:1px solid var(--line);text-decoration:none;font-size:14px;font-weight:600}
.links a.primary{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.drawer-bg{position:fixed;inset:0;background:rgba(0,0,0,.32);opacity:0;pointer-events:none;transition:opacity .2s}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(440px,100%);background:var(--panel);border-left:1px solid var(--line);transform:translateX(100%);transition:transform .25s ease;padding:20px;overflow:auto;z-index:20}
.open .drawer-bg{opacity:1;pointer-events:auto}.open .drawer{transform:none}
.d-head{display:flex;justify-content:space-between;align-items:start;gap:12px}.x{border:0;background:var(--sunk);border-radius:10px;min-width:40px;min-height:40px;cursor:pointer;font-size:18px}
.d-price{font:600 32px "Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;margin:14px 0 4px}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:16px 0}.fact{background:var(--sunk);border-radius:10px;padding:10px 12px}.fact span{display:block;font-size:12px;color:var(--muted)}
.rng{display:flex;gap:6px;margin:8px 0}
.chart{width:100%;height:180px}.chart text{fill:var(--muted);font-size:11px}
.foot{margin-top:28px;font-size:12.5px;color:var(--muted)}
.bnav{display:none}
@media (max-width:760px){
 .kpis{grid-template-columns:repeat(3,1fr);gap:8px}.hero{grid-column:1/-1}.kpis .card{padding:12px}.kpis .k-val{font-size:22px}.kpis .hero .k-val{font-size:30px}.kpis .k-note{font-size:12px}.k-label{font-size:11px}
 #v-prices{margin-top:16px}
 #conts,#origins{flex-wrap:nowrap!important;overflow-x:auto;scrollbar-width:none;margin-right:-16px;padding-right:16px}#conts .chip,#origins .chip{flex:none}
 .grp{flex-direction:column;gap:2px}
 .row{grid-template-columns:1fr auto;grid-template-areas:"a c" "b d";row-gap:4px}
 .row .r-a{grid-area:a}.row .r-b{grid-area:b}.row .r-price{grid-area:c}.row .r-var{grid-area:d}.row .spark,.row .chev{display:none}
 .tabs{display:none}header .btn{display:none}
 .bnav{display:grid;grid-template-columns:repeat(3,1fr);position:fixed;left:0;right:0;bottom:0;background:var(--panel);border-top:1px solid var(--line);padding:6px 8px calc(6px + env(safe-area-inset-bottom));z-index:10}
 .bnav button{border:0;background:none;min-height:48px;font-weight:600;color:var(--muted);border-radius:10px}.bnav button[aria-selected=true]{color:var(--fg);background:var(--sunk)}
 .fab{position:fixed;left:16px;right:16px;bottom:calc(72px + env(safe-area-inset-bottom));z-index:9;justify-content:center;box-shadow:0 6px 20px rgba(0,0,0,.18)}
 .drawer{top:auto;width:100%;max-height:88vh;border-radius:18px 18px 0 0;border-left:0;border-top:1px solid var(--line);transform:translateY(100%)}
}
@media (min-width:761px){.fab{display:none}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style></head><body>
<div class="wrap">
 <header><div><h1>Radar de vuelos</h1><div class="sub" id="when"><span class="sk">Cargando estado…</span></div></div>
  <div><button class="btn" id="go">Buscar ahora</button><div class="prog"><i id="bar"></i></div></div></header>
 <div class="banner" id="offline" role="alert">El panel se desconectó. Abrí <b>3_abrir_panel.bat</b> para volver a verlo; tus datos siguen guardados.</div>
 <section class="kpis" aria-label="Resumen">
  <div class="card hero" id="hero"><div><div class="k-label">Mejor oportunidad</div><div class="k-val sk">USD 000</div><div class="k-note sk">Cargando</div></div></div>
  <div class="card"><div class="k-label">Tramos baratos</div><div class="k-val sk" id="k-below">0</div><div class="k-note" id="k-below-n">15% o más bajo lo normal</div></div>
  <div class="card"><div class="k-label">Vuelos analizados</div><div class="k-val sk" id="k-routes">0</div><div class="k-note" id="k-sweeps">en la última búsqueda</div></div>
  <div class="card"><div class="k-label">Alertas de error</div><div class="k-val sk" id="k-alerts">0</div><div class="k-note">últimos 14 días</div></div>
 </section>
 <nav class="tabs" role="tablist">
  <button class="tab" role="tab" data-tab="prices" aria-selected="true">Precios<span class="n" id="n-prices"></span></button>
  <button class="tab" role="tab" data-tab="alerts" aria-selected="false">Alertas<span class="n" id="n-alerts"></span></button>
  <button class="tab" role="tab" data-tab="feed" aria-selected="false">Ofertas<span class="n" id="n-feed"></span></button>
 </nav>
 <section id="v-prices">
  <div class="tools"><div id="origins" style="display:flex;gap:6px;flex-wrap:wrap"></div>
   <input class="search" id="q" type="search" placeholder="Buscar destino: Miami, san pablo, MAD…" aria-label="Buscar destino">
   <select class="sort" id="group" aria-label="Agrupar"><option value="home">Rosario / otros</option><option value="continent">Por continente</option><option value="country">Por país</option><option value="none">Sin agrupar</option></select>
   <select class="sort" id="sort" aria-label="Ordenar"><option value="opp">Mejor oportunidad</option><option value="price">Precio más bajo</option><option value="route">Ruta A–Z</option></select></div>
  <div id="conts" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px"></div>
  <div class="list" id="routes"></div>
 </section>
 <section id="v-alerts" hidden><div class="list" id="alerts"></div></section>
 <section id="v-feed" hidden><div class="list" id="feed"></div></section>
 <div class="foot">Fuentes: Google Flights (3 fechas por ruta, con 1 valija) · Aviasales vía Travelpayouts (los más baratos de todo el mes; a las low-cost se les suma la valija estimada) · Promociones Aéreas y Fly4free (ofertas publicadas) · DolarAPI (dólar oficial). Las búsquedas automáticas corren cada 6 h con la PC prendida.</div>
</div>
<button class="btn fab" id="go2">Buscar ahora</button>
<nav class="bnav" role="tablist"><button data-tab="prices" aria-selected="true">Precios</button><button data-tab="alerts" aria-selected="false">Alertas</button><button data-tab="feed" aria-selected="false">Ofertas</button></nav>
<div id="dr"><div class="drawer-bg" id="dbg"></div><aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-labelledby="d-title"></aside></div>
<script>
const $=id=>document.getElementById(id);
const usd=v=>v==null?'—':'USD '+new Intl.NumberFormat('es-AR',{maximumFractionDigits:0}).format(v);
const pct=v=>(v>0?'+':'')+Math.round(v*100)+'%';
const dt=s=>s?new Date(s).toLocaleString('es-AR',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:false}):'—';
const ago=s=>{if(!s)return 'nunca';const m=Math.round((Date.now()-new Date(s))/60000);if(m<1)return 'recién';if(m<60)return `hace ${m} min`;const h=Math.round(m/60);return h<24?`hace ${h} h`:`hace ${Math.round(h/24)} d`};
const norm=s=>(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
const el=(t,c,txt)=>{const e=document.createElement(t);if(c)e.className=c;if(txt!=null)e.textContent=txt;return e};
let S=null,etag=null,ui={tab:'prices',origin:'',q:'',sort:'opp',group:'home',cont:''},polling=false;

function varPill(r){
 if(r.variation==null){const p=el('span','pill flat',r.samples<1?'nuevo':`${r.samples}/${S.kpis.min_samples} búsq.`);p.title='Se compara con lo normal desde la búsqueda '+S.kpis.min_samples;return p}
 const v=r.variation,c=Math.abs(v)<0.02?'flat':v<0?'down':'up';return el('span','pill '+c,Math.abs(v)<0.02?'= normal':pct(v))}
function spark(vals){
 const ns='http://www.w3.org/2000/svg',s=document.createElementNS(ns,'svg');s.setAttribute('class','spark');s.setAttribute('viewBox','0 0 90 28');s.setAttribute('aria-hidden','true');
 if(vals.length<2)return s;const lo=Math.min(...vals),hi=Math.max(...vals),sp=hi-lo||1;
 const pts=vals.map((v,i)=>[i/(vals.length-1)*86+2,24-(v-lo)/sp*20]);const p=document.createElementNS(ns,'polyline');
 p.setAttribute('points',pts.map(x=>x.join(',')).join(' '));p.setAttribute('fill','none');p.setAttribute('stroke','var(--faint)');p.setAttribute('stroke-width','1.5');p.setAttribute('stroke-linejoin','round');s.append(p);
 const c=document.createElementNS(ns,'circle');const l=pts.at(-1);c.setAttribute('cx',l[0]);c.setAttribute('cy',l[1]);c.setAttribute('r','2.5');c.setAttribute('fill','var(--acc)');s.append(c);return s}

function renderKpis(){
 const k=S.kpis,b=S.best,h=$('hero');h.textContent='';
 const top=el('div');top.append(el('div','k-label','Mejor oportunidad'));
 if(b){top.append(el('div','route',`${b.origin} → ${b.dest_name}`),el('div','k-val',usd(b.usd)));
  const n=el('div','k-note');n.append(varPill(b),` vs. lo normal (${usd(b.median)}) · ${b.trip==='ida'?'solo ida':'ida y vuelta'} · sale ${b.depart_date}`);top.append(n);
  const go=el('button','btn ghost','Ver detalle');go.onclick=()=>openRoute(b);h.append(top,go)}
 else{top.append(el('div','k-val','—'),el('div','k-note',k.routes?(()=>{const mx=Math.max(0,...S.routes.map(r=>r.samples));if(mx>=k.min_samples)return 'Hoy ningún precio está al menos 5% por debajo de lo normal. Cuando aparezca uno, lo vas a ver acá.';const need=k.min_samples-mx;return `Juntando historial: falta${need>1?'n':''} ${need} búsqueda${need>1?'s':''} más para comparar cada precio con lo normal.`})():'Todavía no hay precios. Tocá “Buscar ahora”.'));h.append(top)}
 $('k-below').textContent=k.cheap_legs;$('k-below-n').textContent=`15% o más bajo lo normal · ${k.below_normal} algo más baratos`;$('k-routes').textContent=new Intl.NumberFormat('es-AR').format(k.flights_last);$('k-alerts').textContent=k.alerts;
 $('k-sweeps').textContent=`última búsqueda · ${Object.entries(k.flights_by_source).map(([s,n])=>s+' '+n).join(' · ')} · ${k.routes} rutas · ${new Intl.NumberFormat('es-AR').format(k.flights_total)} en total (${k.sweeps} búsquedas)`;
 ['k-below','k-routes','k-alerts'].forEach(i=>$(i).classList.remove('sk'));
 $('n-prices').textContent=k.routes||'';$('n-alerts').textContent=k.alerts||'';$('n-feed').textContent=k.feed||'';
}
function renderOrigins(){
 const box=$('origins');if(box.childElementCount)return box.querySelectorAll('.chip').forEach(c=>c.setAttribute('aria-pressed',String(c.dataset.o===ui.origin)));
 ['',...[...new Set(S.routes.map(r=>r.origin))].sort()].forEach(o=>{const c=el('button','chip',o||'Todos');c.dataset.o=o;c.setAttribute('aria-pressed',String(o===ui.origin));c.onclick=()=>{ui.origin=o;renderOrigins();renderRoutes()};box.append(c)})}
function renderConts(){
 const box=$('conts');box.textContent='';
 ['',...[...new Set(S.routes.map(r=>r.continent))].sort()].forEach(c=>{const b=el('button','chip',c||'Todos los destinos');b.setAttribute('aria-pressed',String(c===ui.cont));b.onclick=()=>{ui.cont=c;renderConts();renderRoutes()};box.append(b)})}
function routeRow(r){const b=el('button','row');b.onclick=()=>openRoute(r);
  const a=el('div','r-a');a.append(el('div','r-route',`${r.origin} → ${r.destination}`),el('div','r-dest',`${r.dest_name} · ${r.country}`));
  const m=el('div','r-b r-meta',`${r.depart_date} · ${r.carrier==='MULTI'?'varias aerolíneas':r.carrier} · ${r.stops?r.stops+' escala'+(r.stops>1?'s':''):'directo'} `);
  m.append(el('span','pill trip',r.trip==='ida'?'solo ida':'ida y vuelta'));m.append(' ');m.append(el('span','pill trip',`${r.options} vuelo${r.options===1?'':'s'} · mejor en ${r.source_label}`));
  if(r.cheap_leg){m.append(' ');m.append(el('span','pill cheap','tramo barato'))}
  if(r.is_record){m.append(' ');m.append(el('span','pill rec','mínimo histórico'))}
  const v=el('div','r-var');v.append(varPill(r));
  b.append(a,m,spark(r.spark),v,el('div','r-price',usd(r.usd)),el('span','chev','›'));return b}
function renderRoutes(){
 const L=$('routes');L.textContent='';
 if(!S.routes.length){const e=el('div','empty');e.append(el('b',null,'Todavía no hay precios'),'Tocá “Buscar ahora”: la primera búsqueda tarda unos 8 minutos.');L.append(e);return}
 const q=norm(ui.q);let rows=S.routes.filter(r=>(!ui.origin||r.origin===ui.origin)&&(!ui.cont||r.continent===ui.cont)&&(!q||norm(`${r.origin} ${r.destination} ${r.dest_name} ${r.country} ${r.continent}`).includes(q)));
 const sorters={opp:(a,b)=>(a.variation??9)-(b.variation??9)||a.usd-b.usd,price:(a,b)=>a.usd-b.usd,route:(a,b)=>(a.origin+a.destination).localeCompare(b.origin+b.destination)};
 rows.sort(sorters[ui.sort]);
 if(!rows.length){const e=el('div','empty');e.append(el('b',null,'Sin resultados'),'Probá con otro destino o elegí “Todos”.');L.append(e);return}
 const keyOf={home:r=>r.origin==='ROS'?'Desde Rosario':'Desde otros aeropuertos',continent:r=>r.continent,country:r=>r.country,none:()=>''}[ui.group];
 const order={home:['Desde Rosario','Desde otros aeropuertos']}[ui.group];
 const groups=new Map();rows.forEach(r=>{const k=keyOf(r);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)});
 const keys=[...groups.keys()].sort((x,y)=>order?order.indexOf(x)-order.indexOf(y):Math.min(...groups.get(x).map(r=>r.usd))-Math.min(...groups.get(y).map(r=>r.usd)));
 if(ui.group==='home'&&!groups.has('Desde Rosario')&&!ui.origin){const h=el('div','grp','Desde Rosario');L.append(h);const e=el('div','empty','Sin vuelos encontrados desde Rosario en esta búsqueda.');L.append(e)}
 for(const k of keys){const g=groups.get(k);
  if(k){const h=el('div','grp',k);const cheap=g.filter(r=>r.cheap_leg).length;h.append(el('span',null,`${g.length} ruta${g.length>1?'s':''} · ${g.reduce((a,r)=>a+r.options,0)} vuelos · desde ${usd(Math.min(...g.map(r=>r.usd)))}${cheap?` · ${cheap} tramo${cheap>1?'s':''} barato${cheap>1?'s':''}`:''}`));L.append(h)}
  g.forEach(r=>L.append(routeRow(r)))}
}
function renderAlerts(){
 const L=$('alerts');L.textContent='';
 if(!S.alerts.length){const e=el('div','empty');e.append(el('b',null,'Ningún precio está anormalmente bajo'),S.kpis.sweeps<5?'El detector necesita unos días de historial por ruta. Te avisa acá (y por Telegram, si lo configurás) cuando aparezca un error de tarifa.':'Te avisamos acá cuando aparezca un error de tarifa.');L.append(e);return}
 for(const r of S.alerts){const it=el('div','alert-item');
  it.append(el('div','r-route',`${r.origin} → ${r.dest_name} · ${usd(r.usd_allin)}`),el('div','r-meta',`${r.depart_date} · ${r.carrier} · ${Math.round(r.saving_usd)} USD bajo lo normal · ${r.kind} · encontrada ${ago(r.found_at)}`));
  const ls=el('div','links');[['Google Flights',r.google_flights,1],['Skyscanner',r.skyscanner],['Kayak',r.kayak]].forEach(([t,h,p])=>{const x=el('a',p?'primary':'',t+' ↗');x.href=h;x.target='_blank';x.rel='noopener';ls.append(x)});it.append(ls);L.append(it)}
}
function renderFeed(){
 const L=$('feed');L.textContent='';
 if(!S.feed.length){const e=el('div','empty');e.append(el('b',null,'Sin ofertas nuevas'),'Las ofertas de Promociones Aéreas y Fly4free que salen de Argentina aparecen acá después de cada búsqueda.');L.append(e);return}
 for(const f of S.feed){const a=el('a','feed-item');a.href=f.link;a.target='_blank';a.rel='noopener';a.append(el('div',null,f.title),el('div','feed-src',`${f.source} · ${ago(f.seen_at)}`));L.append(a)}
}
function renderAll(){renderKpis();renderOrigins();renderConts();renderRoutes();renderAlerts();renderFeed()}

async function openRoute(r){
 const d=$('drawer');d.textContent='';$('dr').classList.add('open');
 const head=el('div','d-head');const t=el('div');const h=el('h2',null,`${r.origin} → ${r.dest_name}`);h.id='d-title';h.style.margin='0';h.style.fontSize='18px';
 t.append(h,el('div','sub',`${r.country} · ${r.continent} · ${r.trip==='ida'?'solo ida':'ida y vuelta'} · precio de ${r.source_label} · sale ${r.depart_date} · ${r.carrier==='MULTI'?'varias aerolíneas':r.carrier} · ${r.stops?r.stops+' escala(s)':'directo'}`));
 const x=el('button','x','×');x.setAttribute('aria-label','Cerrar');x.onclick=closeDrawer;head.append(t,x);
 const pr=el('div','d-price',usd(r.usd));const pv=el('div');pv.append(varPill(r));if(r.cheap_leg){pv.append(' ');pv.append(el('span','pill cheap','tramo barato'))}
 const facts=el('div','facts');[['Lo normal (mediana)',usd(r.median)],['Mínimo visto',usd(r.min_seen)],['Vuelos encontrados',`${r.options} en la última búsqueda`],['Búsquedas',String(r.samples+1)],['Incluye','1 valija despachada']].forEach(([k,v])=>{const f=el('div','fact');f.append(el('span',null,k),v);facts.append(f)});
 const rng=el('div','rng');const ch=el('div');
 const ls=el('div','links');[[r.buy_label,r.buy_url,1],...(r.source==='google'?[]:[['Google Flights',r.google_flights]]),['Skyscanner',r.skyscanner],['Kayak',r.kayak]].forEach(([tt,hh,p])=>{const a=el('a',p?'primary':'',tt+' ↗');a.href=hh;a.target='_blank';a.rel='noopener';ls.append(a)});
 d.append(head,pr,pv,facts,el('div','k-label','Historial'),rng,ch,ls,el('div','foot','El precio puede cambiar al abrir el sitio: Google Flights se actualiza en tiempo real.'));
 x.focus();
 {const sk=el('div','sk','');sk.style.height='180px';ch.append(sk)}
 let hist=[];try{hist=(await (await fetch(`/api/route?o=${r.origin}&d=${r.destination}&s=${r.source}`)).json()).history}catch(e){}
 const draw=days=>{ch.textContent='';const cut=days?Date.now()-days*864e5:0;const pts=hist.filter(p=>new Date(p.observed_at)>=cut);
  if(pts.length<2){ch.append(el('div','empty',pts.length?'Solo hay una búsqueda en este rango.':'Sin datos en este rango.'));return}
  const ns='http://www.w3.org/2000/svg',W=400,H=180,ml=44,mb=22,s=document.createElementNS(ns,'svg');s.setAttribute('viewBox',`0 0 ${W} ${H}`);s.setAttribute('class','chart');
  const xs=pts.map(p=>+new Date(p.observed_at)),ys=pts.map(p=>p.min_usd).concat(r.median?[r.median]:[]);const x0=Math.min(...xs),x1=Math.max(...xs),lo=Math.min(...ys)*.95,hi=Math.max(...ys)*1.05;
  const X=t=>ml+(t-x0)/(x1-x0||1)*(W-ml-8),Y=v=>8+(1-(v-lo)/(hi-lo||1))*(H-8-mb);const add=(n,a,txt)=>{const e=document.createElementNS(ns,n);for(const k in a)e.setAttribute(k,a[k]);if(txt)e.textContent=txt;s.append(e);return e};
  [lo,(lo+hi)/2,hi].forEach(v=>{add('line',{x1:ml,x2:W-8,y1:Y(v),y2:Y(v),stroke:'var(--line)'});add('text',{x:ml-6,y:Y(v)+4,'text-anchor':'end'},Math.round(v))});
  [x0,x1].forEach((t,i)=>add('text',{x:X(t),y:H-6,'text-anchor':i?'end':'start'},new Date(t).toLocaleDateString('es-AR',{day:'numeric',month:'short'})));
  if(r.median)add('line',{x1:ml,x2:W-8,y1:Y(r.median),y2:Y(r.median),stroke:'var(--muted)','stroke-dasharray':'4 4'});
  add('polyline',{points:pts.map(p=>`${X(+new Date(p.observed_at))},${Y(p.min_usd)}`).join(' '),fill:'none',stroke:'var(--acc)','stroke-width':2,'stroke-linejoin':'round','stroke-linecap':'round'});
  const l=pts.at(-1);add('circle',{cx:X(+new Date(l.observed_at)),cy:Y(l.min_usd),r:4,fill:'var(--acc)'});ch.append(s);
  if(r.median){const n=el('div','sub','Línea punteada: lo normal para esta ruta.');ch.append(n)}};
 [['7 días',7],['30 días',30],['Todo',0]].forEach(([t,dd],i)=>{const c=el('button','chip',t);c.setAttribute('aria-pressed',String(i===2));c.onclick=()=>{rng.querySelectorAll('.chip').forEach(z=>z.setAttribute('aria-pressed','false'));c.setAttribute('aria-pressed','true');draw(dd)};rng.append(c)});
 draw(0);
}
function closeDrawer(){$('dr').classList.remove('open')}
$('dbg').onclick=closeDrawer;document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});

function setTab(t){ui.tab=t;['prices','alerts','feed'].forEach(x=>{$('v-'+x).hidden=x!==t});document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===t)))}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
$('q').oninput=e=>{ui.q=e.target.value;renderRoutes()};$('sort').onchange=e=>{ui.sort=e.target.value;renderRoutes()};$('group').onchange=e=>{ui.group=e.target.value;renderRoutes()};

async function loadSummary(){
 try{const r=await fetch('/api/summary',{headers:etag?{'If-None-Match':etag}:{}});$('offline').classList.remove('show');
  if(r.status===304)return;etag=r.headers.get('ETag');S=await r.json();renderAll()}
 catch(e){$('offline').classList.add('show')}}
function paintStatus(st){
 const btns=[$('go'),$('go2')];const k=S?S.kpis:{};
 if(st.running){const p=st.total?Math.min(100,Math.round(st.progress/st.total*100)):0;let eta='calculando…';
  // ritmo de los últimos ~90 s: Travelpayouts es casi instantáneo y Google lento, el promedio total engaña
  const now=Date.now();window._pp=(window._pp||[]).filter(x=>now-x[0]<90000);window._pp.push([now,st.progress]);
  const a=window._pp[0],b=window._pp.at(-1);const rate=(b[1]-a[1])/((b[0]-a[0])/1000);
  if(b[0]-a[0]>8000&&rate>0){const m=Math.ceil((st.total-st.progress)/rate/60);eta=m<=1?'menos de 1 min':`~${m} min`}
  btns.forEach(b=>{b.disabled=true;b.textContent=`Buscando… ${p}% · ${eta}`});$('bar').style.width=p+'%'}
 else{btns.forEach(b=>{b.disabled=false;b.textContent='Buscar ahora'});$('bar').style.width='0'}
 $('when').textContent=k.last_sweep?`Última búsqueda ${ago(k.last_sweep)} (${dt(k.last_sweep)}) · ${new Intl.NumberFormat('es-AR').format(k.flights_last||0)} vuelos encontrados · próxima automática ≈ ${dt(k.next_sweep_approx)}`:'Sin búsquedas todavía';
 if(st.message&&!st.running&&st.last_run)$('when').textContent+=` · ${st.message}`}
async function pollStatus(){
 if(polling)return;polling=true;let was=false;
 while(true){let st;try{st=await (await fetch('/api/status')).json();$('offline').classList.remove('show')}catch(e){$('offline').classList.add('show');break}
  paintStatus(st);if(!st.running){window._pp=[];if(was)await loadSummary();paintStatus(st);break}was=true;await new Promise(r=>setTimeout(r,3000))}
 polling=false}
async function start(){try{await fetch('/api/refresh',{method:'POST'})}catch(e){$('offline').classList.add('show');return}pollStatus()}
$('go').onclick=start;$('go2').onclick=start;
(async()=>{await loadSummary();pollStatus();setInterval(()=>{loadSummary();pollStatus()},60000)})();
</script></body></html>"""


def serve(demo: bool, port: int = 8765, open_browser: bool = True):
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    def run_bg():
        try:
            asyncio.run(run_once(demo, export=True))
        except Exception as e:
            print("Barrido falló:", e)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="application/json", headers=None):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            if code != 304:
                self.send_header("Content-Type", ctype + "; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-cache")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if code != 304:
                self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(200, PANEL_HTML, "text/html")
            if u.path == "/api/status":
                return self._send(200, json.dumps(live_status()))
            con = db()
            try:
                if u.path == "/api/summary":
                    last = con.execute("SELECT MAX(observed_at) FROM fares").fetchone()[0]
                    n_feed = con.execute("SELECT COUNT(*) FROM feed_items").fetchone()[0]
                    tag = f'"{last}|{n_feed}"'
                    if self.headers.get("If-None-Match") == tag:
                        return self._send(304)
                    return self._send(200, json.dumps(build_summary(con)), headers={"ETag": tag})
                if u.path == "/api/route":
                    q = parse_qs(u.query)
                    return self._send(200, json.dumps(route_detail(con, q["o"][0], q["d"][0], q.get("s", ["google"])[0])))
                return self._send(404, "{}")
            finally:
                con.close()

        def do_POST(self):
            if urlparse(self.path).path != "/api/refresh":
                return self._send(404, "{}")
            if not STATUS["running"]:
                STATUS["running"] = True
                threading.Thread(target=run_bg, daemon=True).start()
            return self._send(202, json.dumps({"started": True}))

    db().close()  # crea tablas, índices y vista
    import socket
    with socket.socket() as probe:  # en Windows dos servidores pueden compartir puerto: chequeamos antes
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"El panel ya está corriendo en http://localhost:{port}")
            if open_browser:
                webbrowser.open(f"http://localhost:{port}")
            return
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    except OSError:
        print(f"El puerto {port} ya está en uso: el panel ya está corriendo en http://localhost:{port}")
        return
    with open("panel.pid", "w") as fpid:  # para poder apagarlo desde 6_desactivar_segundo_plano.bat
        fpid.write(str(os.getpid()))
    url = f"http://localhost:{port}"
    print(f"Panel en {url}  (Ctrl+C para cerrar)")
    try:
        if open_browser:
            webbrowser.open(url)
    except Exception:
        pass
    srv.serve_forever()


def main():
    import sys
    for stream in (sys.stdout, sys.stderr):  # Windows: evita errores con emojis al escribir en monitor.log
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="datos sintéticos, sin internet")
    ap.add_argument("--serve", action="store_true", help="abre el panel local con botón 'Buscar ahora'")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="no abre el navegador (modo segundo plano)")
    ap.add_argument("--estimate", action="store_true", help="muestra cuántas búsquedas hace cada barrido")
    ap.add_argument("--export", action="store_true", help="exporta CSVs (dashboard_data/)")
    args = ap.parse_args()

    if args.estimate:
        n = len(search_grid()) * len(CABINS)
        print(f"{len(ORIGINS)} orígenes × {len(DESTINATIONS)} destinos × {N_DATES} fechas × {len(CABINS)} cabinas"
              f" = {n} búsquedas por barrido (~{n * 6.5 / 60:.0f} min con las pausas)")
        return
    if args.serve:
        return serve(args.demo, args.port, open_browser=not args.no_browser)
    asyncio.run(run_once(args.demo, args.export))


if __name__ == "__main__":
    main()
