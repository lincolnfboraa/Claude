"""Transcrição, cortes e montagem do vídeo a partir dos ORIGINAIS, sem tratamento de imagem.
- transcrever(): faster-whisper com tempo por palavra (cache em JSON)
- pecas(): trechos escolhidos pelo plano, menos as pausas longas (nunca dentro de uma palavra)
- render_base(): recorte geométrico + escala, HDR continua HDR (HEVC 10 bits, mesmas primárias/transferência)
  e áudio fiel ao gravado (só volume em -14 LUFS com ganho fixo)."""
import json, os, subprocess, wave, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np

FPS = 30000 / 1001
ENQ = {'aberto': (1.18, 0.30), 'medio': (1.32, 0.28), 'fechado': (1.48, 0.26)}   # zoom, posição do rosto (aprovados na Fabiola)
PAUSA = {'limiar_db': -45, 'min_s': 0.30, 'mantem_s': 0.10, 'borda_s': 0.18}
_modelo = None

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

def transcrever(video, cache):
    """Palavras com tempo (segundos do arquivo original)."""
    if os.path.exists(cache): return json.load(open(cache))
    global _modelo
    from faster_whisper import WhisperModel
    if _modelo is None:
        _modelo = WhisperModel(os.environ.get('BORA_WHISPER', 'medium'), device='cpu', compute_type='int8', cpu_threads=6)
    wav = wav16(video, cache.replace('.json', '.wav'))
    a = np.frombuffer(wave.open(wav).readframes(10 ** 10), dtype=np.int16).astype(np.float32) / 32768
    seg, _ = _modelo.transcribe(a, language='pt', word_timestamps=True, beam_size=1, vad_filter=True, condition_on_previous_text=False)
    pal = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in seg for w in s.words if w.word.strip()]
    json.dump(pal, open(cache, 'w'), ensure_ascii=False)
    return pal

