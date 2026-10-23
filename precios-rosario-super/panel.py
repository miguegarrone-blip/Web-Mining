"""Panel local de consulta de precios (sin dependencias externas).

Uso:
    python panel.py            # abre http://127.0.0.1:8765
    python panel.py 9000       # otro puerto

Escribe un término (ej. "cervezas") y busca en vivo en las 8 cadenas. Solo escucha en tu PC
(127.0.0.1). No modifica precios.db.
"""
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import canasta
import consulta

from pathlib import Path

WEB_DIR = Path(__file__).parent / "web"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
CACHE_SECONDS = 600
_cache, _lock = {}, threading.Lock()
_canasta_cache = {}
_gzip_cache = {}


def product_details(ids):
    """Detalle completo (ofertas, promos, historial) de los productos pedidos, en el orden recibido."""
    import sqlite3
    import zlib
    path = WEB_DIR / "data" / "detalle.db"
    if not ids or not path.exists():
        return []
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(ids))
        found = {i: zlib.decompress(d).decode("utf-8") for i, d in db.execute(f"SELECT id, data FROM items WHERE id IN ({marks})", ids)}
    finally:
        db.close()
    return [json.loads(found[i]) for i in ids if i in found]


def canasta_calculada():
    """Calcula (o reutiliza por 10 min) el costo de la canasta y devuelve el HTML del tablero."""
    items = canasta.load_config()["items"]
    key = json.dumps(items, sort_keys=True, ensure_ascii=False)
    with _lock:
        hit = _canasta_cache.get("v")
        if hit and hit[0] == key and time.time() - hit[1] < CACHE_SECONDS:
            return hit[2]
    if not items:
        return {"empty": True}
    result = canasta.calcular(items)
    out = {"html": canasta.build_html(result), "run_at": result["run_at"], "items": len(items)}
    with _lock:
        _canasta_cache["v"] = (key, time.time(), out)
    return out


def buscar_cached(term):
    key = consulta.fold(term).strip()
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
    res = consulta.buscar(term)
    with _lock:
        _cache[key] = (time.time(), res)
    return res


PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Precios Rosario</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#6b7685;--line:#e3e7ec;--acc:#1f6feb;--good:#12805c;--goodbg:#e4f5ee;--warn:#9a5b00;--warnbg:#fff1d6}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1a2029;--ink:#e8ecf1;--mute:#93a0b0;--line:#2a323d;--acc:#5aa2ff;--good:#4cd19b;--goodbg:#143428;--warn:#f1b24a;--warnbg:#3a2c10}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:20px;margin:0 0 14px}
form{display:flex;gap:8px;margin-bottom:14px}
input[type=text]{flex:1;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:16px}
button{padding:11px 18px;border:0;border-radius:10px;background:var(--acc);color:#fff;font-size:15px;font-weight:600;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
.meta{color:var(--mute);font-size:13px;margin:6px 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 12px;cursor:pointer}
.card.on{outline:2px solid var(--acc)}.card.best{border-color:var(--good)}
.card b{display:block;font-size:13px}.card .v{font-size:19px;font-weight:700}.card .s{color:var(--mute);font-size:12px}
.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.tools input{max-width:260px;padding:8px 10px;font-size:14px}
select{padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}
th{font-size:12px;color:var(--mute);text-transform:uppercase;letter-spacing:.03em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:1px 7px;border-radius:99px;font-size:12px;background:var(--goodbg);color:var(--good)}
.tag.p{background:var(--warnbg);color:var(--warn)}
a{color:var(--acc);text-decoration:none}
.err{background:var(--warnbg);color:var(--warn);padding:8px 12px;border-radius:8px;margin-bottom:10px;font-size:13px}
.empty{padding:40px;text-align:center;color:var(--mute)}
.tabs{display:flex;gap:6px;margin-bottom:14px;border-bottom:1px solid var(--line)}
.tab{background:none;color:var(--mute);border-radius:8px 8px 0 0;padding:9px 14px;font-weight:600;border-bottom:2px solid transparent}
.tab.on{color:var(--ink);border-bottom-color:var(--acc)}
.addbtn{padding:3px 10px;font-size:14px;border-radius:7px;background:var(--goodbg);color:var(--good);border:1px solid var(--good)}
.addbtn.done{background:none;color:var(--mute);border-color:var(--line);cursor:default}
.blist{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:12px}
.bitem{display:flex;gap:10px;align-items:center;padding:9px 12px;border-bottom:1px solid var(--line);font-size:14px}
.bitem:last-child{border-bottom:0}.bitem span{flex:1;min-width:0;overflow-wrap:anywhere}
.bitem button{padding:2px 9px;background:none;color:var(--mute);border:1px solid var(--line);border-radius:7px;font-size:13px}
.bactions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.bactions .sec{background:none;color:var(--mute);border:1px solid var(--line)}
iframe#dash{width:100%;height:1500px;border:0;border-radius:12px;background:var(--card)}
@media(max-width:640px){th:nth-child(5),td:nth-child(5){display:none}}
</style></head><body><div class="wrap">
<h1>Precios en Rosario</h1>
<nav class="tabs"><button class="tab on" id="tabB" type="button">Buscar</button><button class="tab" id="tabC" type="button">Mi canasta (0)</button></nav>
<section id="viewB">
<form id="f"><input type="text" id="q" value="" placeholder="Consultá tu producto" autocomplete="off" autofocus><button id="go">Buscar</button></form>
<div id="out"><div class="empty">Consultá tu producto: escribilo arriba y apretá Enter.<br>Ej: cervezas, yerba mate, aceite.<br>Para armar tu canasta, apretá <b>+</b> en los productos que comprás.</div></div>
</section>
<section id="viewC" hidden>
<div id="basketBox"></div>
<div id="basketOut"></div>
</section>
</div>
<script>
let DATA=null, chainSel=null, sortKey='unit', text='';
const $=s=>document.querySelector(s), money=n=>n==null?'-':'$'+Math.round(n).toLocaleString('es-AR');
$('#f').onsubmit=async e=>{e.preventDefault();const q=$('#q').value.trim();if(!q)return;
  $('#go').disabled=true;$('#go').textContent='Buscando…';$('#out').innerHTML='<div class="empty">Consultando las 8 cadenas (20-30 segundos)…</div>';
  try{const r=await fetch('/api/buscar?q='+encodeURIComponent(q));DATA=await r.json();chainSel=null;text='';render();}
  catch(err){$('#out').innerHTML='<div class="err">No se pudo consultar: '+err+'</div>'}
  $('#go').disabled=false;$('#go').textContent='Buscar';};
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){
  const rows=DATA.rows, chains=[...new Set(rows.map(r=>r.chain_label))];
  const stat={};chains.forEach(c=>{const rs=rows.filter(r=>r.chain_label===c);const u=rs.filter(r=>r.unit_price).map(r=>r.unit_price).sort((a,b)=>a-b);
    stat[c]={n:rs.length,min:u[0],med:u.length?u[Math.floor(u.length/2)]:null,cheap:rs.reduce((m,r)=>(!m||r.price<m.price)?r:m,null)}});
  const bestMin=Math.min(...chains.map(c=>stat[c].min).filter(Boolean));
  let list=rows.filter(r=>(!chainSel||r.chain_label===chainSel)&&(!text||(r.title+' '+(r.brand||'')).toLowerCase().includes(text)));
  const key={unit:r=>r.unit_price??1e12,price:r=>r.price,chain:r=>r.chain_label+r.price}[sortKey];
  list=[...list].sort((a,b)=>{const x=key(a),y=key(b);return x<y?-1:x>y?1:0});
  const basis=(rows.find(r=>r.basis)||{}).basis||'';
  let h='';
  const errs=Object.entries(DATA.errors||{});if(errs.length)h+='<div class="err">No respondieron: '+errs.map(e=>e[0]).join(', ')+'</div>';
  h+=`<div class="meta">"${esc(DATA.term)}": ${rows.length} productos en ${chains.length} cadenas · hora ${DATA.at.slice(11,16)} UTC · el precio por ${basis.replace('$/','')} sirve para comparar tamaños distintos</div><div class="cards">`;
  chains.sort((a,b)=>(stat[a].min??1e12)-(stat[b].min??1e12)).forEach(c=>{const s=stat[c];
    h+=`<div class="card ${chainSel===c?'on':''} ${s.min===bestMin?'best':''}" data-c="${esc(c)}"><b>${esc(c)}</b><span class="v">${money(s.min)}</span><span class="s">mínimo ${basis} · mediana ${money(s.med)}<br>${s.n} productos</span></div>`});
  h+=`</div><div class="tools"><input type="text" id="t" placeholder="Filtrar (marca, tamaño…)" value="${esc(text)}"><label>Ordenar <select id="s"><option value="unit">Precio por ${basis.replace('$/','')}</option><option value="price">Precio del producto</option><option value="chain">Cadena</option></select></label><span class="meta" style="margin:0">${list.length} mostrados</span></div>`;
  if(!list.length)h+='<div class="empty">Sin resultados con ese filtro.</div>';
  else h+='<table><thead><tr><th>Cadena</th><th>Producto</th><th class="n">Precio</th><th class="n">'+basis+'</th><th>Promo</th><th>Canasta</th></tr></thead><tbody>'+list.slice(0,400).map((r,i)=>`<tr><td>${esc(r.chain_label)}</td><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></td><td class="n">${money(r.price)}${r.list_price&&r.list_price>r.price?'<br><s style="color:var(--mute);font-size:12px">'+money(r.list_price)+'</s>':''}</td><td class="n">${money(r.unit_price)}</td><td>${r.promo?'<span class="tag p">'+esc(r.promo.slice(0,40))+'</span>':''}</td><td>${inBasket(r.title)?'<button class="addbtn done" disabled>✓ en canasta</button>':'<button class="addbtn" data-i="'+i+'" title="Agregar a mi canasta">+ canasta</button>'}</td></tr>`).join('')+'</tbody></table>'+(list.length>400?'<div class="meta">Mostrando los primeros 400; usá el filtro.</div>':'');
  shown=list.slice(0,400);
  $('#out').innerHTML=h;$('#s').value=sortKey;
  document.querySelectorAll('.addbtn[data-i]').forEach(b=>b.onclick=()=>addToBasket(+b.dataset.i,b));
  document.querySelectorAll('.card').forEach(el=>el.onclick=()=>{chainSel=chainSel===el.dataset.c?null:el.dataset.c;render()});
  $('#s').onchange=e=>{sortKey=e.target.value;render()};
  $('#t').oninput=e=>{text=e.target.value.toLowerCase();const p=e.target.selectionStart;render();const t=$('#t');t.focus();t.setSelectionRange(p,p)};
}
// ---- Mi canasta ----
let BASKET=[], shown=[];
const normT=s=>(s||'').toLowerCase().replace(/\s+/g,' ').trim();
const inBasket=t=>BASKET.some(i=>normT(i.title)===normT(t));
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json()}
async function loadBasket(){BASKET=(await api('/api/canasta')).items;$('#tabC').textContent='Mi canasta ('+BASKET.length+')';renderBasket()}
async function addToBasket(i,btn){const r=shown[i];if(!r)return;btn.disabled=true;btn.textContent='Agregando…';
  try{const res=await api('/api/canasta/agregar',{title:r.title,brand:r.brand});await loadBasket();
    btn.className='addbtn done';btn.textContent='✓ en canasta';
    if(!res.size)alert_msg('Ese producto no trae el tamaño en el nombre: se compara por nombre y marca.')}
  catch(e){btn.disabled=false;btn.textContent='+ canasta'}}
