"""Transcrição, cortes e montagem do vídeo a partir dos ORIGINAIS, sem tratamento de imagem.
- transcrever(): faster-whisper com tempo por palavra (cache em JSON)
- pecas(): trechos escolhidos pelo plano, menos as pausas longas (nunca dentro de uma palavra)
- render_base(): recorte geométrico + escala, HDR continua HDR (HEVC 10 bits, mesmas primárias/transferência)
  e áudio fiel ao gravado (só volume em -14 LUFS com ganho fixo)."""
import json, os, re, subprocess, threading, wave, tempfile
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
import numpy as np

FPS = 30000 / 1001
ENQ = {'total': (1.0, 0.30), 'aberto': (1.18, 0.30), 'medio': (1.32, 0.28), 'fechado': (1.48, 0.26)}   # zoom, posição do rosto (aprovados na Fabiola)
# Pausas: silêncio de verdade (abaixo do limiar) maior que min_s vira 2*mantem_s; nas pontas de cada trecho sobra borda_s.
# Antes: 0,30 / 0,10 / 0,18 (cada junção carregava uns 0,36 s de silêncio; o motor ainda protege 120 ms depois de cada palavra, e o total da pausa interna fica uns 0,24 s). Ajuste fino por projeto no bora.env (BORA_PAUSA_*).
PAUSA = {'limiar_db': -45, 'min_s': float(os.environ.get('BORA_PAUSA_MIN', '0.25')), 'mantem_s': float(os.environ.get('BORA_PAUSA_MANTEM', '0.04')),
         'borda_s': float(os.environ.get('BORA_PAUSA_BORDA', '0.08'))}
BORDA_PELO_SOM = os.environ.get('BORA_BORDA_SOM', '1') != '0'           # começo e fim de cada trecho achados pelo áudio, não só pela transcrição
PROTEGE_PELO_SOM = os.environ.get('BORA_PROTEGE_SOM', '1') != '0'     # proteção das palavras pelo som real (0 volta a proteger pelo tempo do Whisper)
CALMA = 5                                                               # quadros de 20 ms seguidos abaixo do limiar = silêncio de verdade (100 ms)
_modelo = None

# Memória: um processo de codificação 4K usa ~3,2 GB. Por padrão só 1 roda por vez no servidor inteiro (todos os projetos).
# Reversível: BORA_4K_SIMULTANEOS=2 no docker-compose quando a VPS tiver a memória contratada.
TRAVA_4K = threading.Semaphore(max(1, int(os.environ.get('BORA_4K_SIMULTANEOS', '1'))))
def pesado(altura):
    return TRAVA_4K if altura >= 1500 else nullcontext()

class SemMemoria(RuntimeError):
    """O sistema matou o processo por falta de memória (OOM). Não é repetido sozinho."""

def _vigiar(arq, total, cb, parar):
    """Lê o(s) arquivo(s) de progresso (ffmpeg -progress 'frame=N' ou o hdr_texto 'N') e avisa a fração feita (soma dos pedaços)."""
    while not parar.wait(4):
        feito, achou = 0, False
        for a in (arq if isinstance(arq, list) else [arq]):
            try: txt = open(a).read()
            except OSError: continue
            q = re.findall(r'frame=(\d+)', txt) or re.findall(r'^(\d+)\s*$', txt, re.M)
            if q: feito += int(q[-1]); achou = True
        if achou:
            try: cb(min(1.0, feito / max(total, 1)), feito)
            except Exception as e: print('progresso:', e, flush=True)

def quadros(video):
    """Total de quadros (duração x 29,97) pra calcular o avanço das etapas longas."""
    d = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout
    return max(1, round(float((re.findall(r'[\d.]+', d) or ['1'])[0]) * FPS))

def rodar(cmd, rotulo, env=None, prog=None):
    """Roda um processo medindo o pico de memória. Devolve (código, fim do erro, MB). Código -9/137 = morto por falta de memória.
    prog=(arquivo, total_de_quadros, callback): acompanha o avanço lendo o arquivo de progresso."""
    parar = threading.Event()
    if prog: threading.Thread(target=_vigiar, args=(*prog, parar), daemon=True).start()
    with tempfile.TemporaryFile() as err:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err, env=env)
        if hasattr(os, 'wait4'):                       # Linux/Docker: mede o pico de memória
            _, st, uso = os.wait4(p.pid, 0); p.returncode = rc = os.waitstatus_to_exitcode(st)
        else:                                          # Windows nativo: sem medição de memória
            rc = p.wait(); uso = None
        err.seek(0); cauda = [l for l in err.read().decode('utf-8', 'replace').splitlines() if l.strip() and 'x265 [' not in l][-4:]
    parar.set()
    mb = round(uso.ru_maxrss / 1024) if uso else 0
    if rc:
        oom = rc in (-9, 137)
        print(f"{'OOM' if oom else 'FALHA'} {rotulo}: código {rc}, pico {mb} MB" + ('' if oom else ' | ' + ' | '.join(cauda)), flush=True)
    return rc, (cauda[-1] if cauda else ''), mb

def oom(rc, msg=''): return rc in (-9, 137) or 'código -9' in msg or 'código 137' in msg or 'SIGKILL' in msg

def sh(cmd, tentativas=2):
    for t in range(tentativas):
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode == 0: return
        print('tentativa', t + 1, 'falhou, repetindo', flush=True)
    if r.returncode:
        cauda = [l for l in (r.stdout or '').splitlines() if l.strip() and 'x265 [' not in l][-6:]
        print('FALHA', ' '.join(map(str, cmd))[:300], '\n' + '\n'.join(cauda), flush=True)
        raise RuntimeError(f"{os.path.basename(str(cmd[1] if cmd[0] == 'python3' else cmd[0]))}: " + (cauda[-1] if cauda else f'código {r.returncode}')[:160])


