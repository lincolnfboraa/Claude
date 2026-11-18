#!/usr/bin/env python3
"""Editor do Bora Studio no VPS. Recebe pedidos do n8n (POST /pedido), processa um por vez e devolve tudo pro Supabase:
porcentagem e etapa em projetos.original_meta, prévia/final no Storage, status em versoes/projetos.
Variáveis: SUPABASE_URL, SUPABASE_SECRET, ANTHROPIC_API_KEY, BORA_TOKEN."""
import hashlib, hmac, json, os, queue, time, subprocess, threading, traceback, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

URL, KEY, TOKEN = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SECRET'], os.environ['BORA_TOKEN']
TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')
ORIGEM = os.environ.get('BORA_ORIGEM', 'https://studio.borasolucoesdigitais.com')
FILA = queue.Queue()

def sb(metodo, path, corpo=None):
    r = urllib.request.Request(URL + path, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                               headers={'apikey': KEY, 'Content-Type': 'application/json', 'Prefer': 'return=representation'})
    return json.load(urllib.request.urlopen(r, timeout=60))

ULTIMA = [0.0]                                         # hora do último avanço de etapa (detecta vídeo travado)
def etapa(projeto_id, texto, pct, **extra):
    import time; ULTIMA[0] = time.time()
    m = sb('GET', f'/rest/v1/projetos?id=eq.{projeto_id}&select=original_meta')[0]['original_meta'] or {}
    m.update({'andamento': texto, 'progresso': pct, 'detalhe': None, 'previsao_s': None, **extra})
    sb('PATCH', f'/rest/v1/projetos?id=eq.{projeto_id}', {'original_meta': m})

def traduzir(b):
    """Aviso do Supabase -> pedido do editor (o que antes o n8n fazia)."""
    r, o = b.get('record') or {}, b.get('old_record') or {}
    if b.get('table') == 'versoes' and b.get('type') == 'INSERT' and r.get('status') == 'editando':
        return {'tipo': 'ajuste' if r.get('numero', 1) > 1 else 'nova_edicao', 'projeto_id': r['projeto_id'], 'versao_id': r['id'], 'versao': r.get('numero')}
    if b.get('table') == 'projetos' and b.get('type') == 'UPDATE' and r.get('status') == 'aprovado' and o.get('status') != 'aprovado':
        return {'tipo': 'final', 'projeto_id': r['id'], 'cliente': r.get('cliente_id')}
    return None

def avisar(p, ok, erro=''):
    try:
        import avisos
        pr = (sb('GET', f"/rest/v1/projetos?id=eq.{p['projeto_id']}&select=titulo,cliente_id") or [{}])[0]
        nome = (sb('GET', f"/rest/v1/clientes?id=eq.{pr.get('cliente_id')}&select=nome") or [{}])[0].get('nome', '')
        if not ok: t = ('Erro na edição', f"{pr.get('titulo')} · {nome}: {erro}")
        elif p['tipo'] == 'final': t = ('4K pronto pra baixar', f"{pr.get('titulo')} · {nome}")
        else: t = (f"Prévia pronta: {pr.get('titulo')}", f"{nome} · v{p.get('versao') or ''} pra revisar")
        avisos.enviar(t[0], t[1], '/#v=' + p['projeto_id'])
    except Exception as e:
        print('aviso:', e, flush=True)

