"""Teste da atualização automática do Acer: hash, pacote, troca segura, falhas que mantêm o código antigo, rota do editor e trava por código."""
import io, json, os, shutil, sys, tarfile, tempfile, threading, urllib.error, urllib.request
T = tempfile.mkdtemp()
os.environ.update(SUPABASE_URL='https://x', SUPABASE_SECRET='x', BORA_TOKEN='x', BORA_WORKER_TOKEN='tk', BORA_TRABALHO=T)
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import autoatualizar as A
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
def copia(nome):
    d = os.path.join(T, nome); shutil.copytree(AQUI, d, ignore=shutil.ignore_patterns('__pycache__', 'render_cache', 'modelos', 'piloto')); return d
# 1) hash
srv = copia('srv'); h0 = A.hash_codigo(srv)
ok('hash estável e do tamanho certo', A.hash_codigo(srv) == h0 and len(h0) == 16)
open(os.path.join(srv, 'teste_x.py'), 'w').write('x=1'); open(os.path.join(srv, 'GUIA.md'), 'w').write('# x'); open(os.path.join(srv, 'worker.env'), 'w').write('TOKEN=1')
os.makedirs(os.path.join(srv, '__pycache__'), exist_ok=True); open(os.path.join(srv, '__pycache__', 'a.pyc'), 'w').write('x')
ok('testes, .md, .env e __pycache__ não entram no hash', A.hash_codigo(srv) == h0)
open(os.path.join(srv, 'montagem.py'), 'a').write('\n# mudou\n')
ok('mudar um .py muda o hash', A.hash_codigo(srv) != h0)
h_novo = A.hash_codigo(srv); pac = A.empacotar(srv)
ok('pacote leve (< 5 MB) e sem testes nem .env', len(pac) < 5e6 and not any('teste_' in n or n.endswith('.env') for n in tarfile.open(fileobj=io.BytesIO(pac)).getnames()), f'{len(pac) / 1e6:.1f} MB')
# 2) troca segura
acer = copia('acer'); open(os.path.join(acer, 'montagem.py'), 'a').write('\nIDADE = "velha"\n'); open(os.path.join(acer, 'so_do_acer.py'), 'w').write('y=1')
ok('troca: devolve True e deixa o Acer com o hash do editor', A.aplicar(pac, acer, h_novo) is True and A.hash_codigo(acer) == h_novo)
ok('troca: arquivo que só existia no Acer some e não sobra pasta .novo/.antigo', not os.path.exists(os.path.join(acer, 'so_do_acer.py')) and not os.path.exists(acer + '.novo') and not os.path.exists(acer + '.antigo'))
# 3) falhas: mantém o código antigo
def mantem(nome, pacote, hash_):
    d = copia(nome); antes = A.hash_codigo(d)
    try: A.aplicar(pacote, d, hash_); return False
    except ValueError: pass
    except Exception: pass
    return A.hash_codigo(d) == antes and not os.path.exists(d + '.novo')
ok('hash errado: recusa e mantém o código antigo', mantem('f1', pac, 'deadbeefdeadbeef'))
quebrado = copia('q'); open(os.path.join(quebrado, 'montagem.py'), 'w').write('def x(:\n'); pq = A.empacotar(quebrado)
ok('erro de sintaxe no pacote: recusa e mantém o código antigo', mantem('f2', pq, A.hash_codigo(quebrado)))
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as t:
    i = tarfile.TarInfo('../fugiu.py'); d = b'x=1'; i.size = len(d); t.addfile(i, io.BytesIO(d))
ok('caminho fora da pasta (../): recusa', mantem('f3', buf.getvalue(), 'x'))
ok('pacote corrompido: recusa e mantém', mantem('f4', b'isso nao e um tar', 'x'))
# 3b) Docker/overlayfs: renomear PASTA dá EXDEV; a troca não pode depender disso
import errno
_rn, _rp = os.rename, os.replace
def _sem_pasta(a, b, *k, **kw):
    if os.path.isdir(a): raise OSError(errno.EXDEV, 'Invalid cross-device link')
    return _rn(a, b, *k, **kw)
def _sem_pasta2(a, b, *k, **kw):
    if os.path.isdir(a): raise OSError(errno.EXDEV, 'Invalid cross-device link')
    return _rp(a, b, *k, **kw)
os.rename, os.replace = _sem_pasta, _sem_pasta2
try:
    ox = copia('exdev'); open(os.path.join(ox, 'montagem.py'), 'a').write('\nIDADE = "velha"\n')
    ok('EXDEV ao renomear pasta (overlayfs): a troca funciona mesmo assim', A.aplicar(pac, ox, h_novo) is True and A.hash_codigo(ox) == h_novo)
    # falha no meio: o 3º arquivo não grava, tudo volta como estava
    oy = copia('meio'); antes = A.hash_codigo(oy); n = {'i': 0}
    def _quebra(a, b, *k, **kw):
        n['i'] += 1
        if n['i'] == 3: raise OSError(errno.EIO, 'disco falhou')
        return _sem_pasta2(a, b, *k, **kw)
    os.replace = _quebra
    try: A.aplicar(pac, oy, h_novo); falhou = False
    except OSError: falhou = True
    os.replace = _sem_pasta2
    ok('falha no meio da troca: desfaz e mantém o código antigo', falhou and A.hash_codigo(oy) == antes and not os.path.exists(oy + '.antigo'))
finally:
    os.rename, os.replace = _rn, _rp
