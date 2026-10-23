# Contrato de datos de la interfaz web

La interfaz (`web/index.html`) se abre con doble clic y **no usa servidor**: lee dos tipos de archivos que son scripts
(un HTML abierto desde el disco no puede usar `fetch`, pero sí cargar scripts). Están pensados para decenas de miles de productos:

| Archivo | Qué entrega | Cuándo se carga |
|---|---|---|
| `data/index.js` (define `window.CATALOGO_INDEX`) | **Índice liviano**: una fila corta por producto (nombre, marca, categoría, precio de cada cadena…). ~3 MB cada 25.000 productos | Una sola vez al abrir. Con esto se **busca y filtra en el navegador** |
| `data/d/XX.js` (256 archivos, llaman a `window.__shard(XX, {id: Item})`) | **Detalle completo**: ofertas por cadena, promos, historial. Cada producto está en el archivo `XX` = FNV-1a 32 bits del `id` módulo 256, en hexadecimal de 2 dígitos | Solo los archivos que hagan falta para mostrar un producto |

Opcional, solo con el panel (`iniciar_panel.bat`): `GET /api/buscar?q=<texto>` hace una **búsqueda en vivo** en las cadenas (20 a 30 s) para
lo que no esté en el catálogo.

Un ejemplo chico con la forma exacta del **detalle** está en `mock/catalogo.mock.json`.
`python catalogo.py` genera `data/` desde `precios.db` (corre cada noche en `run_all.py`).

## `data/index.js` (índice)

```jsonc
{
  "generated_at": "2026-10-03T14:21:00+00:00",                  // ISO 8601, UTC
  "chains":     [ { "id": "carrefour", "label": "Carrefour" } ], // el orden define la posición en "prices"
  "categories": [ { "name": "Almacén", "count": 3904 } ],        // el orden define el índice "cat"
  "fields": ["id","name","brand","size_text","cat","denom","basis","prices","flags","max_discount","n_chains","spread_pct"],
  "rows": [
    ["ean:7792070009109", "Cerveza Lager HEINEKEN Lata 473 Cc", "Heineken", "473 ml", 2, 0.473, 2,
     [3023, 0, 3380, 4030, 0], 1, 40, 3, 36]
  ]
}
```

| Campo (posición) | Tipo | Descripción |
|---|---|---|
| `id` (0) | string | `ean:<EAN>`, o `<cadena>:<sku>` si el producto está en una sola cadena sin EAN |
| `name` (1) | string | Nombre de la cadena preferida (orden Carrefour, Coto, Jumbo…) |
| `brand` (2) | string | Marca (vacío si no se conoce) |
| `size_text` (3) | string | `"473 ml"`, `"1 kg"` (vacío si no se pudo leer) |
| `cat` (4) | integer | Índice en `categories` |
| `denom` (5) | number | kg o litros de una unidad. **Precio por kg/litro = precio / denom** (0 = no calculable) |
| `basis` (6) | 0, 1, 2 | 0 ninguna, 1 = `$/kg`, 2 = `$/l` |
| `prices` (7) | integer[] | Precio final en cada cadena, en el orden de `chains` (0 = no la tiene) |
| `flags` (8) | bitmask | 1 = oferta fuerte (descuento ≥ 30 % o promo nxm / pct_nth / bulk), 2 = posible anomalía de precio |
| `max_discount` (9) | integer | Mayor descuento % entre cadenas |
| `n_chains` (10) | integer | En cuántas cadenas está |
| `spread_pct` (11) | integer | % entre la más barata y la más cara por kg/litro |

## `data/d/XX.js` (detalle)

```js
window.__shard && window.__shard("20", { "ean:7792070009109": /* Item */, "jumbo:123456": /* Item */ });
```
Para ahorrar espacio, cada Offer omite los campos vacíos (`null`, `false`), `chain_label` (se deduce de `chains` del índice) y `basis`
(es el del producto). El cliente los completa al cargar.

### Item

| Campo | Tipo | Descripción |
|---|---|---|
| `id`, `name`, `brand`, `category`, `size_text`, `pack`, `ean`, `basis` | | Igual que el índice (`category` como texto, `pack` = unidades del pack) |
| `offers` | Offer[] | **Ordenadas de menor a mayor precio unitario**; `offers[0]` es la más barata |
| `stats` | Stats | `n_chains`, `min_price`, `max_price`, `min_unit`, `max_unit`, `spread_pct`, `best_chain`, `best_discount`, `aggressive` |
| `anomaly` | Anomaly \| null | Precio muy por debajo de la mediana del mercado |
| `history` | HistoryPoint[] | Hasta 30 días, un punto por día |