def wav16(video, saida):
    if not os.path.exists(saida):
        sh(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video, '-vn', '-ac', '1', '-ar', '16000', saida])
    return saida

def liberar_modelo():
    """Solta o modelo de transcrição da memória (~1 GB) antes do render pesado; ele é recarregado quando precisar."""
    global _modelo
    if _modelo is not None:
        _modelo = None; import gc; gc.collect()

def transcrever(video, cache, vocab=None):
    """Palavras com tempo (segundos do arquivo original)."""
    if os.path.exists(cache): return json.load(open(cache))
    tem_audio = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', video],
                               capture_output=True, text=True).stdout.strip()
    if not tem_audio:                                  # vídeo sem som (ex.: ambiente): nenhuma palavra
        json.dump([], open(cache, 'w')); return []
    global _modelo
    from faster_whisper import WhisperModel
    if _modelo is None:
        _modelo = WhisperModel(os.environ.get('BORA_WHISPER', 'medium'), device='cpu', compute_type='int8', cpu_threads=8)
    wav = wav16(video, cache.replace('.json', '.wav'))
    a = np.frombuffer(wave.open(wav).readframes(10 ** 10), dtype=np.int16).astype(np.float32) / 32768
    import vocabulario
    kw = {'hotwords': vocabulario.dica(vocab)} if vocabulario.dica(vocab) else {}      # termos do cliente como dica em toda janela de áudio
    seg, _ = _modelo.transcribe(a, language='pt', word_timestamps=True, beam_size=1, vad_filter=True, condition_on_previous_text=False, **kw)
    pal = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in seg for w in s.words if w.word.strip()]
    pal = unir_moeda(vocabulario.aplicar(pal, vocab))
    json.dump(pal, open(cache, 'w'), ensure_ascii=False)
    return pal

def unir_moeda(pal):
    """O Whisper às vezes parte valores: 'R' '$219' ',90' (a legenda saía 'R $219 ,90'). Junta em 'R$219,90'."""
    out = []
    for w in pal:
        t = w['w']
        if out and ((out[-1]['w'] == 'R' and t.startswith('$')) or (re.match(r'^[,.]\d', t) and re.search(r'\d$', out[-1]['w']))):
            out[-1] = {**out[-1], 'w': out[-1]['w'] + t, 'e': w['e']}
        else: out.append(w)
    return out

