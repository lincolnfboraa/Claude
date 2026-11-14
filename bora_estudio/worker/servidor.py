#!/usr/bin/env python3
"""Editor do Bora Studio no VPS. Recebe pedidos do n8n (POST /pedido), processa um por vez e devolve tudo pro Supabase:
porcentagem e etapa em projetos.original_meta, prévia/final no Storage, status em versoes/projetos.
Variáveis: SUPABASE_URL, SUPABASE_SECRET, ANTHROPIC_API_KEY, BORA_TOKEN."""
import json, os, queue, threading, traceback, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

URL, KEY, TOKEN = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SECRET'], os.environ['BORA_TOKEN']
FILA = queue.Queue()

def sb(metodo, path, corpo=None):
    r = urllib.request.Request(URL + path, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                               headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json', 'Prefer': 'return=representation'})
    return json.load(urllib.request.urlopen(r, timeout=60))

def etapa(projeto_id, texto, pct, **extra):
    m = sb('GET', f'/rest/v1/projetos?id=eq.{projeto_id}&select=original_meta')[0]['original_meta'] or {}
    m.update({'andamento': texto, 'progresso': pct, **extra})
    sb('PATCH', f'/rest/v1/projetos?id=eq.{projeto_id}', {'original_meta': m})

def processar(p):
    pid = p['projeto_id']
    try:
        import motor                                   # motor de edição (bora_estudio/worker/motor.py)
        motor.executar(p, etapa=lambda t, n, **k: etapa(pid, t, n, **k), sb=sb)
    except Exception as e:
        traceback.print_exc()
        etapa(pid, 'Erro na edição: ' + str(e)[:120], None)

def trabalhador():
    while True:
        p = FILA.get()
        try: processar(p)
        finally: FILA.task_done()

class H(BaseHTTPRequestHandler):
    def _r(self, cod, obj):
        self.send_response(cod); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(obj).encode())
    def do_GET(self):
        self._r(200, {'ok': True, 'na_fila': FILA.qsize()})
    def do_POST(self):
        if self.headers.get('X-Bora-Token') != TOKEN: return self._r(401, {'erro': 'token'})
        p = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if not p.get('projeto_id') or p.get('tipo') not in ('nova_edicao', 'ajuste', 'final'): return self._r(400, {'erro': 'pedido incompleto'})
        etapa(p['projeto_id'], 'Na fila do editor', 2, andamento_versao=p.get('versao_id'))
        FILA.put(p); self._r(202, {'ok': True, 'posicao': FILA.qsize()})

threading.Thread(target=trabalhador, daemon=True).start()
print('Editor Bora Studio ouvindo na porta 8787')
ThreadingHTTPServer(('0.0.0.0', 8787), H).serve_forever()
