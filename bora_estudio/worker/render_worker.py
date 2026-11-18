#!/usr/bin/env python3
"""Render worker do Bora Studio: roda em qualquer máquina (Windows com Docker Desktop, Linux, nuvem com GPU).
Pede trabalho ao editor do VPS, baixa só os arquivos daquele trabalho (com cache e retomada), renderiza com o MESMO
motor (motor.renderizar) e devolve o resultado. Não tem chave do Supabase nem da IA: só o BORA_WORKER_TOKEN.

Variáveis: BORA_EDITOR (ex.: https://editor.borasolucoesdigitais.com), BORA_WORKER_TOKEN, BORA_WORKER_NOME (ex.: pc-lincoln),
           BORA_TRABALHO (pasta local de cache), BORA_ACELERACAO (auto | x265 | nvenc).
Uso: python3 render_worker.py            (fica esperando trabalho)
     python3 render_worker.py --uma-vez  (pega no máximo um trabalho e sai)
     python3 render_worker.py --teste    (só mostra os codificadores e o teste do NVENC)"""
import json, os, sys, time, traceback, urllib.error, urllib.parse, urllib.request

EDITOR = os.environ.get('BORA_EDITOR', 'https://editor.borasolucoesdigitais.com').rstrip('/')
TOKEN = os.environ.get('BORA_WORKER_TOKEN', '')
NOME = os.environ.get('BORA_WORKER_NOME', 'worker')[:40]
TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')
os.environ.setdefault('BORA_ACELERACAO', 'auto')
PARTE = 8 << 20

def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)

def chamar(metodo, rota, corpo=None, dados=None, extra=None, tentativas=5):
    """HTTP com o token do worker; repete em falhas de rede (não em recusas do editor)."""
    for t in range(tentativas):
        try:
            h = {'X-Bora-Worker': TOKEN, 'X-Bora-Worker-Nome': NOME, **(extra or {})}
            if corpo is not None: dados = json.dumps(corpo).encode(); h['Content-Type'] = 'application/json'
            r = urllib.request.urlopen(urllib.request.Request(EDITOR + rota, data=dados, method=metodo, headers=h), timeout=600)
            txt = r.read(); return r.status, (json.loads(txt) if txt else {})
        except urllib.error.HTTPError as e:
            if e.code < 500: return e.code, json.loads(e.read() or b'{}')
            erro = e
        except Exception as e:
            erro = e
        time.sleep(min(60, 3 * 2 ** t))
    raise RuntimeError(f'sem conexão com o editor: {erro}')

