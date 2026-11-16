#!/usr/bin/env python3
"""Editor do Bora Studio no VPS. Recebe pedidos do n8n (POST /pedido), processa um por vez e devolve tudo pro Supabase:
porcentagem e etapa em projetos.original_meta, prévia/final no Storage, status em versoes/projetos.
Variáveis: SUPABASE_URL, SUPABASE_SECRET, ANTHROPIC_API_KEY, BORA_TOKEN."""
import hashlib, hmac, json, os, queue, time, subprocess, threading, traceback, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

URL, KEY, TOKEN = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SECRET'], os.environ['BORA_TOKEN']
TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')
ORIGEM = os.environ.get('BORA_ORIGEM', 'https://studio.borasolucoesdigitais.com')
FILA = queue.Queue()

def sb(metodo, path, corpo=None):
    r = urllib.request.Request(URL + path, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                               headers={'apikey': KEY, 'Content-Type': 'application/json', 'Prefer': 'return=representation'})
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

OCUPADO = [0]
def trabalhador():
    while True:
        p = FILA.get(); OCUPADO[0] += 1
        try: processar(p)
        finally:
            OCUPADO[0] -= 1; FILA.task_done(); EM_FILA.discard(('final:' if p['tipo'] == 'final' else '') + str(p.get('versao_id')))

def subir(bucket, caminho, arquivo, tipo):
    r = urllib.request.Request(f'{URL}/storage/v1/object/{bucket}/{caminho}', data=open(arquivo, 'rb').read(), method='POST',
                               headers={'apikey': KEY, 'Content-Type': tipo, 'x-upsert': 'true'})
    return json.load(urllib.request.urlopen(r, timeout=300))

def capa_do_projeto(pid, cliente, video):
    """Gera a miniatura do card (quadro real do vídeo) e grava em projetos.original_meta.capa."""
    try:
        import capas
        jpg = os.path.join(pasta(pid), 'capa.jpg'); capas.gerar_capa(video, jpg)
        caminho = f'{cliente}/{pid}/capa.jpg'; subir('previas', caminho, jpg, 'image/jpeg')
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m['capa'] = caminho; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
    except Exception as e:
        print('capa:', e, flush=True)

def usuario_da_equipe(auth):
    """Confere o login do app (token do Supabase) e se a pessoa está na tabela equipe."""
    if not auth or not auth.startswith('Bearer '): return None
    try:
        r = urllib.request.Request(URL + '/auth/v1/user', headers={'apikey': KEY, 'Authorization': auth})
        uid = json.load(urllib.request.urlopen(r, timeout=20))['id']
        return uid if sb('GET', f'/rest/v1/equipe?user_id=eq.{uid}&select=user_id') else None
    except Exception:
        return None

def pasta(pid):
    d = os.path.join(TRAB, os.path.basename(pid)); os.makedirs(d, exist_ok=True); return d

def inspecionar(arq):
    """ffprobe do original: resolução, fps, cor; diz se é HDR."""
    o = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,r_frame_rate,color_transfer,color_primaries,pix_fmt:stream_side_data:format=duration',
        '-of', 'json', arq], capture_output=True, text=True).stdout or '{}')
    st = (o.get('streams') or [{}])[0]; w, h = st.get('width', 0), st.get('height', 0)
    rot = abs(int(float(next((x.get('rotation') for x in st.get('side_data_list') or [] if 'rotation' in x), 0) or 0)))
    if rot in (90, 270): w, h = h, w
    n, d_ = (st.get('r_frame_rate') or '0/1').split('/'); fps = round(int(n) / max(int(d_), 1), 2)
    tr = st.get('color_transfer') or ''
    hdr = tr in ('arib-std-b67', 'smpte2084')
    cor = {'arib-std-b67': 'HDR HLG', 'smpte2084': 'HDR PQ'}.get(tr, 'SDR') + (' · BT.2020' if st.get('color_primaries') == 'bt2020' else '') + (' · 10 bits' if '10' in (st.get('pix_fmt') or '') else '')
    dur = float((o.get('format') or {}).get('duration', 0) or 0)
    return {'res': f'{w} × {h}', 'fps': f'{fps:g} fps'.replace('.', ','), 'cor': cor, 'hdr': hdr, 'dur': f'{round(dur)} s'}

