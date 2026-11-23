"""Teste das rotas da aba Biblioteca (editor real, login e Drive simulados): lista, som, prévia de fonte, escolha e segurança."""
import json, os, shutil, subprocess, sys, tempfile, threading, urllib.error, urllib.request
os.environ.update(SUPABASE_URL='https://x', SUPABASE_SECRET='x', BORA_TOKEN='x', BORA_WORKER_TOKEN='tk')
D = tempfile.mkdtemp(); os.environ['BORA_TRABALHO'] = D
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=2:c=pink:a=0.8', D + '/w.mp3'], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=900:d=0.3', D + '/p.wav'], check=True)
import drive, biblioteca, servidor
nomes = ['Pop 7.wav', 'Pop 12.wav', 'ES_Swooshes, Whoosh, Classic, Airy - Epidemic Sound.mp3', 'Beep 1.wav']
sons = [{'id': f's{i}xxxxxxx', 'nome': n, 'tamanho': 1000 + i, 'mime': 'audio/x'} for i, n in enumerate(nomes)]
fts = [{'id': 'f1', 'nome': 'ChamberiText-Regular.otf', 'tamanho': 9, 'mime': 'x'}, {'id': 'f2', 'nome': 'ChamberiText-Bold.otf', 'tamanho': 9, 'mime': 'x'},
       {'id': 'f3', 'nome': 'Roboto-VariableFont_wdth,wght.ttf', 'tamanho': 9, 'mime': 'x'}]
drive.configurado = lambda: True
drive.achar_pasta = lambda nome, pai=None: 'id_' + nome
drive.listar_arquivos = lambda p: sons if p == 'id_SoundFX' else fts
def bx(fid, dest, prog=None):
    shutil.copy((D + ('/w.mp3' if nomes[int(fid[1])].endswith('mp3') else '/p.wav')) if fid.startswith('s') else os.path.join(AQUI, 'fonts', 'Poppins-Medium.ttf'), dest); return 1
drive.baixar = bx
biblioteca.CACHE = D + '/cache'; biblioteca.CONFIG = D + '/cache/config.json'; os.makedirs(D + '/cache')
servidor.usuario_da_equipe = lambda a: a == 'Bearer ok'
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(('127.0.0.1', 0), servidor.H); port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
def req(path, corpo=None, auth='Bearer ok'):
    r = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(corpo).encode() if corpo is not None else None, headers={'Authorization': auth, 'Content-Type': 'application/json'})
    try: x = urllib.request.urlopen(r, timeout=20); return x.status, x.headers.get('Content-Type'), x.read()
    except urllib.error.HTTPError as e: return e.code, e.headers.get('Content-Type'), e.read()
c, t, b = req('/biblioteca/lista'); j = json.loads(b)
ok('lista: sons, famílias de fonte (variável marcada) e escolhidos padrão', c == 200 and len(j['sons']) == 4 and [(f['familia'], f['arquivos'], f['variavel']) for f in j['fontes']] == [('ChamberiText', 2, False), ('Roboto', 1, True)]
   and j['escolhidos'] == {'whoosh': 's2xxxxxxx', 'pop': 's0xxxxxxx'}, str(j['escolhidos']))
ok('prévia da fonte usa a Regular da família', j['fontes'][0]['exemplo'] == 'ChamberiText-Regular.otf')
ok('sem login: 401 em todas', all(req(p, auth='x')[0] == 401 for p in ('/biblioteca/lista', '/biblioteca/som?id=s1xxxxxxx', '/biblioteca/fonte?id=f1')) and req('/biblioteca/escolher', {'tipo': 'pop', 'id': 's1xxxxxxx'}, auth='x')[0] == 401)
c, t, b = req('/biblioteca/som?id=s1xxxxxxx'); ok('som: áudio entregue com o tipo certo', c == 200 and t == 'audio/wav' and len(b) > 1000, f'{t} {len(b)} bytes')
ok('som fora da biblioteca: 403', req('/biblioteca/som?id=outro')[0] == 403)
c, t, b = req('/biblioteca/fonte?id=f1'); ok('prévia da fonte: PNG', c == 200 and t == 'image/png' and b[:4] == b'\x89PNG')
ok('fonte fora da biblioteca: 403', req('/biblioteca/fonte?id=zzz')[0] == 403)
c, t, b = req('/biblioteca/escolher', {'tipo': 'pop', 'id': 's1xxxxxxx'}); ok('escolher o pop: ok e devolve o nome', c == 200 and json.loads(b)['nome'] == 'Pop 12.wav')
ok('escolha inválida (tipo ou arquivo): 400', req('/biblioteca/escolher', {'tipo': 'xx', 'id': 's1xxxxxxx'})[0] == 400 and req('/biblioteca/escolher', {'tipo': 'pop', 'id': 'nada'})[0] == 400)
biblioteca._cat['quando'] = 0
ok('lista passa a mostrar a escolha', json.loads(req('/biblioteca/lista')[2])['escolhidos']['pop'] == 's1xxxxxxx')
ok('o motor usa a escolha do app no próximo vídeo', biblioteca.escolher('pop', [{'id': x['id'], 'nome': x['nome'], 'tamanho': x['tamanho']} for x in sons])['nome'] == 'Pop 12.wav')
os.remove(biblioteca.CONFIG)
ok('sem escolha do app volta pro padrão', biblioteca.escolher('pop', [{'id': x['id'], 'nome': x['nome'], 'tamanho': x['tamanho']} for x in sons])['nome'] == 'Pop 7.wav')
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