def envelope(wav, hop=0.02):
    a = np.frombuffer(wave.open(wav).readframes(10 ** 10), dtype=np.int16).astype(np.float32) / 32768
    n = int(hop * 16000); k = len(a) // n
    return 20 * np.log10(np.sqrt((a[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9)

def borda_inicio(env, s, hop=0.02):
    """Onde começar um trecho cuja primeira palavra o Whisper marcou em `s`: antes do começo REAL da fala (o Whisper às vezes marca tarde e
    come o começo da palavra). Procura o último silêncio de verdade até 300 ms antes de `s`; a fala começa logo depois dele."""
    lim, borda = PAUSA['limiar_db'], PAUSA['borda_s']
    padrao = max(0.0, s - 0.06)
    if not BORDA_PELO_SOM: return padrao
    lo, hi = int(max(s - 0.30, 0) / hop), min(int(s / hop), len(env) - CALMA)
    for i in range(hi, lo - 1, -1):
        if (env[i:i + CALMA] < lim).all():
            onset = (i + CALMA) * hop                      # fim do silêncio = começo da fala
            return max(0.0, min(padrao, onset - borda - 0.02))
    return padrao

def borda_fim(env, e, hop=0.02):
    """Onde terminar um trecho cuja última palavra o Whisper marcou terminando em `e`: no começo do silêncio de verdade que vem depois
    (até 300 ms além de `e`, caso a palavra tenha terminado mais tarde do que o Whisper disse), nunca antes de `e`."""
    lim, borda = PAUSA['limiar_db'], PAUSA['borda_s']
    padrao = e + 0.18
    if not BORDA_PELO_SOM: return padrao
    i0, i1 = int(max(e - 0.03, 0) / hop), min(int((e + 0.30) / hop), len(env) - CALMA)
    for i in range(i0, i1):
        if (env[i:i + CALMA] < lim).all():
            return max(i * hop, e) + borda + 0.04          # tirar_pausas deixa só `borda` de silêncio no fim
    return padrao

def tirar_pausas(a, b, env, palavras, hop=0.02):
    """[a,b] do original -> lista de trechos mantidos, sem pausas longas; protege palavras (+120 ms no fim)."""
    LIM, MIN, KEEP, BORDA = PAUSA['limiar_db'], PAUSA['min_s'], PAUSA['mantem_s'], PAUSA['borda_s']
    i0, i1 = int(a / hop), int(b / hop); quieta = env[i0:i1] < LIM; q = quieta.copy()
    n_ = len(q)
    if PROTEGE_PELO_SOM and n_:
        # Protege pelo SOM REAL: 140 ms depois e 50 ms antes de cada quadro com voz (cauda e começo fracos de palavra). O Whisper costuma esticar o
        # fim de uma palavra por cima da pausa seguinte; proteger até o fim que ele marcou deixava a pausa inteira intocada (pausas de 0,4 s e mais).
        c = np.cumsum(~quieta); idx = np.arange(n_)
        lo, hi = np.clip(idx - int(0.14 / hop), 0, n_ - 1), np.clip(idx + int(0.05 / hop), 0, n_ - 1)
        voz = (c[hi] - np.where(lo > 0, c[lo - 1], 0)) > 0
        q &= ~voz
    for w in palavras:                                   # nunca é pausa onde há palavra
        if w['e'] < a or w['s'] > b: continue
        j0, j1 = max(int((w['s'] - 0.04) / hop) - i0, 0), min(int((w['e'] + 0.12) / hop) - i0 + 1, len(q))
        if PROTEGE_PELO_SOM and (~quieta[j0:j1]).any(): continue       # há voz na janela da palavra: a proteção pelo som já cobre
        q[j0:j1] = False                                 # palavra sem nenhuma energia acima do limiar (muito baixa): protege pelo tempo do Whisper, como antes
    cortes, n = [], len(q)
    j = 0
    while j < n and q[j]: j += 1
    if j * hop > BORDA: cortes.append((a, a + j * hop - BORDA))
    k = n
    while k > 0 and q[k - 1]: k -= 1
    if (n - k) * hop > BORDA: cortes.append((a + k * hop + BORDA, b))
    r = j
    while r < k:
        if q[r]:
            s = r
            while s < k and q[s]: s += 1
            if (s - r) * hop >= MIN: cortes.append((a + r * hop + KEEP, a + s * hop - KEEP))
            r = s
        else: r += 1
    res, cur = [], a
    for c0, c1 in sorted(cortes):
        if c0 > cur: res.append((cur, c0))
        cur = max(cur, c1)
    if b > cur: res.append((cur, b))
    return [(x, y) for x, y in res if y - x >= 2 / FPS]

def indice_global(palavras):
    """Numeração única das palavras de todos os arquivos (é o que a IA usa no plano): g -> (arquivo_idx, k)."""
    return [(ai, k) for ai, pw in enumerate(palavras) for k in range(len(pw))]

def pecas(plano, arquivos, palavras, pasta):
    """Plano -> peças [(arquivo_idx, frame_ini, frame_fim, quadro)] e palavras no tempo do vídeo montado."""
    G = indice_global(palavras); out, tokens, t_out, envs = [], [], 0.0, {}
    corr = {int(c['palavra']): c['texto'] for c in plano.get('correcoes', []) if str(c.get('palavra', '')).isdigit() or isinstance(c.get('palavra'), int)}
    for sg in plano['segmentos']:
        g0, g1 = max(0, int(sg['palavra_inicio'])), min(len(G) - 1, int(sg['palavra_fim']))
        if g1 < g0 or G[g0][0] != G[g1][0]: continue          # um segmento fica dentro de um arquivo só
        ai = G[g0][0]; pw = palavras[ai]; k0, k1 = G[g0][1], G[g1][1]
        if ai not in envs: envs[ai] = envelope(wav16(arquivos[ai], os.path.join(pasta, f'audio_{ai + 1:02d}.wav')))
        a = borda_inicio(envs[ai], pw[k0]['s']); b = borda_fim(envs[ai], pw[k1]['e'])
        for x, y in tirar_pausas(a, b, envs[ai], pw[k0:k1 + 1]):
            fa, fb = round(x * FPS), round(y * FPS)
            if fb - fa < 2: continue
            x, y = fa / FPS, fb / FPS
            for k in range(k0, k1 + 1):
                w = pw[k]
                if x - 0.02 <= w['s'] < y:
                    g = g0 + (k - k0)
                    tokens.append({'tok': corr.get(g, w['w']), 's': round(t_out + w['s'] - x, 3), 'e': round(t_out + min(w['e'], y) - x, 3), 'i': g})
            out.append((ai, fa, fb, sg.get('quadro', 'medio')))
            t_out += (fb - fa) / FPS
    return out, tokens, round(t_out, 3)

def duracao(video):
    d = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout
    return float((re.findall(r'[\d.]+', d) or ['0'])[0])

def classificar(palavras_do_arquivo, video, escolha=None):
    """'fala' (locução) ou 'ambiente' (B-roll). Vale a escolha do app; sem ela, pouca fala por segundo = ambiente."""
    if escolha in ('fala', 'ambiente'): return escolha
    d = max(duracao(video), 0.1); n = len(palavras_do_arquivo)
    return 'ambiente' if n <= 3 or n / d < 0.6 else 'fala'

TREMOR_ALTO = 1.2      # px por quadro (a 144x256, 10 fps): acima disso a câmera está tremendo
def tremor_por_segundo(video, cache=None):
    """Tremor da câmera em cada segundo do take: mede o deslocamento da imagem inteira entre quadros (correlação de fase)
    e soma o quanto ele muda de um quadro pro outro. Panorâmica suave dá número baixo; mão tremendo dá número alto."""
    if cache and os.path.exists(cache): return json.load(open(cache))
    W, H, F = 144, 256, 10
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-an', '-vf', f'fps={F},scale={W}:{H},format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True).stdout
    q = np.frombuffer(raw, np.uint8)[: len(raw) // (W * H) * W * H].reshape(-1, H, W).astype(np.float32)
    jan = np.outer(np.hanning(H), np.hanning(W)); desl = []
    for a, b in zip(q[:-1], q[1:]):
        A, B = np.fft.fft2((a - a.mean()) * jan), np.fft.fft2((b - b.mean()) * jan)
        R = A * np.conj(B); r = np.abs(np.fft.ifft2(R / (np.abs(R) + 1e-6)))
        y, x = np.unravel_index(np.argmax(r), r.shape)
        def sub(c, m, n):                              # refinamento subpixel (parábola nos vizinhos do pico)
            e, d = m((c - 1) % n), m((c + 1) % n); den = e - 2 * m(c) + d
            return c + (0.5 * (e - d) / den if den else 0.0)
        yf, xf = sub(y, lambda i: r[i, x], H), sub(x, lambda i: r[y, i], W)
        desl.append((yf - H if yf > H / 2 else yf, xf - W if xf > W / 2 else xf))
    d = np.array(desl, np.float32).reshape(-1, 2)
    salto = np.r_[0.0, np.hypot(*np.diff(d, axis=0).T)] if len(d) > 1 else np.zeros(len(d))
    res = [round(float(salto[i:i + F].mean()), 2) for i in range(0, len(salto), F)] or [0.0]
    if cache: json.dump(res, open(cache, 'w'))
    return res

def folha_take(video, saida, largura=256, k=None):
    """Folha com vários quadros do take (k quadros em 2 linhas; padrão 6 ou 8), convertidos pra SDR só pra IA enxergar; não vai pro vídeo.
    Devolve (jpg, [segundo de cada quadro])."""
    dur = duracao(video); k = (k or (6 if dur <= 15 else 8)) // 2 * 2; cols = k // 2
    tempos = [round(dur * (i + 0.5) / k, 1) for i in range(k)]
    if os.path.exists(saida): return saida, tempos
    hdr = sondar(video)[2] in ('arib-std-b67', 'smpte2084')
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if hdr else ''
    for t_ in (tm, ''):
        args = ['ffmpeg', '-v', 'error', '-y']
        for t in tempos: args += ['-ss', f'{t:.2f}', '-i', video]
        fc = ';'.join(f'[{i}:v]trim=end_frame=1,{t_}scale={largura}:-2,setsar=1[q{i}]' for i in range(k))
        fc += ';' + ''.join(f'[q{i}]' for i in range(cols)) + f'hstack={cols}[l1];' + ''.join(f'[q{i}]' for i in range(cols, k)) + f'hstack={cols}[l2];[l1][l2]vstack[o]'
        r = subprocess.run(args + ['-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-q:v', '4', saida], capture_output=True)
        if r.returncode == 0 and os.path.exists(saida): return saida, tempos
    j = quadro_jpg(video, saida.replace('.jpg', '_1.jpg'), 512)
    return j, ([round(dur / 2, 1)] if j else [])

def trecho_estavel(tremor, ini, dur_cena, dur_take, folga=3.0):
    """Se a cena escolhida pega segundos tremidos, procura até `folga` s pra frente ou pra trás um trecho firme do mesmo tamanho."""
    def pior(s):
        a, b = int(s), int(min(dur_take, s + dur_cena) - 1e-3)
        return max(tremor[a:b + 1] or [0.0])
    if not tremor or pior(ini) <= TREMOR_ALTO: return ini
    lim = max(0.0, dur_take - dur_cena - 0.05)
    perto = [c for c in (round(ini + d / 2, 2) for d in range(-int(folga * 2), int(folga * 2) + 1)) if 0 <= c <= lim]
    melhor = min(perto, key=lambda c: (pior(c), abs(c - ini))) if perto else ini
    if pior(melhor) > TREMOR_ALTO:                     # nada firme por perto: procura no take inteiro
        todos = [round(d / 2, 2) for d in range(int(lim * 2) + 1)]
        if todos: melhor = min(todos, key=lambda c: (pior(c) > TREMOR_ALTO, abs(c - ini), pior(c)))
    return melhor

def quadro_jpg(video, saida, largura=512):
    """Um quadro do meio do vídeo em JPEG (convertido pra SDR só pra IA enxergar a cena; não vai pro vídeo)."""
    if os.path.exists(saida): return saida
    t = duracao(video) / 2; hdr = sondar(video)[2] in ('arib-std-b67', 'smpte2084')
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if hdr else ''
    for f in ((tm + f'scale={largura}:-2'), f'scale={largura}:-2'):
        r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1', '-vf', f, '-q:v', '4', saida], capture_output=True)
        if r.returncode == 0 and os.path.exists(saida): return saida
    return None

BROLL_APLICADOS = 0
def aplicar_broll(base, saida, pl, tokens, dur, arquivos, altura, pasta, hdr, crf=14):
    """Cenas de ambiente cobrindo a imagem durante a locução (a voz continua). Tudo em HDR do original:
    recorte vertical + escala como os takes, sobreposto direto em 10 bits (sem conversão de cor, sem filtro)."""
    global BROLL_APLICADOS
    BROLL_APLICADOS = 0
    amb = pl.get('_broll_arquivos') or []
    OH = altura; OW = OH * 9 // 16
    transf_base = sondar(base)[2]; params, tags = x265(transf_base)
    nv = os.environ.get('BORA_INTERMEDIARIO') == 'nvenc'
    cache = os.path.join(pasta, f'_trechos_{altura}'); os.makedirs(cache, exist_ok=True)
    usados, ult_fim = [], -1.0
    for b in sorted(pl.get('broll') or [], key=lambda x: int(x['palavra_inicio'])):
        k = int(b['video']) - 1
        if not (0 <= k < len(amb)): continue
        arq = arquivos[amb[k]]
        if sondar(arq)[2] != transf_base: print('broll: cor diferente do vídeo (HDR x SDR), pulado', arq, flush=True); continue
        # só as palavras do trecho escolhido que ficaram no vídeo montado (os segmentos podem vir fora da ordem dos arquivos)
        sel = [t for t in tokens if int(b['palavra_inicio']) <= t['i'] <= int(b['palavra_fim'])]
        if not sel: print('broll: trecho escolhido não está no vídeo montado, pulado', b, flush=True); continue
        a = min(t['s'] for t in sel); z = max(t['e'] for t in sel)
        final = dur - z < 1.5 and dur - a <= 7.0             # cena que fecha o vídeo: vai até o último quadro, sem voltar pro rosto
        z = dur if final else min(max(z, a + 1.5), a + 4.5, dur)    # 1,5 a 4,5 s
        if a < ult_fim + 1.0 or z - a < 1.0: continue        # sem colar um B-roll no outro
        fa, fb = round(a * FPS), round(z * FPS); n = fb - fa
        dclip = duracao(arq); ini = max(0.0, min(float(b.get('inicio_s') or 0), dclip - n / FPS - 0.05))
        trem = (pl.get('_broll_tremor') or [])[k] if k < len(pl.get('_broll_tremor') or []) else None
        novo = trecho_estavel(trem, ini, n / FPS, dclip)
        if novo != ini: print(f'broll: trecho tremido em {ini:.1f} s, usando {novo:.1f} s', arq, flush=True); ini = novo
        if dclip < n / FPS: n = int(dclip * FPS) - 1
        if n < 20: continue
        W, H = sondar(arq)[:2]
        if W / H > 9 / 16: cw, ch = round(H * 9 / 16 / 2) * 2, H
        else: cw, ch = W, round(W * 16 / 9 / 2) * 2
        x, y = (W - cw) // 2, max(0, (H - ch) // 2)
        chave = os.path.join(cache, f'broll{amb[k]}_{ini:.2f}_{n}_{crf}{"n" if nv else "r"}.mp4')
        if not os.path.exists(chave):
            if nv:
                import codificadores; cod = codificadores.args_nvenc()
            else:
                cod = ['-c:v', 'libx265', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params]
            with pesado(altura):
                rc, msg, mb = rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{ini:.3f}', '-i', arq, '-an',
                                     '-vf', f'crop={cw}:{ch}:{x}:{y},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001', '-frames:v', str(n),
                                     *cod, *tags, chave + '.tmp.mp4'], 'b-roll')
            if oom(rc, msg): raise SemMemoria(f'memória insuficiente no B-roll ({mb} MB)')
            if rc: print('broll falhou:', msg, flush=True); continue
            os.replace(chave + '.tmp.mp4', chave)
        usados.append((chave, fa / FPS)); ult_fim = fa / FPS + n / FPS
    if not usados: return base
    grande = altura >= 1500                            # 4K: decodificadores e x265 enxutos (cada quadro 10 bits tem ~25 MB)
    args, fc, ult = ['ffmpeg', '-nostdin', '-v', 'error', '-y'] + (['-threads', '2'] if grande else []) + ['-i', base], [], '0:v'
    for j, (c, t0) in enumerate(usados, 1):
        args += (['-threads', '1'] if grande else []) + ['-itsoffset', f'{t0:.6f}', '-i', c]     # cena já no tempo certo: só é lida quando chega a vez
        fc.append(f'[{ult}][{j}:v]overlay=eof_action=pass:format=yuv420p10[v{j}]'); ult = f'v{j}'
    enx = ':frame-threads=1:pools=4:rc-lookahead=10:lookahead-slices=0' if grande else ''
    cod = (__import__('codificadores').args_nvenc() if nv else ['-c:v', 'libx265', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params + enx])
    with pesado(altura):
        rc, msg, mb = rodar(args + ['-filter_complex', ';'.join(fc), '-map', f'[{ult}]', '-map', '0:a', '-c:a', 'copy', *cod, *tags,
                                    '-tag:v', 'hvc1', saida], 'b-roll (juntar)')
    if oom(rc, msg): raise SemMemoria(f'memória insuficiente ao juntar o B-roll ({mb} MB)')
    if rc: raise RuntimeError('b-roll: ' + (msg or f'código {rc}')[:150])
    BROLL_APLICADOS = len(usados)
    return saida

def sondar(video):
    o = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,color_transfer,color_primaries:stream_side_data', '-of', 'json', video], capture_output=True, text=True).stdout)
    st = o['streams'][0]; w, h = st['width'], st['height']
    rot = abs(int(float(next((x.get('rotation') for x in st.get('side_data_list') or [] if 'rotation' in x), 0) or 0)))
    if rot in (90, 270): w, h = h, w
    return w, h, st.get('color_transfer') or '', st.get('color_primaries') or ''

def x265(transf):
    if transf in ('arib-std-b67', 'smpte2084'):
        return (f'colorprim=bt2020:transfer={transf}:colormatrix=bt2020nc:range=limited:no-sao=1:no-strong-intra-smoothing=1',
                ['-color_primaries', 'bt2020', '-color_trc', transf, '-colorspace', 'bt2020nc'])
    return ('colorprim=bt709:transfer=bt709:colormatrix=bt709:range=limited:no-sao=1:no-strong-intra-smoothing=1',
            ['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709'])

# SDR (BT.709) -> HLG (BT.2020), o mesmo caminho dos textos (hdr_texto.py): a capa final tem a mesma cor e o mesmo branco forte (BRILHO_TEXTO)
_M_HLG = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]], np.float32)
def _hlg(E):
    E = np.clip(E, 0, 1)
    return np.where(E <= 1 / 12, np.sqrt(3 * E), 0.17883277 * np.log(np.maximum(12 * E - 0.28466892, 1e-6)) + 0.55991073)