class H(BaseHTTPRequestHandler):
    def _r(self, cod, obj):
        self.send_response(cod); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(obj).encode())
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', ORIGEM)
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Bora-Token')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith('/final/'): return self._final(u)
        if u.path.startswith('/upload/'):                  # quanto do arquivo já chegou (pra retomar)
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            partes = u.path.split('/'); pid = partes[2]; n = int(partes[3]) if len(partes) > 3 and partes[3].isdigit() else 1
            arq = os.path.join(pasta(pid), f"{'anexo' if urllib.parse.parse_qs(u.query).get('tipo') == ['anexo'] else 'original'}_{n:02d}.parcial")
            return self._r(200, {'recebido': os.path.getsize(arq) if os.path.exists(arq) else 0})
        self._r(200, {'ok': True, 'na_fila': FILA.qsize(), 'ocupado': OCUPADO[0]})
    def _final(self, u):
        """GET /final/<projeto>?exp=..&sig=.. : baixa o .zip do final (link assinado, vale 2 h)."""
        q = urllib.parse.parse_qs(u.query); pid = os.path.basename(u.path.split('/')[2])
        exp = q.get('exp', ['0'])[0]; sig = q.get('sig', [''])[0]
        certo = hmac.new(TOKEN.encode(), f'{pid}:{exp}'.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, certo) or int(exp) < time.time(): return self._r(403, {'erro': 'link vencido'})
        m = (sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta') or [{}])[0].get('original_meta') or {}
        arq = m.get('final_zip')
        if not arq or not os.path.exists(arq): return self._r(404, {'erro': 'final ainda não está pronto'})
        self.send_response(200); self.send_header('Content-Type', 'application/zip')
        self.send_header('Content-Length', str(os.path.getsize(arq)))
        self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(arq)}"'); self.end_headers()
        with open(arq, 'rb') as f:
            while True:
                b = f.read(1 << 20)
                if not b: break
                self.wfile.write(b)
    def do_PUT(self):
        """Envio do original em partes: PUT /upload/<projeto>?offset=N (corpo = pedaço do arquivo)."""
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if not u.path.startswith('/upload/'): return self._r(404, {'erro': 'rota'})
        if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
        partes = u.path.split('/'); pid = partes[2]; n = int(partes[3]) if len(partes) > 3 and partes[3].isdigit() else 1
        arq = os.path.join(pasta(pid), f"{'anexo' if urllib.parse.parse_qs(u.query).get('tipo') == ['anexo'] else 'original'}_{n:02d}.parcial")
        atual = os.path.getsize(arq) if os.path.exists(arq) else 0
        if int(q.get('offset', ['0'])[0]) != atual: return self._r(409, {'recebido': atual})
        n = int(self.headers.get('Content-Length', 0))
        with open(arq, 'ab') as f:
            while n > 0:
                b = self.rfile.read(min(n, 1 << 20))
                if not b: break
                f.write(b); n -= len(b)
        self._r(200, {'recebido': os.path.getsize(arq)})
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith('/final/') and u.path.endswith('/link'):
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            pid = os.path.basename(u.path.split('/')[2]); exp = str(int(time.time()) + 7200)
            sig = hmac.new(TOKEN.encode(), f'{pid}:{exp}'.encode(), hashlib.sha256).hexdigest()
            return self._r(200, {'url': f'https://{self.headers.get("Host", "editor.borasolucoesdigitais.com")}/final/{pid}?exp={exp}&sig={sig}'})
        if u.path.startswith('/anexo/') and u.path.endswith('/fim'):
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            pid = os.path.basename(u.path.split('/')[2]); d = pasta(pid)
            corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
            lista = m.get('anexos') or []
            for i, a in enumerate(corpo.get('arquivos') or [], 1):
                parcial = os.path.join(d, f'anexo_{i:02d}.parcial')
                if not os.path.exists(parcial) or os.path.getsize(parcial) != int(a.get('tamanho', -1)):
                    return self._r(409, {'erro': f'anexo {i} incompleto'})
                ext = os.path.splitext(a.get('nome', 'x.png'))[1].lower() or '.png'
                final = os.path.join(d, f'anexo_{len(lista) + 1:02d}{ext}'); os.replace(parcial, final)
                tipo = 'video' if ext in ('.mp4', '.mov', '.m4v', '.webm') else 'imagem'
                if tipo == 'imagem' and ext in ('.heic', '.heif'):
                    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', final, final + '.png']); final += '.png'
                lista.append({'nome': a.get('nome'), 'caminho': final, 'tipo': tipo, 'versao': corpo.get('versao')})
            m['anexos'] = lista; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
            return self._r(200, {'ok': True, 'anexos': len(lista)})
        if u.path.startswith('/upload/') and u.path.endswith('/fim'):
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            pid = u.path.split('/')[2]; d = pasta(pid); corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            lista = corpo.get('arquivos') or [{'nome': corpo.get('nome', 'video.mov'), 'tamanho': corpo.get('tamanho', -1)}]
            arquivos = []
            for i, a in enumerate(lista, 1):
                parcial = os.path.join(d, f'original_{i:02d}.parcial')
                if not os.path.exists(parcial) or os.path.getsize(parcial) != int(a.get('tamanho', -1)):
                    return self._r(409, {'erro': f'arquivo {i} incompleto'})
                ext = os.path.splitext(a.get('nome', 'video.mov'))[1].lower() or '.mov'
                final = os.path.join(d, f'original_{i:02d}{ext}'); os.replace(parcial, final)
                arquivos.append({'nome': a.get('nome'), 'caminho': final, **inspecionar(final)})
            info = {k: arquivos[0][k] for k in ('res', 'fps', 'cor')}
            sem_hdr = [x['nome'] for x in arquivos if not x['hdr']]
            aviso = None if not sem_hdr else ('Chegou sem HDR: ' + ', '.join(sem_hdr) + '. No iPhone, escolha Opções > Atual na Fototeca pra mandar o original')
            m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
            m.update({**info, 'arq': arquivos[0]['nome'] if len(arquivos) == 1 else f'{len(arquivos)} vídeos', 'arquivos': arquivos,
                      'dur': f"{round(sum(float(x['dur'].split()[0]) for x in arquivos))} s", 'aguardando_upload': False, 'aviso': aviso})
            sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
            cliente = (sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=cliente_id') or [{}])[0].get('cliente_id', 'sem-cliente')
            capa_do_projeto(pid, cliente, arquivos[0]['caminho'])      # antes da versão entrar na fila (evita corrida no original_meta)
            sb('POST', '/rest/v1/versoes', {'projeto_id': pid, 'numero': 1, 'status': 'editando', 'resumo': 'Primeira versão'})
            return self._r(200, {'ok': True, 'arquivos': len(arquivos), 'aviso': aviso})
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
    """Consulta o Supabase a cada 10 s (o VPS só faz chamadas de saída; não depende de porta aberta).
    Na primeira volta depois de ligar, retoma também o que ficou parado (erro ou reinício do editor)."""
    import time
    retomar = True
    while True:
        try:
            for v in sb('GET', '/rest/v1/versoes?status=eq.editando&select=id,numero,projeto_id,projetos(original_meta)'):
                m = (v.get('projetos') or {}).get('original_meta') or {}
                if retomar or m.get('andamento_versao') != v['id']:
                    enfileirar({'tipo': 'ajuste' if v['numero'] > 1 else 'nova_edicao', 'projeto_id': v['projeto_id'], 'versao_id': v['id'], 'versao': v['numero']})
            for pr in sb('GET', '/rest/v1/projetos?status=eq.aprovado&select=id,cliente_id,original_meta,versoes(id,numero,final_drive_id)'):
                m = pr.get('original_meta') or {}; vs = sorted(pr['versoes'], key=lambda x: x['numero'])
                if vs and not vs[-1]['final_drive_id'] and not m.get('final_pronto') and (retomar or m.get('andamento_versao') != 'final:' + vs[-1]['id']):
                    enfileirar({'tipo': 'final', 'projeto_id': pr['id'], 'cliente': pr['cliente_id'], 'versao_id': vs[-1]['id'], 'versao': vs[-1]['numero']})
            retomar = False
        except Exception as e:
            print('vigia:', e, flush=True)
        time.sleep(10)

threading.Thread(target=vigia, daemon=True).start()
for _ in range(int(os.environ.get("BORA_PARALELO", "2"))):   # até 2 vídeos ao mesmo tempo
    threading.Thread(target=trabalhador, daemon=True).start()
print('Editor Bora Studio ouvindo na porta 8787')
ThreadingHTTPServer(('0.0.0.0', 8787), H).serve_forever()
