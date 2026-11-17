"""Prova de conceito do render externo do 4K com vídeo real (clipe 4K HDR HLG do iPhone, Fabiola / Próstata).
Prévia 480p continua no VPS. O final 4K vai pra fila e é feito pelo worker (outra pasta, outro processo, arquivos por HTTP),
sem fallback pro VPS. Compara o 4K do worker com o do renderizador atual.
O Supabase é simulado em memória (mesmas rotas REST e o PATCH condicional que impede trabalho duplicado).
Uso: python3 teste_render_externo.py"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.request, zipfile
from http.server import ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
SP = '/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad'
A, B = SP + '/poc/vps', SP + '/poc/pc'
PID, TOKEN = 'poc-prostata', 'token-de-teste-do-worker'
for d in (A, B): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
os.environ.update({'BORA_TRABALHO': A, 'SUPABASE_URL': 'http://supabase.falso', 'SUPABASE_SECRET': 'x', 'BORA_TOKEN': 'x',
                   'BORA_RENDER_EXTERNO': '1', 'BORA_WORKER_TOKEN': TOKEN})
sys.path.insert(0, AQUI)

# ---------- projeto real: original 4K HDR, transcrição, plano e 4 cards anexados ----------
P = os.path.join(A, PID); os.makedirs(P)
os.symlink(SP + '/prost/raw/IMG_2589.MOV', P + '/original_01.mov')
shutil.copy(SP + '/trab/teste/transcricao_01.json', P)
anexos = []
for k, f in enumerate(sorted(glob.glob(SP + '/canetas/card*_9x16.png')), 1):
    shutil.copy(f, P + f'/anexo_{k:02d}.png'); anexos.append({'nome': os.path.basename(f), 'caminho': P + f'/anexo_{k:02d}.png', 'tipo': 'imagem', 'versao': 1})
pl = json.load(open(SP + '/trab/teste/plano_v1.json')); pl['segmentos'] = pl['segmentos'][:1]            # trecho curto (~3,4 s) em 4K; o benchmark completo fica pro Acer
pl['insercoes'] = [{'anexo': k + 1, 'palavra_inicio': 6 + 2 * k, 'palavra_fim': 9 + 2 * k, 'modo': 'flutuando'} for k in range(2)]
json.dump(pl, open(P + '/plano_v1.json', 'w'), ensure_ascii=False)

# ---------- Supabase em memória ----------
TAB = {'projetos': [{'id': PID, 'cliente_id': 'fabiola', 'titulo': 'Próstata POC', 'status': 'editando', 'cores_texto': {'leg': '#FFFFFF', 'dest': '#C8B9A7'},
                     'original_meta': {'anexos': anexos, 'arquivos': [{'nome': 'IMG_2589.MOV', 'caminho': P + '/original_01.mov'}]}}],
       'clientes': [{'id': 'fabiola', 'nome': 'Fabiola Pedron'}], 'dna_ativo': [], 'regras_globais': [], 'render_trabalhos': [],
       'versoes': [{'id': 'v1', 'projeto_id': PID, 'numero': 1, 'status': 'editando'}]}
TRAVA = threading.Lock(); SEQ = [0]
def _filtra(linhas, q):
    for k, v in q:
        if k in ('select', 'order', 'limit'): continue
        op, val = v.split('.', 1)
        if op == 'eq': linhas = [l for l in linhas if str(l.get(k)) == val]
        elif op == 'in': linhas = [l for l in linhas if str(l.get(k)) in val.strip('()').split(',')]
    return linhas
def sb_falso(metodo, path, corpo=None):
    tab, _, qs = path.split('/rest/v1/')[1].partition('?')
    q = [tuple(x.split('=', 1)) for x in qs.split('&') if '=' in x]
    with TRAVA:
        linhas = TAB.setdefault(tab, [])
        if metodo == 'GET':
            r = _filtra(linhas, q)
            if dict(q).get('order', '').startswith('criado_em'): r = sorted(r, key=lambda l: l['criado_em'])
            if 'limit' in dict(q): r = r[:int(dict(q)['limit'])]
            return json.loads(json.dumps(r))
        if metodo == 'PATCH':
            r = _filtra(linhas, q)
            for l in r: l.update(json.loads(json.dumps(corpo)))
            return json.loads(json.dumps(r))
        if metodo == 'POST':
            novo = {'status': 'pendente', 'tentativas': 0, 'etapas': [], **json.loads(json.dumps(corpo))}
            if tab == 'render_trabalhos':
                if any(l['versao_id'] == novo['versao_id'] and l['tipo'] == novo['tipo'] and l['status'] in ('pendente', 'renderizando') for l in linhas):
                    raise urllib.error.HTTPError(path, 409, 'duplicado', {}, None)   # índice único parcial
                SEQ[0] += 1; novo.update({'id': f'job{SEQ[0]}', 'criado_em': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
            linhas.append(novo); return [json.loads(json.dumps(novo))]

import montagem, motor, servidor
servidor.sb = sb_falso
ENVIADOS = {}
motor._subir = lambda sb, caminho, arq, tipo: ENVIADOS.__setitem__(caminho, shutil.copy(arq, arq + '.enviado.mp4'))
srv = ThreadingHTTPServer(('127.0.0.1', 0), servidor.H); PORTA = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

def md5_video(arq):
    return subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-map', '0:v', '-f', 'md5', '-'], capture_output=True, text=True).stdout.strip()[4:16]
def md5_audio(arq):
    return subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-map', '0:a', '-f', 'md5', '-'], capture_output=True, text=True).stdout.strip()[4:16]
def info(arq):
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,pix_fmt,color_transfer,color_primaries,profile', '-of', 'json', arq], capture_output=True, text=True).stdout)['streams'][0]
    return f"{s['width']}x{s['height']} {s['profile']} {s['pix_fmt']} {s['color_transfer']} {s['color_primaries']}"
def ssim(a, b):
    o = subprocess.run(['ffmpeg', '-v', 'info', '-i', a, '-i', b, '-lavfi', 'ssim', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return (re.findall(r'All:([\d.]+)', o) or ['?'])[-1]
def worker(extra=None):
    env = {**os.environ, 'BORA_TRABALHO': B, 'BORA_EDITOR': f'http://127.0.0.1:{PORTA}', 'BORA_WORKER_NOME': 'pc-teste', **(extra or {})}
    return subprocess.Popen([sys.executable, os.path.join(AQUI, 'render_worker.py'), '--uma-vez'], env=env)
def call(metodo, rota, token=TOKEN, nome='pc-teste', corpo=None):
    h = {'X-Bora-Worker': token, 'X-Bora-Worker-Nome': nome, 'Content-Type': 'application/json'}
    try:
        r = urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{PORTA}{rota}', data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo, headers=h))
        return r.status
    except urllib.error.HTTPError as e:
        return e.code

R = []
def ok(nome, cond, det=''): R.append(cond); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
def job_final(): return next(j for j in reversed(TAB['render_trabalhos']) if j['tipo'] == 'final')
def M(): return TAB['projetos'][0]['original_meta']

# 1) com o render externo ligado, a prévia 480p continua no VPS (estrutura atual)
servidor.EXTERNO = True
servidor.processar({'tipo': 'nova_edicao', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
ok('prévia 480p feita no próprio VPS, sem ir pra fila externa', not TAB['render_trabalhos'] and TAB['versoes'][0]['status'] == 'revisao'
   and info(P + '/previa_v1.mp4').startswith('480x854') and any(k.endswith('/v1.mp4') for k in ENVIADOS), info(P + '/previa_v1.mp4'))

# 2) final 4K pelo renderizador atual (referência)
TAB['projetos'][0]['status'] = 'aprovado'; servidor.EXTERNO = False
t = time.time(); servidor.processar({'tipo': 'final', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1}); t_ref4 = time.time() - t
zref = P + '/final_ref.zip'; shutil.move(M()['final_zip'], zref); M().update({'final_pronto': None, 'final_zip': None})
print(f'referência 4K (renderizador atual): {t_ref4:.0f} s', flush=True)

# 3) final com render externo e o Acer DESLIGADO: fica na fila, o VPS não renderiza
servidor.EXTERNO = True
t = time.time(); servidor.processar({'tipo': 'final', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1}); t_fila = time.time() - t
j = job_final(); time.sleep(12); servidor.cuidar_da_fila()
ok('aprovação só grava o trabalho e libera o VPS na hora', t_fila < 30 and j['status'] == 'pendente', f'{t_fila:.1f} s')
ok('Acer desligado: trabalho continua na fila, sem fallback pro VPS', job_final()['status'] == 'pendente' and not job_final().get('worker')
   and not M().get('final_pronto') and 'fila do render 4K' in (M().get('andamento') or ''), M().get('andamento'))
servidor.processar({'tipo': 'final', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
ok('aprovar de novo (ou VPS reiniciado) não duplica o trabalho', sum(x['tipo'] == 'final' for x in TAB['render_trabalhos']) == 1)

# 4) segurança e duplicidade
ok('token errado é recusado', call('POST', '/worker/pegar', token='errado', corpo={}) == 401)
res = []; ths = [threading.Thread(target=lambda n=n: res.append(call('POST', '/worker/pegar', nome=f'acer{n}', corpo={}))) for n in range(5)]
[x.start() for x in ths]; [x.join() for x in ths]
ok('5 workers ao mesmo tempo: só 1 pega o trabalho', sorted(res) == [200, 204, 204, 204, 204], str(sorted(res)))
dono = job_final()['worker']; jid = job_final()['id']
ok('outro worker não baixa arquivo do trabalho', call('GET', f'/worker/arquivo/{jid}/original_01.mov', nome='intruso') == 404)
ok('nome fora do pacote é recusado', call('GET', f'/worker/arquivo/{jid}/..%2F..%2Fbora.env', nome=dono) == 404)

# 5) falha no Acer: volta pra fila (tentativa 1)
call('POST', f'/worker/falhou/{jid}', nome=dono, corpo={'erro': 'falha simulada no Acer'})
ok('falha no Acer: trabalho volta pra fila', job_final()['status'] == 'pendente' and job_final()['tentativas'] == 1 and 'tentar de novo' in M()['andamento'], M()['andamento'])
# 6) Acer some no meio (sem sinal): volta pra fila (tentativa 2)
call('POST', '/worker/pegar', nome='acer-sumiu', corpo={}); job_final()['batida'] = '2026-01-01T00:00:00Z'
servidor.cuidar_da_fila()
ok('Acer sem sinal: trabalho volta pra fila', job_final()['status'] == 'pendente' and job_final()['tentativas'] == 2 and 'sem sinal' in job_final()['erro'])

# 7) Acer ligado: renderiza o 4K e o VPS entrega no app (tentativa 3)
w = worker({'BORA_WORKER_NOME': 'acer-teste'}); t = time.time(); w.wait(); t_ext4 = time.time() - t
servidor.cuidar_da_fila(); job4 = job_final()
print('\nTRABALHO 4K', json.dumps({k: job4.get(k) for k in ('status', 'worker', 'codificador', 'tentativas', 'segundos', 'erro')}, ensure_ascii=False))
for e in job4['etapas']: print('   ', e)
ok('final 4K renderizado no worker e entregue no app', job4['status'] == 'entregue' and M().get('final_pronto') and os.path.exists(M().get('final_zip') or ''))
d1, d2 = SP + '/poc/zref', SP + '/poc/zext'
for z, d in ((zref, d1), (M()['final_zip'], d2)): shutil.rmtree(d, ignore_errors=True); zipfile.ZipFile(z).extractall(d)
for nome in sorted(os.listdir(d1)):
    a, b = os.path.join(d1, nome), os.path.join(d2, nome)
    if nome.endswith('.mp4'):
        ok(f'{nome}: imagem idêntica à do renderizador atual', md5_video(a) == md5_video(b), info(b) + ('' if md5_video(a) == md5_video(b) else f' SSIM {ssim(a, b)}'))
        ok(f'{nome}: áudio idêntico', md5_audio(a) == md5_audio(b))
    else:
        ok(f'{nome}: idêntico', open(a, 'rb').read() == open(b, 'rb').read())
print(f'tempo 4K: atual {t_ref4:.0f} s | worker {t_ext4:.0f} s (inclui baixar os originais e devolver o zip)')

# 8) limite de tentativas: depois de 3 falhas vira erro com Tentar de novo (sem loop e sem VPS)
TAB['render_trabalhos'].append({**job4, 'id': 'jobY', 'versao_id': 'v9', 'status': 'renderizando', 'worker': 'acer-teste', 'tentativas': 3})
call('POST', '/worker/falhou/jobY', nome='acer-teste', corpo={'erro': 'memória insuficiente no trecho 2 (3200 MB, código -9)'})
y = TAB['render_trabalhos'][-1]
ok('3ª falha: vira erro claro no app, sem repetir sozinho', y['status'] == 'falhou' and M()['andamento'].startswith('Erro: memória') and M().get('falha_memoria') == 'final:v9', M()['andamento'])

print(f'\n{sum(R)} de {len(R)} verificações passaram')
