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
                   'BORA_RENDER_EXTERNO': '1', 'BORA_WORKER_TOKEN': TOKEN, 'BORA_WHISPER': 'medium'})
sys.path.insert(0, AQUI)

# ---------- projeto real: original 4K HDR, transcrição, plano e 4 cards anexados ----------
P = os.path.join(A, PID); os.makedirs(P)
os.symlink(SP + '/prost/raw/IMG_2589.MOV', P + '/original_01.mov')
shutil.copy(SP + '/tr_vps.json', P + '/transcricao_01.json')   # transcrição feita com o código atual
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
def M(): return TAB['projetos'][0]['original_meta']
def jobs(**f): return [j for j in TAB['render_trabalhos'] if all(j.get(k) == v for k, v in f.items())]
servidor.INICIO = 0                                    # sem a espera de 30 s do começo
TR = P + '/transcricao_01.json'; tr_ref = open(TR).read()

# 1) referência: tudo no VPS (computador de render desligado)
servidor.EXTERNO = True; servidor.VISTO.clear()
servidor.processar({'tipo': 'nova_edicao', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
ok('Acer desligado: prévia feita no VPS, sem fila', not TAB['render_trabalhos'] and TAB['versoes'][0]['status'] == 'revisao')
ref = P + '/previa_ref.mp4'; shutil.copy(P + '/previa_v1.mp4', ref)
TAB['projetos'][0]['status'] = 'aprovado'
servidor.processar({'tipo': 'final', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
ok('Acer desligado: 4K feito no VPS, sem fila', not TAB['render_trabalhos'] and bool(M().get('final_pronto')))
zref = P + '/final_ref.zip'; shutil.move(M()['final_zip'], zref); M().update({'final_pronto': None, 'final_zip': None})

# 2) Acer ligado: transcrição e prévia vão pra ele; a IA (plano) fica no VPS
for f in glob.glob(P + '/previa_v1.mp4*') + glob.glob(P + '/transcricao_01.*'): os.remove(f)
w = subprocess.Popen([sys.executable, os.path.join(AQUI, 'render_worker.py')],
                     env={**os.environ, 'BORA_TRABALHO': B, 'BORA_EDITOR': f'http://127.0.0.1:{PORTA}', 'BORA_WORKER_NOME': 'acer-teste'})
for _ in range(30):
    if servidor.acer_ligado(): break
    time.sleep(1)
ok('VPS percebe o Acer ligado', servidor.acer_ligado())
TAB['versoes'][0]['status'] = 'editando'; t0 = time.time()
servidor.processar({'tipo': 'nova_edicao', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
jt = [j for j in jobs(tipo='previa') if j['pacote'].get('etapa') == 'transcricao']; jp = [j for j in jobs(tipo='previa') if not j['pacote'].get('etapa')]
ok('transcrição feita no Acer', jt and jt[-1]['status'] == 'entregue' and jt[-1]['worker'] == 'acer-teste' and os.path.exists(TR))
ok('transcrição do Acer igual à do VPS', os.path.exists(TR) and open(TR).read() == tr_ref)
ok('prévia renderizada no Acer e entregue no app', jp and jp[-1]['status'] == 'entregue' and TAB['versoes'][0]['status'] == 'revisao')
ok('prévia do Acer idêntica à do VPS (imagem)', md5_video(P + '/previa_v1.mp4') == md5_video(ref), f'{time.time() - t0:.0f} s')

# 3) Acer ligado: 4K vai pra ele e o VPS entrega quando ele termina
t0 = time.time(); servidor.processar({'tipo': 'final', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
while not jobs(tipo='final', status='concluido') and time.time() - t0 < 1500: time.sleep(5)
servidor.cuidar_da_fila(); jf = jobs(tipo='final')[-1]
ok('4K renderizado no Acer e entregue no app', jf['status'] == 'entregue' and jf['worker'] == 'acer-teste' and bool(M().get('final_pronto')), f'{time.time() - t0:.0f} s')
d1, d2 = SP + '/poc/zref', SP + '/poc/zext'
for z, d in ((zref, d1), (M()['final_zip'], d2)): shutil.rmtree(d, ignore_errors=True); zipfile.ZipFile(z).extractall(d)
for nome in sorted(os.listdir(d1)):
    ok(f'{nome}: imagem e áudio idênticos ao do VPS', md5_video(os.path.join(d1, nome)) == md5_video(os.path.join(d2, nome)) and md5_audio(os.path.join(d1, nome)) == md5_audio(os.path.join(d2, nome)), info(os.path.join(d2, nome)))

# 4) segurança e duplicidade (com o Acer ligado)
ok('token errado é recusado', call('POST', '/worker/pegar', token='errado', corpo={}) == 401)
ok('nome fora do pacote é recusado', call('GET', f"/worker/arquivo/{jf['id']}/..%2F..%2Fbora.env", nome='acer-teste') in (404, 409))

# 5) Acer desliga com 4K na fila: depois do tempo limite o VPS assume
w.terminate(); w.wait(); servidor.VISTO.clear()
M().update({'final_pronto': None, 'final_zip': None})
TAB['render_trabalhos'].append({'id': 'jobZ', 'projeto_id': PID, 'versao_id': 'v1', 'tipo': 'final', 'altura': 3840, 'status': 'pendente', 'tentativas': 0,
                                'etapas': [], 'criado_em': '2026-01-01T00:00:00Z', 'pacote': jf['pacote']})
servidor.cuidar_da_fila()
ok('Acer desligado por 10 min: 4K sai da fila e volta pro VPS', TAB['render_trabalhos'][-1]['status'] == 'cancelado' and M().get('andamento_versao') is None, M().get('andamento'))

# 6) prévia com o Acer desligado no meio (trabalho pendente sem ninguém): o VPS faz
TAB['versoes'][0]['status'] = 'editando'; servidor.VISTO['acer-teste'] = time.time()      # parece ligado na hora de decidir
for f in glob.glob(P + '/previa_v1.mp4*'): os.remove(f)
t0 = time.time(); servidor.processar({'tipo': 'nova_edicao', 'projeto_id': PID, 'versao_id': 'v1', 'versao': 1})
ok('Acer some no meio da prévia: o VPS termina sozinho', TAB['versoes'][0]['status'] == 'revisao' and md5_video(P + '/previa_v1.mp4') == md5_video(ref), f'{time.time() - t0:.0f} s')

print(f'\n{sum(R)} de {len(R)} verificações passaram')