def processar(p):
    pid = p['projeto_id']
    try:
        import motor                                   # motor de edição (bora_estudio/worker/motor.py)
        et = lambda t, n, **k: etapa(pid, t, n, **k)
        if EXTERNO:
            espera = 30 - (time.time() - INICIO)       # logo depois de ligar, dá tempo do computador de render dar sinal
            if espera > 0: time.sleep(espera)
        if EXTERNO and acer_ligado():                  # computador de render ligado: transcrição, prévia e 4K vão pra ele
            if p['tipo'] == 'final':
                fila_enfileirar(motor.preparar(p, et, sb))
                return                                 # a entrega acontece quando o worker devolver (cuidar_da_fila)
            if previa_externa(p, et):
                avisar(p, True); return
        motor.executar(p, etapa=et, sb=sb)             # computador de render desligado: tudo no VPS (como sempre)
        avisar(p, True)
    except Exception as e:
        traceback.print_exc()
        sem_mem = type(e).__name__ == 'SemMemoria'          # não repete sozinho (nem ao reiniciar); só pelo botão Tentar de novo
        etapa(pid, ('Erro: ' if sem_mem else 'Erro na edição: ') + str(e)[:120], None,
              **({'falha_memoria': ('final:' if p['tipo'] == 'final' else '') + str(p.get('versao_id'))} if sem_mem else {}))
        avisar(p, False, str(e)[:80])

OCUPADO = [0]
FINAIS = [0]                                           # 4K em andamento (etapas longas, sem avanço por até ~1 h)
def trabalhador():
    while True:
        p = FILA.get(); OCUPADO[0] += 1; FINAIS[0] += p['tipo'] == 'final'
        try: processar(p)
        finally:
            OCUPADO[0] -= 1; FINAIS[0] -= p['tipo'] == 'final'; FILA.task_done(); EM_FILA.discard(('final:' if p['tipo'] == 'final' else '') + str(p.get('versao_id')))

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


# ---------------- Render externo do 4K (opcional: BORA_RENDER_EXTERNO=1 e BORA_WORKER_TOKEN no bora.env) ----------------
# Só o final 4K aprovado vai pro worker (ex.: o Acer). Análise, plano e prévia 480p continuam aqui.
# O VPS continua dono do banco: grava o trabalho em render_trabalhos (Supabase), entrega os arquivos ao worker por HTTPS
# com token próprio, recebe o resultado e conclui. SEM fallback: se o worker estiver desligado ou falhar, o trabalho fica
# na fila (até BORA_MAX_TENTATIVAS tentativas; depois vira erro com o botão Tentar de novo no app).
EXTERNO = os.environ.get('BORA_RENDER_EXTERNO', '0') == '1' and bool(os.environ.get('BORA_WORKER_TOKEN'))
WTOKEN = os.environ.get('BORA_WORKER_TOKEN', '')
SILENCIO = int(os.environ.get('BORA_WORKER_SILENCIO', '900'))
MAX_TENT = int(os.environ.get('BORA_MAX_TENTATIVAS', '3'))
JOBS = {}                                              # cache em memória: id -> trabalho (o Supabase é a fonte)