function alert_msg(t){const d=document.createElement('div');d.className='err';d.textContent=t;$('#out').prepend(d);setTimeout(()=>d.remove(),6000)}
function renderBasket(){
  const box=$('#basketBox');
  if(!BASKET.length){box.innerHTML='<div class="empty">Tu canasta está vacía.<br>Buscá un producto en la pestaña <b>Buscar</b> y apretá <b>+ canasta</b> en el que comprás.</div>';$('#basketOut').innerHTML='';return}
  box.innerHTML='<div class="blist">'+BASKET.map((it,k)=>`<div class="bitem"><span>${esc(it.name)}</span><button data-k="${k}" title="Quitar">✕</button></div>`).join('')+'</div>'+
    '<div class="bactions"><button id="calc">Calcular costo en cada cadena</button><button class="sec" id="clear">Empezar de cero</button></div>';
  box.querySelectorAll('button[data-k]').forEach(b=>b.onclick=async()=>{await api('/api/canasta/quitar',{name:BASKET[+b.dataset.k].name});await loadBasket();$('#basketOut').innerHTML=''});
  $('#clear').onclick=async()=>{if(!confirm('¿Borrar todos los productos de tu canasta?'))return;await api('/api/canasta/vaciar',{});await loadBasket()};
  $('#calc').onclick=calcBasket;
}
async function calcBasket(){
  const out=$('#basketOut'),btn=$('#calc');btn.disabled=true;btn.textContent='Calculando…';
  out.innerHTML='<div class="empty">Buscando cada producto en las 8 cadenas. Con '+BASKET.length+' productos tarda entre 1 y 3 minutos.</div>';
  try{const d=await api('/api/canasta/calcular');
    if(d.error)out.innerHTML='<div class="err">No se pudo calcular: '+esc(d.error)+'</div>';
    else if(d.empty)out.innerHTML='<div class="empty">Tu canasta está vacía.</div>';
    else{out.innerHTML='<iframe id="dash" title="Costo de mi canasta"></iframe>';const f=$('#dash');f.srcdoc=d.html;
      f.onload=()=>{try{f.style.height=(f.contentDocument.documentElement.scrollHeight+20)+'px'}catch(e){}}}}
  catch(e){out.innerHTML='<div class="err">No se pudo calcular: '+e+'</div>'}
  btn.disabled=false;btn.textContent='Calcular costo en cada cadena';
}
function showView(v){$('#viewB').hidden=v!=='B';$('#viewC').hidden=v!=='C';$('#tabB').classList.toggle('on',v==='B');$('#tabC').classList.toggle('on',v==='C')}
$('#tabB').onclick=()=>showView('B');$('#tabC').onclick=()=>showView('C');
loadBasket();
// Si el link trae ?q=producto, busca solo al abrir; si no, queda esperando que escribas
const initial=new URLSearchParams(location.search).get('q');
if(initial){$('#q').value=initial;$('#f').requestSubmit();}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, rel):
        """Sirve archivos de web/ (nunca fuera de esa carpeta)."""
        root = WEB_DIR.resolve()
        target = (root / rel).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not (target.is_file() and (root in target.parents)):
            self._send(404, "No encontrado", "text/plain")
            return
        ctype = {".html": "text/html", ".js": "application/javascript", ".json": "application/json",
                 ".css": "text/css", ".svg": "image/svg+xml"}.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        gzipped = False
        if len(data) > 4096 and "gzip" in (self.headers.get("Accept-Encoding") or "") and target.suffix in (".json", ".js", ".html"):
            key = (str(target), target.stat().st_mtime)
            if key not in _gzip_cache:
                import gzip
                _gzip_cache.clear()
                _gzip_cache[key] = gzip.compress(data, 6)
            data, gzipped = _gzip_cache[key], True
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        if gzipped:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.send_response(302)                       # la interfaz nueva es la página principal
            self.send_header("Location", "/ui/" + ("?" + url.query if url.query else ""))
            self.end_headers()
        elif url.path == "/clasico":
            self._send(200, PAGE, "text/html")
        elif url.path == "/ui" or url.path.startswith("/ui/"):
            self._static(url.path[4:].lstrip("/"))
        elif url.path == "/api/catalogo":
            self._static("data/index.json")
        elif url.path == "/api/productos":
            ids = [i for i in (parse_qs(url.query).get("ids") or [""])[0].split(",") if i][:60]
            self._json({"items": product_details(ids)})
        elif url.path == "/api/buscar":
            term = (parse_qs(url.query).get("q") or [""])[0].strip()[:80]
            if not term:
                self._send(400, json.dumps({"error": "falta q"}), "application/json")
                return
            try:
                self._send(200, json.dumps(buscar_cached(term), ensure_ascii=False), "application/json")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}), "application/json")
        elif url.path == "/api/canasta":
            items = canasta.load_config()["items"]
            self._json({"items": [{"name": i["name"], "title": i.get("title") or i["name"]} for i in items]})
        elif url.path == "/api/canasta/calcular":
            try:
                self._json(canasta_calculada())
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self._send(404, "No encontrado", "text/plain")

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json")

    def do_POST(self):
        url = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:        # clientes de consola de Windows mandan cp1252
                text = raw.decode("cp1252", errors="replace")
            body = json.loads(text)
        except ValueError:
            self._json({"error": "JSON inválido"}, 400)
            return
        if url.path == "/api/canasta/agregar":
            title = str(body.get("title") or "").strip()[:200]
            if not title:
                self._json({"error": "falta title"}, 400)
                return
            item, added = canasta.add_item(title, body.get("brand"))
            self._json({"added": added, "name": item["name"], "size": item.get("size"),
                        "brand": item.get("brand")})
        elif url.path == "/api/canasta/quitar":
            self._json({"removed": canasta.remove_item(str(body.get("name") or ""))})
        elif url.path == "/api/canasta/vaciar":
            canasta.clear_items()
            self._json({"ok": True})
        else:
            self._send(404, "No encontrado", "text/plain")


class _Server(ThreadingHTTPServer):
    # En Windows, allow_reuse_address=True (el valor por defecto de HTTPServer) deja que DOS servidores usen el
    # mismo puerto. Se desactiva para que un segundo arranque falle y solo abra el navegador.
    allow_reuse_address = False


def main():
    url = f"http://127.0.0.1:{PORT}"
    try:
        server = _Server(("127.0.0.1", PORT), Handler)
    except OSError:                                  # el puerto está ocupado: el panel ya estaba abierto
        print(f"El panel ya estaba abierto en {url}; solo se abre el navegador.")
        if "--no-open" not in sys.argv:
            webbrowser.open(url)
        return
    print(f"Panel en {url}  (Ctrl+C para cerrar)")
    if "--no-open" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