def envelope(wav, hop=0.02):
    a = np.frombuffer(wave.open(wav).readframes(10 ** 10), dtype=np.int16).astype(np.float32) / 32768
    n = int(hop * 16000); k = len(a) // n
    return 20 * np.log10(np.sqrt((a[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9)

def tirar_pausas(a, b, env, palavras, hop=0.02):
    """[a,b] do original -> lista de trechos mantidos, sem pausas longas; protege palavras (+120 ms no fim)."""
    LIM, MIN, KEEP, BORDA = PAUSA['limiar_db'], PAUSA['min_s'], PAUSA['mantem_s'], PAUSA['borda_s']
    i0, i1 = int(a / hop), int(b / hop); q = env[i0:i1] < LIM
    for w in palavras:                                   # nunca é pausa onde há palavra
        if w['e'] < a or w['s'] > b: continue
        j0, j1 = max(int((w['s'] - 0.04) / hop) - i0, 0), min(int((w['e'] + 0.12) / hop) - i0 + 1, len(q))
        q[j0:j1] = False
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
        a = max(0.0, pw[k0]['s'] - 0.06); b = pw[k1]['e'] + 0.18
        if ai not in envs: envs[ai] = envelope(wav16(arquivos[ai], os.path.join(pasta, f'audio_{ai + 1:02d}.wav')))
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

def render_base(pcs, arquivos, saida, altura=854, crf=14, progresso=None):
    """Monta o vídeo base (sem textos). Cada peça vira um arquivo; depois junta sem recodificar."""
    OH = altura; OW = OH * 9 // 16
    tmp = tempfile.mkdtemp(prefix='base_', dir=os.path.dirname(os.path.abspath(saida)))
    info = {i: sondar(a) for i, a in enumerate(arquivos)}
    transf = info[0][2]; params, tags = x265(transf)
    jobs, a_in, a_fc = [], [], []
    for n, (ai, fa, fb, quadro) in enumerate(pcs):
        W, H = info[ai][0], info[ai][1]; z, fy = ENQ.get(quadro, ENQ['medio'])
        if W / H > 9 / 16: cw0, ch0 = H * 9 / 16, H        # original horizontal: recorte vertical central
        else: cw0, ch0 = W, W * 16 / 9
        cw, ch = round(cw0 / z / 2) * 2, round(ch0 / z / 2) * 2
        x = int(min(max(0.5 * W - cw / 2, 0), W - cw)); y = int(min(max(0.40 * H - fy * ch, 0), H - ch))
        tin, dur = fa / FPS, (fb - fa) / FPS
        jobs.append(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', arquivos[ai], '-an',
                     '-vf', f'crop={cw}:{ch}:{x}:{y},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001', '-frames:v', str(fb - fa),
                     '-c:v', 'libx265', '-preset', 'medium', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params, *tags,
                     os.path.join(tmp, f'p{n:03d}.mp4')])
        a_in += ['-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', arquivos[ai]]
        a_fc.append(f"[{n}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.010,afade=t=out:st={max(dur - 0.012, 0):.4f}:d=0.012[a{n}]")
    feitos = [0]
    def roda(cmd):
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        feitos[0] += 1
        if progresso: progresso(feitos[0] / len(jobs))
        return r.returncode
    with ThreadPoolExecutor(3) as ex:
        if any(ex.map(roda, jobs)): raise RuntimeError('falha ao codificar um trecho')
    open(os.path.join(tmp, 'lista.txt'), 'w').write(''.join(f"file 'p{i:03d}.mp4'\n" for i in range(len(jobs))))
    vid, aud = os.path.join(tmp, 'video.mp4'), os.path.join(tmp, 'audio.m4a')
    sh(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(tmp, 'lista.txt'), '-c', 'copy', vid])
    n = len(jobs)
    # Áudio fiel ao gravado (o microfone já limpa o ruído): sem redução de ruído, EQ ou compressor.
    # Só junta os trechos, tira o que está abaixo de 60 Hz e acerta o volume em -14 LUFS com ganho FIXO (medido antes).
    bruto = os.path.join(tmp, 'audio.wav')
    afc = ';'.join(a_fc) + ';' + ''.join(f'[a{i}]' for i in range(n)) + f'concat=n={n}:v=0:a=1,highpass=f=60[ao]'
    sh(['ffmpeg', '-v', 'error', '-y'] + a_in + ['-filter_complex', afc, '-map', '[ao]', '-c:a', 'pcm_s24le', bruto])
    med = subprocess.run(['ffmpeg', '-nostdin', '-i', bruto, '-af', 'loudnorm=I=-14:TP=-1.5:print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = json.loads(med[med.rindex('{'):med.rindex('}') + 1])
    ganho = -14.0 - float(m['input_i'])                       # ganho fixo: a dinâmica da fala fica igual à gravada
    # limitador só nos picos raros que passariam de -1,5 dBTP (não comprime a voz)
    ln = f"volume={ganho:.2f}dB,alimiter=limit=0.84:attack=5:release=50:level=disabled,aresample=48000"
    sh(['ffmpeg', '-v', 'error', '-y', '-i', bruto, '-af', ln, '-c:a', 'aac', '-b:a', '256k', aud])
    sh(['ffmpeg', '-v', 'error', '-y', '-i', vid, '-i', aud, '-map', '0:v', '-map', '1:a', '-c', 'copy', '-tag:v', 'hvc1', '-movflags', '+faststart', saida])
    subprocess.run(['rm', '-rf', tmp])
    return transf in ('arib-std-b67', 'smpte2084')

def aplicar_textos(base, ass, saida, hdr, crf=24, here=os.path.dirname(os.path.abspath(__file__))):
    """Textos por cima sem mexer na imagem: HDR usa a conversão SDR->HLG com branco forte; SDR queima direto."""
    if hdr:
        sh(['python3', os.path.join(here, 'hdr_texto.py'), base, ass, saida, str(crf)])
    else:
        params, tags = x265('bt709')
        sh(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', base, '-vf', f"subtitles={ass}:fontsdir={os.path.join(here, 'fonts')}",
            '-c:v', 'libx265', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', params, *tags, '-tag:v', 'hvc1',
            '-c:a', 'copy', '-movflags', '+faststart', saida])