def baixar(job, nome, tamanho, pasta):
    """Baixa um arquivo do trabalho; se já existe com o mesmo tamanho (cache), não baixa de novo; retoma do ponto onde parou."""
    final = os.path.join(pasta, nome)
    if os.path.exists(final) and os.path.getsize(final) == tamanho: return False
    parcial = final + '.parcial'
    for t in range(6):
        ini = os.path.getsize(parcial) if os.path.exists(parcial) else 0
        if ini >= tamanho: break
        try:
            req = urllib.request.Request(f'{EDITOR}/worker/arquivo/{job}/{urllib.parse.quote(nome)}',
                                         headers={'X-Bora-Worker': TOKEN, 'X-Bora-Worker-Nome': NOME, 'Range': f'bytes={ini}-'})
            with urllib.request.urlopen(req, timeout=600) as r, open(parcial, 'ab' if ini and r.status == 206 else 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
        except Exception as e:
            log('download interrompido, retomando:', nome, e); time.sleep(3 * (t + 1))
    if os.path.getsize(parcial) != tamanho: raise RuntimeError(f'download incompleto: {nome}')
    os.replace(parcial, final); return True

def enviar(job, caminho, rel):
    """Envia um arquivo do resultado em partes de 8 MB (retoma se a conexão cair)."""
    nome = urllib.parse.quote(os.path.basename(rel)); total = os.path.getsize(caminho)
    _, r = chamar('GET', f'/worker/resultado/{job}/{nome}'); off = r.get('recebido', 0)
    if off > total: off = 0
    with open(caminho, 'rb') as f:
        while off < total:
            f.seek(off); pedaco = f.read(PARTE)
            st, r = chamar('PUT', f'/worker/resultado/{job}/{nome}?offset={off}', dados=pedaco, extra={'Content-Type': 'application/octet-stream'})
            if st not in (200, 409): raise RuntimeError(f'envio recusado ({st}): {r}')
            off = r['recebido']
    return total

def um_trabalho():
    import codificadores
    cod = codificadores.escolher(); os.environ['BORA_INTERMEDIARIO'] = cod
    st, r = chamar('POST', '/worker/pegar', {'codificador': cod})
    if st == 204: return False
    if st != 200: raise RuntimeError(f'editor recusou ({st}): {r}')
    job, pac = r['job'], r['pacote']; pasta = os.path.join(TRAB, pac['projeto_id']); os.makedirs(pasta, exist_ok=True)
    t0 = time.time(); log(f"trabalho {job[:8]}: {pac['tipo']} v{pac['n']} {pac['altura']}p, intermediários em {cod}")
    ultimo = [0.0, '']
    def etapa(texto, pct=None, **extra):
        if texto == ultimo[1] and time.time() - ultimo[0] < 10: return     # no máximo a cada 10 s por etapa
        ultimo[:] = [time.time(), texto]
        st, rr = chamar('POST', f'/worker/progresso/{job}', {'texto': texto, 'pct': pct, **extra})
        if st == 409: raise RuntimeError('o editor cancelou ou pegou de volta este trabalho')
        log(f'{pct if pct is not None else "":>3}% {texto}')
    import threading
    fim = threading.Event()
    def batida():                                      # sinal de vida mesmo nas etapas longas (o VPS assume se sumir 15 min)
        while not fim.wait(60):
            try: chamar('POST', f'/worker/progresso/{job}', {'texto': ultimo[1], 'pct': None}, tentativas=1)
            except Exception: pass
    threading.Thread(target=batida, daemon=True).start()
    try:
        etapa('Baixando os arquivos pro render externo', 3)
        novos = sum(baixar(job, a['nome'], a['tamanho'], pasta) for a in r['arquivos'])
        log(f"{len(r['arquivos'])} arquivos ({novos} baixados, {len(r['arquivos']) - novos} do cache)")
        import motor, montagem
        if pac.get('etapa') == 'transcricao':          # só transcrever (a IA monta o plano no VPS)
            feitos = []
            for i, a in enumerate(pac['arquivos'], 1):
                n = len(pac['arquivos']); rotulo = 'o vídeo' if n == 1 else f'o vídeo {i} de {n}'
                etapa(f'Transcrevendo {rotulo}', 8 + int(17 * (i - 1) / n))
                montagem.transcrever(os.path.join(pasta, a), os.path.join(pasta, f'transcricao_{i:02d}.json')); feitos.append(f'transcricao_{i:02d}.json')
            montagem.liberar_modelo()
            res = {'arquivos': feitos}
        else:
            res = motor.renderizar(pac, etapa, pasta)
        etapa('Enviando o resultado pro editor', 96)
        tam = {rel: enviar(job, os.path.join(pasta, rel), rel) for rel in res['arquivos']}
        st, rr = chamar('POST', f'/worker/concluir/{job}', {'resultado': res, 'tamanhos': tam, 'segundos': round(time.time() - t0)})
        if st != 200: raise RuntimeError(f'editor não aceitou o resultado ({st}): {rr}')
        log(f'concluído em {round(time.time() - t0)} s')
    except Exception as e:
        traceback.print_exc()
        chamar('POST', f'/worker/falhou/{job}', {'erro': str(e)[:300]})
    finally:
        fim.set()
    return True

if __name__ == '__main__':
    import codificadores
    log('Bora Studio render worker', NOME, '->', EDITOR)
    log('codificadores:', json.dumps(codificadores.relatorio(), ensure_ascii=False))
    if '--teste' in sys.argv: sys.exit(0)
    if not TOKEN: sys.exit('defina BORA_WORKER_TOKEN')
    while True:
        try:
            pegou = um_trabalho()
        except Exception as e:
            log('erro:', e); pegou = False
        if '--uma-vez' in sys.argv: break
        if not pegou: time.sleep(5)