def capa_clip(imagem, saida, OW, OH, dur_s, hdr, crf, params, tags):
    """Clipe (sem áudio) da capa final por dur_s. Cartão horizontal (CRM, RQE, redes) vira o cartão animado em 9:16 (cartao_animado);
    imagem em pé preenche a tela (corta o excesso) com fade de entrada. HDR: SDR->HLG como os textos."""
    from PIL import Image
    im = Image.open(imagem)
    if im.width / im.height > 2: return _capa_animada(imagem, saida, OW, OH, dur_s, hdr, crf, params, tags)
    im = im.convert('RGB'); r = max(OW / im.width, OH / im.height)
    im = im.resize((max(OW, round(im.width * r)), max(OH, round(im.height * r))), Image.LANCZOS)
    x0, y0 = (im.width - OW) // 2, (im.height - OH) // 2; im = im.crop((x0, y0, x0 + OW, y0 + OH))
    a = np.asarray(im, np.float32) / 255; raw = os.path.splitext(saida)[0] + '.raw'; nq = max(2, round(dur_s * FPS))
    if hdr:
        sig = _hlg((a ** 2.4) @ _M_HLG.T * float(os.environ.get('BRILHO_TEXTO', '0.62'))); open(raw, 'wb').write((sig * 65535).astype('<u2').tobytes()); pix, mat = 'rgb48le', 'bt2020'
    else:
        open(raw, 'wb').write((a * 255).astype(np.uint8).tobytes()); pix, mat = 'rgb24', 'bt709'
    try:
        sh(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', pix, '-s', f'{OW}x{OH}', '-framerate', '30000/1001', '-i', raw,
            '-vf', f'loop=loop={nq - 1}:size=1:start=0,scale=out_color_matrix={mat}:out_range=tv,format=yuv420p10le,fade=t=in:st=0:d=0.35,setsar=1,fps=30000/1001',
            '-frames:v', str(nq), '-c:v', 'libx265', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params, *tags, saida])
    finally:
        if os.path.exists(raw): os.remove(raw)