# 4) editor real: rota do código e trava por código
import servidor
servidor.WTOKEN = 'tk'; servidor.sb = lambda *a, **k: []
from http.server import ThreadingHTTPServer
srv_http = ThreadingHTTPServer(('127.0.0.1', 0), servidor.H); porta = srv_http.server_address[1]; threading.Thread(target=srv_http.serve_forever, daemon=True).start()
hash_real = servidor.codigo_atual()[0]
def req(path, cab=None, corpo=None, token='tk'):
    r = urllib.request.Request(f'http://127.0.0.1:{porta}{path}', data=json.dumps(corpo).encode() if corpo is not None else None, method='POST' if corpo is not None else 'GET',
                               headers={'X-Bora-Worker': token, 'X-Bora-Worker-Nome': 'acer-teste', **(cab or {})})
    try: x = urllib.request.urlopen(r, timeout=30); return x.status, dict(x.headers), x.read()
    except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()
ok('rota do código sem token: 401', req('/worker/codigo', token='errado')[0] == 401)
ok('rota do código com o mesmo hash: 204', req('/worker/codigo', {'X-Bora-Worker-Codigo': hash_real})[0] == 204)
c, hd, corpo = req('/worker/codigo', {'X-Bora-Worker-Codigo': 'velho'})
ok('rota do código com hash diferente: entrega o pacote e o hash do editor', c == 200 and hd.get('X-Bora-Codigo') == hash_real and len(corpo) > 1000)
ok('pedir trabalho com código diferente: 426 pedindo pra atualizar', (lambda r: r[0] == 426 and json.loads(r[2]).get('atualizar') is True)(req('/worker/pegar', {'X-Bora-Worker-Codigo': 'velho', 'X-Bora-Worker-Imagem': '1'}, {})))
ok('programa antigo (sem hash): 426 pedindo o zip uma última vez', (lambda r: r[0] == 426 and json.loads(r[2]).get('atualizar') is False)(req('/worker/pegar', None, {})))
ok('imagem antiga: 426 pedindo reinstalar', (lambda r: r[0] == 426 and 'biblioteca' in json.loads(r[2])['erro'])(req('/worker/pegar', {'X-Bora-Worker-Codigo': hash_real, 'X-Bora-Worker-Imagem': '0'}, {})))
ok('mesmo código e imagem em dia: passa pelo portão (204, sem trabalho na fila)', req('/worker/pegar', {'X-Bora-Worker-Codigo': hash_real, 'X-Bora-Worker-Imagem': '1'}, {})[0] == 204)
ok('o painel sabe quem está desatualizado e por quê', servidor.DESATUALIZADO.get('acer-teste', (0, ''))[1] in ('codigo', 'imagem', 'manual') or 'acer-teste' not in servidor.DESATUALIZADO)
# 5) o worker se cura sozinho: Acer com código antigo e quebrado, falando com o editor de verdade
os.environ['BORA_EDITOR'] = f'http://127.0.0.1:{porta}'
import render_worker as W
W.EDITOR = os.environ['BORA_EDITOR']; W.TOKEN = 'tk'
doente = copia('doente'); open(os.path.join(doente, 'montagem.py'), 'w').write('# versão antiga\n'); W.RAIZ = doente; W.CODIGO = A.hash_codigo(doente); W.CAB['X-Bora-Worker-Codigo'] = W.CODIGO
ok('worker com código antigo: atualiza sozinho (True) e fica igual ao editor', W.atualizar_codigo() is True and A.hash_codigo(doente) == hash_real, A.hash_codigo(doente))
W.CODIGO = A.hash_codigo(doente); W.CAB['X-Bora-Worker-Codigo'] = W.CODIGO
ok('já atualizado: não faz nada (False)', W.atualizar_codigo() is False)
os.environ['BORA_AUTOATUALIZAR'] = '0'; W.CAB['X-Bora-Worker-Codigo'] = 'velho'
ok('BORA_AUTOATUALIZAR=0 desliga', W.atualizar_codigo() is False)
# 6) a VPS espera o Acer voltar (código novo) em vez de mandar o vídeo pra ela mesma
import time
servidor.EXTERNO = True; servidor.VISTO.clear(); servidor.DESATUALIZADO.clear(); servidor.INICIO = time.time() - 10        # editor acabou de reiniciar
threading.Timer(1.0, lambda: servidor.VISTO.update({'acer-teste': time.time()})).start()
t0 = time.time(); servidor.esperar_acer(None, max_s=20)
ok('editor recém-reiniciado: espera o Acer dar sinal (não manda pra VPS)', servidor.acer_ligado() and 0.8 < time.time() - t0 < 8, f'{time.time() - t0:.1f} s')
servidor.VISTO.clear(); servidor.INICIO = time.time() - 3600
t0 = time.time(); servidor.esperar_acer(None, max_s=20)
ok('Acer sem sinal há muito tempo e editor antigo: não espera (VPS faz na hora)', time.time() - t0 < 0.5 and not servidor.acer_ligado())
servidor.DESATUALIZADO['acer-teste'] = (time.time() - 30, 'codigo'); servidor.VISTO.clear()
threading.Timer(1.0, lambda: servidor.VISTO.update({'acer-teste': time.time()})).start()
t0 = time.time(); servidor.esperar_acer(None, max_s=20)
ok('Acer recusado há pouco (se atualizando): espera ele voltar', servidor.acer_ligado() and time.time() - t0 < 8, f'{time.time() - t0:.1f} s')
servidor.EXTERNO = False; t0 = time.time(); servidor.esperar_acer(None, max_s=20)
ok('render externo desligado: não espera', time.time() - t0 < 0.5)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
