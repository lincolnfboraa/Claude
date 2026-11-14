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

def traduzir(b):
    """Aviso do Supabase -> pedido do editor (o que antes o n8n fazia)."""
    r, o = b.get('record') or {}, b.get('old_record') or {}
    if b.get('table') == 'versoes' and b.get('type') == 'INSERT' and r.get('status') == 'editando':
        return {'tipo': 'ajuste' if r.get('numero', 1) > 1 else 'nova_edicao', 'projeto_id': r['projeto_id'], 'versao_id': r['id'], 'versao': r.get('numero')}
    if b.get('table') == 'projetos' and b.get('type') == 'UPDATE' and r.get('status') == 'aprovado' and o.get('status') != 'aprovado':
        return {'tipo': 'final', 'projeto_id': r['id'], 'cliente': r.get('cliente_id')}
    return None

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
        finally:
            FILA.task_done(); EM_FILA.discard(('final:' if p['tipo'] == 'final' else '') + str(p.get('versao_id')))

class H(BaseHTTPRequestHandler):
    def _r(self, cod, obj):
        self.send_response(cod); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(obj).encode())
    def do_GET(self):
        self._r(200, {'ok': True, 'na_fila': FILA.qsize()})
    def do_POST(self):
        if self.headers.get('X-Bora-Token') != TOKEN: return self._r(401, {'erro': 'token'})
        p = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if 'table' in p:                                   # aviso direto do Supabase (Database Webhook)
            p = traduzir(p)
            if not p: return self._r(200, {'ok': True, 'ignorado': True})
        if not p.get('projeto_id') or p.get('tipo') not in ('nova_edicao', 'ajuste', 'final'): return self._r(400, {'erro': 'pedido incompleto'})
        enfileirar(p); self._r(202, {'ok': True, 'posicao': FILA.qsize()})

EM_FILA = set()
def enfileirar(p):
    chave = ('final:' if p['tipo'] == 'final' else '') + str(p.get('versao_id'))
    if chave in EM_FILA: return False
    EM_FILA.add(chave)
    etapa(p['projeto_id'], 'Na fila do editor', 2, andamento_versao=chave)
    FILA.put(p); return True

def vigia():
    """Consulta o Supabase a cada 10 s (o VPS só faz chamadas de saída; não depende de porta aberta)."""
    import time
    while True:
        try:
            for v in sb('GET', '/rest/v1/versoes?status=eq.editando&select=id,numero,projeto_id,projetos(original_meta)'):
                m = (v.get('projetos') or {}).get('original_meta') or {}
                if m.get('andamento_versao') != v['id']:
                    enfileirar({'tipo': 'ajuste' if v['numero'] > 1 else 'nova_edicao', 'projeto_id': v['projeto_id'], 'versao_id': v['id'], 'versao': v['numero']})
            for pr in sb('GET', '/rest/v1/projetos?status=eq.aprovado&select=id,cliente_id,original_meta,versoes(id,numero,final_drive_id)'):
                m = pr.get('original_meta') or {}; vs = sorted(pr['versoes'], key=lambda x: x['numero'])
                if vs and not vs[-1]['final_drive_id'] and not m.get('final_pronto') and m.get('andamento_versao') != 'final:' + vs[-1]['id']:
                    enfileirar({'tipo': 'final', 'projeto_id': pr['id'], 'cliente': pr['cliente_id'], 'versao_id': vs[-1]['id'], 'versao': vs[-1]['numero']})
        except Exception as e:
            print('vigia:', e, flush=True)
        time.sleep(10)

threading.Thread(target=vigia, daemon=True).start()
threading.Thread(target=trabalhador, daemon=True).start()
print('Editor Bora Studio ouvindo na porta 8787')
ThreadingHTTPServer(('0.0.0.0', 8787), H).serve_forever()