def _capa_animada(imagem, saida, OW, OH, dur_s, hdr, crf, params, tags):
    import cartao_animado
    pix, mat = ('rgb48le', 'bt2020') if hdr else ('rgb24', 'bt709'); nq = max(2, round(dur_s * FPS))
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', pix, '-s', f'{OW}x{OH}', '-framerate', '30000/1001', '-i', '-',
                          '-vf', f'scale=out_color_matrix={mat}:out_range=tv,format=yuv420p10le,fade=t=in:st=0:d=0.35,setsar=1,fps=30000/1001',
                          '-frames:v', str(nq), '-c:v', 'libx265', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params, *tags, saida],
                         stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for a in cartao_animado.quadros(imagem, OW, OH, dur_s, FPS):
            if hdr: a = (_hlg((a ** 2.4) @ _M_HLG.T * float(os.environ.get('BRILHO_TEXTO', '0.62'))) * 65535).astype('<u2')
            else: a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
            p.stdin.write(a.tobytes())
        p.stdin.close(); err = p.stderr.read().decode(); p.wait()
    except BrokenPipeError: err = p.stderr.read().decode(); p.wait()
    if p.returncode: raise RuntimeError('cartão animado: ' + err[-200:])

def render_base(pcs, arquivos, saida, altura=854, crf=14, progresso=None, sfx=None, capa=None, rostos=None):
    """Monta o vídeo base (sem textos). Cada peça vira um arquivo; depois junta sem recodificar."""
    OH = altura; OW = OH * 9 // 16
    tmp = tempfile.mkdtemp(prefix='base_', dir=os.path.dirname(os.path.abspath(saida)))
    cache = os.path.join(os.path.dirname(os.path.abspath(saida)), f'_trechos_{altura}')   # trechos já montados (reaproveitados nos ajustes)
    os.makedirs(cache, exist_ok=True)
    info = {i: sondar(a) for i, a in enumerate(arquivos)}
    transf = info[0][2]; params, tags = x265(transf)
    jobs, a_in, a_fc = [], [], []
    for n, (ai, fa, fb, quadro) in enumerate(pcs):
        W, H = info[ai][0], info[ai][1]; z, fy = ENQ.get(quadro, ENQ['medio'])
        tin, dur = fa / FPS, (fb - fa) / FPS
        import enquadramento                            # com rostos medidos: zoom que não corta ninguém, respiro em cima, centrado no grupo
        cx = enquadramento.caixas_do_trecho((rostos or {}).get(str(ai)) or [], tin, tin + dur)
        cw, ch, x, y = enquadramento.recorte(W, H, z, fy, cx)
        # intermediário: rápido e quase sem perda (a entrega é recodificada depois). NVENC só se a máquina validou (codificadores.py)
        nv = os.environ.get('BORA_INTERMEDIARIO') == 'nvenc'
        chave = os.path.join(cache, f'a{ai}_{fa}_{fb}_{quadro}_{cw}x{ch}+{x}+{y}_{crf}{"n" if nv else "r"}.mp4')
        if nv:
            import codificadores; cod = codificadores.args_nvenc()
        else:
            cod = ['-c:v', 'libx265', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params]
        jobs.append((chave, ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', arquivos[ai], '-an',
                     '-vf', f'crop={cw}:{ch}:{x}:{y},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001', '-frames:v', str(fb - fa),
                     *cod, *tags, chave + '.tmp.mp4']))
        a_in += ['-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', arquivos[ai]]
        a_fc.append(f"[{n}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.010,afade=t=out:st={max(dur - 0.012, 0):.4f}:d=0.012[a{n}]")
    feitos = [0]
    def roda(job):
        chave, cmd = job; rc = 0
        if not os.path.exists(chave):                  # só codifica o trecho que ainda não existe (retomada aproveita os prontos)
            with pesado(altura):
                rc, _, _ = rodar(cmd, 'trecho ' + os.path.basename(chave))
            if rc == 0: os.replace(chave + '.tmp.mp4', chave)
        feitos[0] += 1
        if progresso: progresso(feitos[0] / len(jobs))
        return rc
    with ThreadPoolExecutor(4 if altura < 1500 else 1) as ex:
        falhas = [j for j, rc in zip(jobs, ex.map(roda, jobs)) if rc]
    for k, (chave, cmd) in enumerate(falhas, 1):       # uma nova tentativa, sozinha; se faltar memória de novo, para
        if progresso: progresso(1.0, f'Refazendo um trecho que falhou ({k} de {len(falhas)})')
        with pesado(altura):
            rc, msg, mb = rodar(cmd, 'trecho ' + os.path.basename(chave) + ' (2ª tentativa)')
        if rc:
            if oom(rc): raise SemMemoria(f'memória insuficiente no trecho {k} ({mb} MB, código {rc})')
            raise RuntimeError('falha ao codificar um trecho: ' + (msg or f'código {rc}')[:120])
        os.replace(chave + '.tmp.mp4', chave)
    partes = [c for c, _ in jobs]
    if capa:                                           # capa final (ex.: CRM e RQE): imagem em tela cheia depois do último trecho
        import hashlib
        cartao = os.path.join(cache, f"capa_{hashlib.md5(open(capa['imagem'], 'rb').read()).hexdigest()[:8]}_{int(capa['dur'] * 10)}_{crf}.mp4")
        if not os.path.exists(cartao):
            capa_clip(capa['imagem'], cartao + '.tmp.mp4', OW, OH, capa['dur'], transf in ('arib-std-b67', 'smpte2084'), crf, params, tags); os.replace(cartao + '.tmp.mp4', cartao)
        partes.append(cartao)
    open(os.path.join(tmp, 'lista.txt'), 'w').write(''.join(f"file '{c}'\n" for c in partes))
    vid, aud = os.path.join(tmp, 'video.mp4'), os.path.join(tmp, 'audio.m4a')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(tmp, 'lista.txt'), '-c', 'copy', vid])
    n = len(jobs)
    # Áudio fiel ao gravado (o microfone já limpa o ruído): sem redução de ruído, EQ ou compressor.
    # Só junta os trechos, tira o que está abaixo de 60 Hz e acerta o volume em -14 LUFS com ganho FIXO (medido antes).
    bruto = os.path.join(tmp, 'audio.wav')
    afc = ';'.join(a_fc) + ';' + ''.join(f'[a{i}]' for i in range(n)) + f'concat=n={n}:v=0:a=1,highpass=f=60' + (f",apad=pad_dur={capa['dur']:.3f}" if capa else '') + '[ao]'
    sh(['ffmpeg', '-v', 'error', '-y'] + a_in + ['-filter_complex', afc, '-map', '[ao]', '-c:a', 'pcm_s24le', bruto])
    med = subprocess.run(['ffmpeg', '-nostdin', '-i', bruto, '-af', 'loudnorm=I=-14:TP=-1.5:print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = json.loads(med[med.rindex('{'):med.rindex('}') + 1])
    ganho = -14.0 - float(m['input_i'])                       # ganho fixo: a dinâmica da fala fica igual à gravada
    # limitador só nos picos raros que passariam de -1,5 dBTP (não comprime a voz)
    ln = f"volume={ganho:.2f}dB,alimiter=limit=0.84:attack=5:release=50:level=disabled,aresample=48000"
    if sfx: misturar_sfx(bruto, ganho, sfx, aud)               # efeitos sonoros (opcional): faixa separada, a voz já está no ganho final
    else: sh(['ffmpeg', '-v', 'error', '-y', '-i', bruto, '-af', ln, '-c:a', 'aac', '-b:a', '256k', aud])
    sh(['ffmpeg', '-v', 'error', '-y', '-i', vid, '-i', aud, '-map', '0:v', '-map', '1:a', '-c', 'copy', '-tag:v', 'hvc1', '-movflags', '+faststart', saida])
    subprocess.run(['rm', '-rf', tmp])
    return transf in ('arib-std-b67', 'smpte2084')

def eventos_sfx(pcs, destaques_t, dur):
    """Momentos dos efeitos no vídeo montado: [(segundo, 'whoosh'|'pop')].
    Whoosh só nas trocas de história (outro take, outro enquadramento ou salto de mais de 2 s no bruto), não nos cortes de pausa.
    Pop no começo de cada destaque. Espaçados (whoosh 2,5 s, pop 0,8 s), longe das bordas do vídeo, no máximo 8 whooshes."""
    ev, t, ult = [], 0.0, None
    for ai, fa, fb, quadro in pcs:
        if ult and (ai != ult[0] or quadro != ult[3] or (fa - ult[2]) / FPS > 2.0): ev.append((round(t, 3), 'whoosh'))
        t += (fb - fa) / FPS; ult = (ai, fa, fb, quadro)
    ws, ult_w = [], -99.0
    for t in sorted(x for x, _ in ev):
        if 0.3 <= t <= dur - 0.3 and t - ult_w >= 2.5 and len(ws) < 8: ws.append(t); ult_w = t
    ps, ult_p = [], -99.0
    for t in sorted(destaques_t):
        if 0.3 <= t <= dur - 0.3 and t - ult_p >= 0.8 and all(abs(t - w) > 0.35 for w in ws): ps.append(round(t, 3)); ult_p = t
    return sorted([(w, 'whoosh') for w in ws] + [(p, 'pop') for p in ps])

def misturar_sfx(bruto, ganho, sfx, saida, codec=('-c:a', 'aac', '-b:a', '256k')):
    """AAC final = voz (ganho fixo, como sempre) + efeitos em tempos marcados. sfx: [(inicio_s, arquivo_wav)].
    Só soma: a voz não passa por EQ nem compressor; o limitador de picos é o mesmo de antes."""
    canais = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels', '-of', 'csv=p=0', bruto],
                            capture_output=True, text=True).stdout.strip()
    lay = 'mono' if canais == '1' else 'stereo'
    args, fc = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', bruto], [f'[0:a]volume={ganho:.2f}dB,aresample=48000[v]']
    for j, (t0, arq) in enumerate(sfx, 1):
        args += ['-i', arq]
        fc.append(f'[{j}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts={lay},adelay={max(1, int(round(t0 * 1000)))}:all=1[s{j}]')
    fc.append('[v]' + ''.join(f'[s{j}]' for j in range(1, len(sfx) + 1)) + f'amix=inputs={len(sfx) + 1}:duration=first:normalize=0:dropout_transition=0[m]')
    fc.append('[m]alimiter=limit=0.84:attack=5:release=50:level=disabled[o]')
    sh(args + ['-filter_complex', ';'.join(fc), '-map', '[o]', *codec, saida])

def _textos_em_pedacos(base, ass, saida, crf, partes, here, prog):
    """4K: divide o vídeo em pedaços de quadros, aplica os textos em paralelo (a conversão HDR dos textos usa 1 núcleo por
    processo) e junta sem recodificar; o áudio sai inteiro do vídeo base. Mesma imagem, mesmas cores, mesmos quadros."""
    total = quadros(base); tam = -(-total // partes); ped = []
    for k in range(partes):
        ini, n = k * tam, min(tam, total - k * tam)
        if n > 0: ped.append((k, ini, n, f'{saida}.p{k}.mp4', f'{saida}.p{k}.progresso'))
    def um(p):
        k, ini, n, out, arq = p
        return rodar(['python3', os.path.join(here, 'hdr_texto.py'), base, ass, out, str(crf)], f'textos pedaço {k + 1}/{len(ped)}',
                     env={**os.environ, 'BORA_PRESET': 'medium', 'BORA_PROGRESSO': arq, 'BORA_INICIO_Q': str(ini), 'BORA_N_Q': str(n)})
    parar = threading.Event()
    if prog: threading.Thread(target=_vigiar, args=([p[4] for p in ped], total, prog, parar), daemon=True).start()
    with ThreadPoolExecutor(len(ped)) as ex:
        res = list(ex.map(um, ped))
    parar.set()
    ruim = next((r for r in res if r[0]), None)
    if not ruim:
        lista = saida + '.lista.txt'; open(lista, 'w').write(''.join(f"file '{p[3]}'\n" for p in ped))
        r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-i', base, '-map', '0:v', '-map', '1:a',
                            '-c', 'copy', '-tag:v', 'hvc1', '-movflags', '+faststart', saida], capture_output=True, text=True)
        ruim = (r.returncode, (r.stderr.strip().splitlines() or [''])[-1], 0) if r.returncode else None
        if not ruim and quadros(saida) != total: ruim = (1, f'juntar os pedaços deu {quadros(saida)} quadros, esperado {total}', 0)
        os.remove(lista)
    for p in ped:
        for f in (p[3], p[4]):
            if os.path.exists(f): os.remove(f)
    return ruim or (0, '', max(r[2] for r in res))