def agora(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def fila_get(jid):
    j = (sb('GET', f'/rest/v1/render_trabalhos?id=eq.{jid}&select=*') or [None])[0]
    if j: JOBS[jid] = j
    return j

def fila_patch(jid, corpo, cond=''):
    r = sb('PATCH', f'/rest/v1/render_trabalhos?id=eq.{jid}{cond}', corpo)
    if r: JOBS[jid] = r[0]
    return r

def _iso_seg(iso):
    import calendar
    return calendar.timegm(time.strptime(iso[:19], '%Y-%m-%dT%H:%M:%S')) if iso else 0

INICIO = time.time()
VISTO = {}                                             # nome do worker -> última vez que pediu trabalho ou deu sinal
OFFLINE_MIN = int(os.environ.get('BORA_OFFLINE_MIN', '10'))     # 4K pendente sem computador ligado por N min: o VPS assume

def acer_ligado():
    return any(time.time() - t < 45 for t in VISTO.values())

def _esperar_externo(pac):
    """Manda um trabalho de prévia (transcrição ou render) pro computador de render e espera.
    Devolve o resultado, ou None se ele desligar, sumir ou falhar (aí o VPS faz)."""
    try:
        job = sb('POST', '/rest/v1/render_trabalhos', {'projeto_id': pac['projeto_id'], 'versao_id': pac['versao_id'], 'tipo': 'previa',
                                                       'altura': pac['altura'], 'pacote': pac})[0]
    except urllib.error.HTTPError as e:
        if e.code != 409: raise
        job = sb('GET', f"/rest/v1/render_trabalhos?versao_id=eq.{pac['versao_id']}&tipo=eq.previa&status=in.(pendente,renderizando)&select=*")[0]
        if job['status'] == 'pendente': fila_patch(job['id'], {'pacote': pac})
    jid, desde = job['id'], time.time()
    while True:
        time.sleep(4)
        j = fila_get(jid) or {}; st = j.get('status')
        if st == 'concluido':
            fila_patch(jid, {'status': 'entregue'}); return j['resultado']
        if st in ('falhou', 'cancelado'):
            print('prévia externa:', st, j.get('erro'), '| o VPS faz', flush=True); return None
        if st == 'pendente' and not acer_ligado() and time.time() - desde > 60:
            if fila_patch(jid, {'status': 'cancelado', 'erro': 'computador de render desligado'}, '&status=eq.pendente'): return None
        if st == 'renderizando' and time.time() - _iso_seg(j.get('batida')) > 150:
            if fila_patch(jid, {'status': 'cancelado', 'erro': 'computador de render sem sinal'}, '&status=eq.renderizando'): return None

def previa_externa(p, et):
    """Transcrição e prévia no computador de render; a IA (plano) continua no VPS. Se ele sumir no meio, o VPS termina."""
    import motor
    pac_t = motor.pacote_transcricao(p, sb)
    if pac_t:
        et('Transcrevendo no computador de render', 6)
        res = _esperar_externo(pac_t)
        if res is None: return False                   # o VPS transcreve e faz tudo
    pac = motor.preparar(p, et, sb)                    # transcrições já prontas: só a IA monta o plano
    et('Montando a prévia no computador de render', 40)
    res = _esperar_externo(pac)
    if res is None:
        et('Computador de render saiu: o VPS termina a prévia', 40)
        res = motor.renderizar(pac, et)
    motor.concluir(pac, res, sb)
    return True

def fila_enfileirar(pac):
    """Grava o trabalho de render (o índice único impede duplicado da mesma versão) e volta na hora."""
    try:
        sb('POST', '/rest/v1/render_trabalhos', {'projeto_id': pac['projeto_id'], 'versao_id': pac['versao_id'], 'tipo': pac['tipo'],
                                                 'altura': pac['altura'], 'pacote': pac})
    except urllib.error.HTTPError as e:                # já existe um ativo (ex.: o VPS reiniciou): segue com ele, sem mexer no andamento
        if e.code != 409: raise
        return
    etapa(pac['projeto_id'], 'Na fila do render 4K (aguardando o computador de render)', None)

def _falhou(job, erro):
    """Falha do worker: a prévia volta pro VPS na hora; o 4K volta pra fila e, depois de MAX_TENT tentativas, vira erro."""
    if job['tipo'] == 'previa':
        fila_patch(job['id'], {'status': 'falhou', 'erro': erro[:300]}); return
    if job['tentativas'] < MAX_TENT:
        fila_patch(job['id'], {'status': 'pendente', 'worker': None, 'erro': erro[:300]}, '&status=eq.renderizando')
        etapa(job['projeto_id'], f"Render 4K vai tentar de novo ({job['tentativas']} de {MAX_TENT}): {erro[:80]}", None)
    else:
        fila_patch(job['id'], {'status': 'falhou', 'erro': erro[:300], 'concluido_em': agora()}, '&status=eq.renderizando')
        sem_mem = erro.startswith('memória')
        etapa(job['projeto_id'], ('Erro: ' if sem_mem else 'Erro no render 4K: ') + erro[:120], None,
              **({'falha_memoria': 'final:' + job['versao_id']} if sem_mem else {}))
        avisar({'tipo': job['tipo'], 'projeto_id': job['projeto_id']}, False, erro[:80])

def cuidar_da_fila():
    """Chamado pela vigia: entrega o que o worker terminou e devolve pra fila trabalho de worker que sumiu."""
    for j in sb('GET', '/rest/v1/render_trabalhos?status=eq.concluido&tipo=eq.final&select=*'):
        if not fila_patch(j['id'], {'status': 'entregue'}, '&status=eq.concluido'): continue
        try:
            import motor
            motor.concluir(j['pacote'], j['resultado'], sb)
            avisar({'tipo': j['tipo'], 'projeto_id': j['projeto_id'], 'versao': j['pacote'].get('n')}, True)
        except Exception as e:
            traceback.print_exc(); fila_patch(j['id'], {'status': 'concluido'})     # tenta entregar de novo na próxima volta
    for j in sb('GET', '/rest/v1/render_trabalhos?status=eq.renderizando&tipo=eq.final&select=*'):
        if time.time() - _iso_seg(j.get('batida')) > SILENCIO:
            _falhou(j, f"o computador {j.get('worker')} ficou sem sinal por {SILENCIO // 60} min")
    if not acer_ligado() and time.time() - INICIO > 120:           # computador de render desligado: o VPS assume o 4K
        for j in sb('GET', '/rest/v1/render_trabalhos?status=eq.pendente&tipo=eq.final&select=*'):
            ref = max(_iso_seg(j['criado_em']), max(VISTO.values(), default=0))
            if time.time() - ref > OFFLINE_MIN * 60 and fila_patch(j['id'], {'status': 'cancelado', 'erro': 'computador de render desligado: o VPS fez'}, '&status=eq.pendente'):
                etapa(j['projeto_id'], 'Computador de render desligado: o VPS vai fazer o 4K', None, andamento_versao=None)

def _permitidos(job):
    p = job['pacote']; return {n for n in p['arquivos'] + p['transcricoes'] + [p.get('plano')] + (p.get('anexos') or []) if n}

def _rota_worker(h, metodo, u):
    """Rotas /worker/* : autenticadas pelo BORA_WORKER_TOKEN (cabeçalho X-Bora-Worker); o worker só vê os arquivos do trabalho dele."""
    if not WTOKEN or not hmac.compare_digest(h.headers.get('X-Bora-Worker', ''), WTOKEN): return h._r(401, {'erro': 'token do worker'})
    nome_w = (h.headers.get('X-Bora-Worker-Nome') or 'worker')[:40]
    VISTO[nome_w] = time.time()
    partes = [urllib.parse.unquote(x) for x in u.path.split('/')[2:]]
    acao = partes[0] if partes else ''
    corpo = json.loads(h.rfile.read(int(h.headers.get('Content-Length', 0))) or b'{}') if metodo == 'POST' else {}
    if acao == 'pegar' and metodo == 'POST':
        for j in sb('GET', '/rest/v1/render_trabalhos?status=eq.pendente&order=criado_em&limit=3&select=*'):
            ok = fila_patch(j['id'], {'status': 'renderizando', 'worker': nome_w, 'codificador': corpo.get('codificador', 'x265'),
                                      'pego_em': agora(), 'batida': agora(), 'tentativas': j['tentativas'] + 1}, '&status=eq.pendente')
            if ok:                                     # PATCH condicional: só um worker consegue pegar
                d = pasta(j['projeto_id'])
                arqs = [{'nome': n, 'tamanho': os.path.getsize(os.path.join(d, n))} for n in sorted(_permitidos(j)) if os.path.exists(os.path.join(d, n))]
                etapa(j['projeto_id'], f'Render externo ({nome_w}) começou', None)
                return h._r(200, {'job': j['id'], 'pacote': j['pacote'], 'arquivos': arqs})
        return h._r(204, {})
    jid = partes[1] if len(partes) > 1 else ''
    job = JOBS.get(jid) if JOBS.get(jid, {}).get('worker') == nome_w else fila_get(jid)
    if not job or job.get('worker') != nome_w: return h._r(404, {'erro': 'trabalho não é deste worker'})
    if job['status'] != 'renderizando': return h._r(409, {'erro': 'trabalho ' + job['status']})
    d = pasta(job['projeto_id'])
    if acao == 'arquivo' and metodo == 'GET':
        nome = os.path.basename(partes[2] if len(partes) > 2 else '')
        if nome not in _permitidos(job) or not os.path.exists(os.path.join(d, nome)): return h._r(404, {'erro': 'arquivo'})
        arq = os.path.join(d, nome); total = os.path.getsize(arq)
        ini = int((h.headers.get('Range') or 'bytes=0-').split('=')[1].split('-')[0] or 0)
        h.send_response(206 if ini else 200); h.send_header('Content-Type', 'application/octet-stream')
        h.send_header('Content-Length', str(total - ini))
        if ini: h.send_header('Content-Range', f'bytes {ini}-{total - 1}/{total}')
        h.end_headers()
        with open(arq, 'rb') as f:
            f.seek(ini)
            while True:
                b = f.read(1 << 20)
                if not b: break
                h.wfile.write(b)
        return
    if acao == 'progresso' and metodo == 'POST':
        et = job.get('etapas') or []
        if not et or et[-1].get('texto') != corpo.get('texto'):
            et.append({'t': round(time.time() - _iso_seg(job.get('pego_em'))), 'texto': corpo.get('texto'), 'pct': corpo.get('pct')})
        fila_patch(jid, {'batida': agora(), 'etapas': et})
        ULTIMA[0] = time.time()                        # worker vivo: o VPS não considera travado
        if corpo.get('texto') and corpo.get('pct') is not None:
            etapa(job['projeto_id'], corpo['texto'], corpo['pct'], **{k: corpo.get(k) for k in ('detalhe', 'previsao_s') if corpo.get(k) is not None})
        return h._r(200, {'ok': True})
    if acao == 'resultado':                            # envio do resultado em partes (retomável)
        nome = os.path.basename(partes[2] if len(partes) > 2 else '')
        if not nome: return h._r(400, {'erro': 'nome'})
        dest = os.path.join(d, '_externo'); os.makedirs(dest, exist_ok=True); parcial = os.path.join(dest, nome + '.parcial')
        atual = os.path.getsize(parcial) if os.path.exists(parcial) else 0
        if metodo == 'GET': return h._r(200, {'recebido': atual})
        if int(urllib.parse.parse_qs(u.query).get('offset', ['0'])[0]) != atual: return h._r(409, {'recebido': atual})
        n = int(h.headers.get('Content-Length', 0))
        with open(parcial, 'ab') as f:
            while n > 0:
                b = h.rfile.read(min(n, 1 << 20))
                if not b: break
                f.write(b); n -= len(b)
        return h._r(200, {'recebido': os.path.getsize(parcial)})
    if acao == 'concluir' and metodo == 'POST':
        res = corpo.get('resultado') or {}; tam = corpo.get('tamanhos') or {}
        for rel in res.get('arquivos') or []:
            parcial = os.path.join(d, '_externo', os.path.basename(rel) + '.parcial')
            if not os.path.exists(parcial) or os.path.getsize(parcial) != int(tam.get(rel, -1)): return h._r(409, {'erro': f'{rel} incompleto'})
        for rel in res.get('arquivos') or []:
            final = os.path.normpath(os.path.join(d, rel))
            if not final.startswith(d + os.sep): return h._r(400, {'erro': 'caminho'})
            os.makedirs(os.path.dirname(final), exist_ok=True)
            os.replace(os.path.join(d, '_externo', os.path.basename(rel) + '.parcial'), final)
        fila_patch(jid, {'status': 'concluido', 'resultado': res, 'concluido_em': agora(), 'segundos': corpo.get('segundos'),
                         'etapas': (job.get('etapas') or []) + [{'t': corpo.get('segundos'), 'texto': 'Concluído no ' + nome_w, 'pct': 100}]})
        return h._r(200, {'ok': True})
    if acao == 'falhou' and metodo == 'POST':
        _falhou(job, corpo.get('erro') or 'falhou')
        return h._r(200, {'ok': True})
    return h._r(404, {'erro': 'rota'})

def receber_originais(pid, lista):
    """Os originais chegaram (pelo app ou pelo Drive) como original_NN.parcial: confere, grava no projeto, gera a capa e cria a v1."""
    d = pasta(pid); arquivos = []
    for i, a in enumerate(lista, 1):
        parcial = os.path.join(d, f'original_{i:02d}.parcial')
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
    return arquivos, aviso

def importar_do_drive(pid, lista):
    """Baixa os vídeos escolhidos do Drive direto pra VPS (servidor com servidor) e segue o fluxo normal."""
    import drive
    try:
        total = sum(int(a.get('tamanho') or 0) for a in lista) or 1; feito = [0]; ult = [0.0]
        for i, a in enumerate(lista, 1):
            base = feito[0]
            def prog(n, _t, i=i, base=base):
                if time.time() - ult[0] > 5:
                    ult[0] = time.time()
                    etapa(pid, f'Baixando do Drive ({i} de {len(lista)})', min(99, round((base + n) / total * 100)), aguardando_upload=True)
            drive.baixar(a['id'], os.path.join(pasta(pid), f'original_{i:02d}.parcial'), prog)
            feito[0] += int(a.get('tamanho') or 0)
        etapa(pid, 'Vídeos recebidos do Drive', None, aguardando_upload=True)
        receber_originais(pid, lista)
    except Exception as e:
        traceback.print_exc(); etapa(pid, 'Erro ao baixar do Drive: ' + str(e)[:120], None)

class H(BaseHTTPRequestHandler):
    def _r(self, cod, obj):
        self.send_response(cod); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(obj).encode())
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', ORIGEM)
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Bora-Token, X-Bora-Worker, X-Bora-Worker-Nome, Range')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith('/worker/'): return _rota_worker(self, 'GET', u)
        if u.path == '/drive/listar':                      # pastas e vídeos do Drive (só dentro da pasta raiz)
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            import drive
            if not drive.configurado(): return self._r(503, {'erro': 'o acesso ao Drive ainda não foi configurado no servidor'})
            try: return self._r(200, drive.listar(urllib.parse.parse_qs(u.query).get('pasta', [None])[0]))
            except PermissionError as e: return self._r(403, {'erro': str(e)})
            except Exception as e: return self._r(502, {'erro': 'Drive: ' + str(e)[:150]})
        if u.path == '/push/chave':
            import avisos; return self._r(200, {'chave': avisos.chave_publica()})
        if u.path.startswith('/final/'): return self._final(u)
        if u.path.startswith('/upload/'):                  # quanto do arquivo já chegou (pra retomar)
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            partes = u.path.split('/'); pid = partes[2]; n = int(partes[3]) if len(partes) > 3 and partes[3].isdigit() else 1
            arq = os.path.join(pasta(pid), f"{'anexo' if urllib.parse.parse_qs(u.query).get('tipo') == ['anexo'] else 'original'}_{n:02d}.parcial")
            return self._r(200, {'recebido': os.path.getsize(arq) if os.path.exists(arq) else 0})
        import time
        self._r(200, {'ok': True, 'na_fila': FILA.qsize(), 'ocupado': OCUPADO[0], 'parado_min': max(0, int((time.time() - ULTIMA[0]) / 60) - (90 if FINAIS[0] else 0)) if OCUPADO[0] else 0})
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
        if u.path.startswith('/worker/'): return _rota_worker(self, 'PUT', u)
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
        if u.path.startswith('/worker/'): return _rota_worker(self, 'POST', u)
        if u.path.startswith('/drive/importar/'):          # POST /drive/importar/<projeto> {arquivos:[{id,nome,tamanho}]}
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            import drive
            if not drive.configurado(): return self._r(503, {'erro': 'o acesso ao Drive ainda não foi configurado no servidor'})
            pid = os.path.basename(u.path.split('/')[3]); corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            lista = [{'id': str(a['id']), 'nome': os.path.basename(str(a.get('nome') or 'video.mov')), 'tamanho': int(a.get('tamanho') or 0)} for a in corpo.get('arquivos') or []]
            if not lista: return self._r(400, {'erro': 'nenhum vídeo escolhido'})
            try:
                for a in lista:                            # cada arquivo precisa estar dentro da pasta raiz
                    pais = drive._get(f"files/{a['id']}", fields='parents').get('parents') or []
                    if not pais or not drive.dentro_da_raiz(pais[0]): return self._r(403, {'erro': f"{a['nome']} está fora da pasta do Bora Studio"})
            except Exception as e: return self._r(502, {'erro': 'Drive: ' + str(e)[:150]})
            threading.Thread(target=importar_do_drive, args=(pid, lista), daemon=True).start()
            return self._r(202, {'ok': True, 'arquivos': len(lista)})
        if u.path.startswith('/final/') and u.path.endswith('/link'):
            if not usuario_da_equipe(self.headers.get('Authorization')): return self._r(401, {'erro': 'login'})
            pid = os.path.basename(u.path.split('/')[2]); exp = str(int(time.time()) + 7200)
            sig = hmac.new(TOKEN.encode(), f'{pid}:{exp}'.encode(), hashlib.sha256).hexdigest()
            return self._r(200, {'url': f'https://{self.headers.get("Host", "editor.borasolucoesdigitais.com")}/final/{pid}?exp={exp}&sig={sig}'})
        if u.path == '/push/inscrever':
            uid = usuario_da_equipe(self.headers.get('Authorization'))
            if not uid: return self._r(401, {'erro': 'login'})
            import avisos; corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            return self._r(200, {'ok': True, 'aparelhos': avisos.inscrever(corpo, uid)})
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
            for i, a in enumerate(lista, 1):
                parcial = os.path.join(d, f'original_{i:02d}.parcial')
                if not os.path.exists(parcial) or os.path.getsize(parcial) != int(a.get('tamanho', -1)):
                    return self._r(409, {'erro': f'arquivo {i} incompleto'})
            arquivos, aviso = receber_originais(pid, lista)
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
                if (retomar and m.get('falha_memoria') != v['id']) or m.get('andamento_versao') != v['id']:
                    enfileirar({'tipo': 'ajuste' if v['numero'] > 1 else 'nova_edicao', 'projeto_id': v['projeto_id'], 'versao_id': v['id'], 'versao': v['numero']})
            for pr in sb('GET', '/rest/v1/projetos?status=eq.aprovado&select=id,cliente_id,original_meta,versoes(id,numero,final_drive_id)'):
                m = pr.get('original_meta') or {}; vs = sorted(pr['versoes'], key=lambda x: x['numero'])
                if vs and not vs[-1]['final_drive_id'] and not m.get('final_pronto') and ((retomar and m.get('falha_memoria') != 'final:' + vs[-1]['id']) or m.get('andamento_versao') != 'final:' + vs[-1]['id']):
                    enfileirar({'tipo': 'final', 'projeto_id': pr['id'], 'cliente': pr['cliente_id'], 'versao_id': vs[-1]['id'], 'versao': vs[-1]['numero']})
            retomar = False
            if EXTERNO: cuidar_da_fila()
        except Exception as e:
            print('vigia:', e, flush=True)
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=vigia, daemon=True).start()
    for _ in range(int(os.environ.get("BORA_PARALELO", "2"))):   # até 2 vídeos ao mesmo tempo
        threading.Thread(target=trabalhador, daemon=True).start()
    print('Editor Bora Studio ouvindo na porta 8787' + (' (render externo ligado)' if EXTERNO else ''))
    ThreadingHTTPServer(('0.0.0.0', 8787), H).serve_forever()