### Offer (el producto en una cadena)

| Campo | Tipo | Descripción |
|---|---|---|
| `chain`, `chain_label` | string | id y nombre visible |
| `title` | string | Nombre exacto en esa cadena |
| `price` | integer | Precio final de góndola (ARS). Con promo `nxm`/`pct_nth`/`bulk` es el **precio efectivo por unidad** |
| `list_price` | integer \| null | Precio anterior tachado (solo cadenas con lista confiable; Jumbo trae una lista rota y se omite) |
| `unit_price`, `basis` | integer, string | `price` por kg o litro, y `"$/kg"` o `"$/l"` |
| `promo` | string \| null | Texto original de la cadena |
| `promo_type` | enum \| null | `nxm` (2x1, 3x2), `pct_nth` (70 % 2da), `bulk` (Llevando 2), `card` (tarjeta), `installments`, `pct` (25 % Dto), `offer` |
| `promo_label` | string \| null | Etiqueta corta lista para mostrar |
| `discount_pct` | integer \| null | % de descuento sobre lista o sobre la etiqueta de la promo |
| `url` | string | Link al producto en la cadena |
| `flag` | boolean | `true` si esta oferta es la que disparó la anomalía |

### Anomaly e HistoryPoint

```jsonc
{ "type": "posible_error",   // "posible_error" (< 50 % de la mediana, confirmado por EAN) | "bajo_mercado" (< 70 %)
  "chain": "Carrefour", "ratio": 0.59, "detail": "59% de la mediana de 7 cadenas (3,150)" }

{ "d": "2026-10-03", "min": 893, "by_chain": { "lagallega": 893, "carrefour": 919 } }
```
Con menos de 2 días de datos la interfaz muestra un aviso en lugar del gráfico del historial.

## `GET /api/buscar?q=<texto>` (búsqueda en vivo)

```jsonc
{ "term": "473 heineken lata",          // lo que escribió la persona
  "search_term": "heineken",            // lo que se les pidió a las cadenas (sin números ni envases)
  "at": "2026-10-03T14:10:00+00:00",
  "errors": { "coto": "ReadTimeout: ..." },   // cadenas que no respondieron
  "rows": [ { "chain": "coto", "chain_label": "Coto", "title": "...", "brand": null, "price": 1199,
              "list_price": 2126, "promo": "40%Dto", "unit_price": 2535, "basis": "$/l", "size": "473 ml",
              "pack": 1, "url": "https://..." } ] }
```
La interfaz filtra `rows` en el navegador con el buscador tolerante (`search.js`), por eso `search_term` puede ser más corto que lo escrito.

## Buscador tolerante (`search.js`)

```js
const index = PriceSearch.createIndex(items);        // una vez; items con name, brand, size_text, category
const { results, partial, unknown } = PriceSearch.search(index, "473 heineken lata", { limit: 20 });
```
- Orden de palabras indiferente; sin tildes ni mayúsculas; `473`, `473cc` y `473ml` equivalen y `1 kg` equivale a `1000 g`; plurales simples.
- Errores de tipeo leves (1 letra en palabras de 4 a 7 letras, 2 desde 8); la última palabra se completa como prefijo (autocompletado).
- Deben coincidir todas las palabras; si ninguna alcanza, se muestran las que coinciden con dos tercios (`partial: true`).
- Si una palabra no existe en ningún producto, no hay resultados y se informa en `unknown` (ej. una marca que no está).
- **Escala:** índice invertido. Con 120.000 productos arma el índice en ~0,9 s y cada búsqueda tarda 5 a 15 ms. Pruebas: `node web/search.test.js`.

## Qué cubre el catálogo

Es el relevamiento **completo** de las 5 cadenas en la última corrida nocturna: Carrefour y Jumbo (todas las categorías de la tienda
VTEX), Coto (rubros de supermercado), La Gallega y DAR (catálogo completo). No incluye Electro, Hogar ni Textil. La categoría se toma
de la que asigna cada tienda cuando está disponible y, si no, de palabras del nombre. Lo que no figure se busca en vivo.