def aplicar_textos(base, ass, saida, hdr, crf=24, here=os.path.dirname(os.path.abspath(__file__)), prog=None):
    """Textos por cima sem mexer na imagem: HDR usa a conversão SDR->HLG com branco forte; SDR queima direto."""
    if hdr:
        H = int((re.findall(r'\d+', subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height', '-of', 'csv=p=0', base], capture_output=True, text=True).stdout) or [0])[0])
        partes = max(1, int(os.environ.get('BORA_PARTES_4K', '1'))) if H >= 1500 else 1
        with pesado(H):
            if partes == 1:
                arq = saida + '.progresso'
                rc, msg, mb = rodar(['python3', os.path.join(here, 'hdr_texto.py'), base, ass, saida, str(crf)], 'textos ' + os.path.basename(saida),
                                    env={**os.environ, 'BORA_PRESET': 'veryfast' if H < 1500 else 'medium', 'BORA_PROGRESSO': arq},
                                    prog=(arq, quadros(base), prog) if prog else None)
                if os.path.exists(arq): os.remove(arq)
            else:
                rc, msg, mb = _textos_em_pedacos(base, ass, saida, crf, partes, here, prog)
        if oom(rc, msg): raise SemMemoria(f'memória insuficiente ao aplicar os textos ({mb} MB)')
        if rc: raise RuntimeError('textos: ' + (msg or f'código {rc}')[:150])
    else:
        params, tags = x265('bt709')
        sh(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', base, '-vf', f"subtitles={ass}:fontsdir={os.path.join(here, 'fonts')}",
            '-c:v', 'libx265', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params, *tags, '-tag:v', 'hvc1',
            '-c:a', 'copy', '-movflags', '+faststart', saida])
