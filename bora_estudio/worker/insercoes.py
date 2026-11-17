"""Inserções (imagens e vídeos anexados) por cima do vídeo, sem tocar na imagem original:
- tela_cheia: cobre a tela (imagem com zoom lento ou vídeo), fade de entrada e saída; a voz continua por baixo
- flutuando: imagem menor ao lado da pessoa, com sombra, leve desfoque e flutuação suave
As camadas são sequências PNG com transparência; no HDR entram pela mesma conversão SDR->HLG dos textos."""
import math, os, shutil, subprocess
from PIL import Image, ImageFilter

FPS = 30000 / 1001
APLICADAS = 0

def _tempo(tokens, i0, i1, fim):
    a = next((t['s'] for t in tokens if t['i'] >= i0), None)
    b = max((t['e'] for t in tokens if t['i'] <= i1), default=None)
    if a is None: return None
    b = max(b if b is not None else a + 1.5, a + 1.2)
    return max(0.0, a - 0.15), min(fim, b + 0.04)    # termina junto da última palavra (não invade o corte seguinte)

def _cover(im, W, H, z=1.0):
    r = max(W / im.width, H / im.height) * z
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))

def _quadros_video(arq, pasta, W, H, n):
    os.makedirs(pasta, exist_ok=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-stream_loop', '-1', '-i', arq, '-frames:v', str(n),
                    '-vf', f'fps=30000/1001,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=rgba',
                    os.path.join(pasta, 'v%04d.png')], check=True)
    return [os.path.join(pasta, f'v{k:04d}.png') for k in range(1, n + 1)]

_sessao = None
_cache_masc = {}
def mascaras_pessoa(base, t0, n, W, H, hdr):
    """Recorte da pessoa nos quadros [t0, t0+n): 1 = pessoa (fica na frente da arte). Modelo u2net_human_seg (rembg).
    Cada quadro é recortado uma vez só e reaproveitado por todos os anexos do mesmo vídeo."""
    q0 = round(t0 * FPS); faltam = [q for q in range(q0, q0 + n) if (base, W, q) not in _cache_masc]
    if faltam:
        a, b = faltam[0], faltam[-1] + 1
        for i, m in enumerate(_recortar(base, a / FPS, b - a, W, H, hdr)): _cache_masc[(base, W, a + i)] = m
    return [_cache_masc.get((base, W, q)) or Image.new('L', (W, H), 0) for q in range(q0, q0 + n)]

def _recortar(base, t0, n, W, H, hdr):
    global _sessao
    from rembg import new_session, remove
    import numpy as np, tempfile
    if _sessao is None: _sessao = new_session('u2net_human_seg')
    d = tempfile.mkdtemp(prefix='mask_')
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if hdr else ''
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t0:.3f}', '-i', base, '-frames:v', str(n),
                    '-vf', tm + 'scale=320:-2', os.path.join(d, 'f%04d.png')], check=True)
    out, ult = [], None
    for k in range(1, n + 1):
        f = os.path.join(d, f'f{k:04d}.png')
        if k % 2 == 1 or ult is None:                     # a cada 2 quadros (movimento de fala é lento)
            if os.path.exists(f):
                m = remove(Image.open(f).convert('RGB'), session=_sessao, only_mask=True)
                m = m.point(lambda v: 0 if v < 110 else (255 if v > 170 else int((v - 110) * 4.25)))   # borda mais justa
                ult = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1)).resize((W, H), Image.BILINEAR)
            else:
                ult = ult or Image.new('L', (W, H), 0)
        out.append(ult)
    shutil.rmtree(d, ignore_errors=True)
    return out

def camada(ins, anexo, t0, t1, W, H, pasta, lado, base=None, hdr=True):
    n = max(2, round((t1 - t0) * FPS)); f_in = f_out = min(8, n // 3)
    if os.path.exists(pasta): shutil.rmtree(pasta)
    os.makedirs(pasta)
    video = anexo['tipo'] == 'video'
    modo = 'tela_cheia' if video else ins.get('modo', 'tela_cheia')
    if video: fontes = _quadros_video(anexo['caminho'], pasta + '_v', W, H, n)
    else: img = Image.open(anexo['caminho']).convert('RGBA')
    quadro = (not video) and img.getchannel('A').getextrema()[0] < 250 and 0.5 <= img.width / img.height <= 0.62
    if quadro:                                   # PNG transparente 9:16 já composto: ocupa o quadro inteiro
        modo = 'quadro'; img = img.resize((W, H), Image.LANCZOS)
        try: masks = mascaras_pessoa(base, t0, n, W, H, hdr) if base else None
        except Exception as e: print('máscara:', e, flush=True); masks = None
    if modo == 'flutuando':
        larg = int(W * 0.40); img = img.resize((larg, max(1, int(img.height * larg / img.width))), Image.LANCZOS)
        if img.height > H * 0.38: img = img.resize((int(img.width * H * 0.38 / img.height), int(H * 0.38)), Image.LANCZOS)
        pad = int(W * 0.05); base = Image.new('RGBA', (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
        sombra = Image.new('RGBA', base.size, (0, 0, 0, 0)); sombra.paste((0, 0, 0, 150), (pad + 8, pad + 14), img.getchannel('A'))
        base.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(W * 0.02)))
        base.alpha_composite(img.filter(ImageFilter.GaussianBlur(max(1, W * 0.0025))), (pad, pad))
        cx = W * (0.80 if lado else 0.20); cy = H * 0.36
    for k in range(n):
        a = min(1.0, (k + 1) / max(f_in, 1), (n - k) / max(f_out, 1))
        if modo == 'quadro':
            q = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ent = 1 - min(1, (k + 1) / max(f_in, 1))
            q.alpha_composite(img, (0, int(math.sin(k / FPS * 1.4) * H * 0.006 + ent * H * 0.02)))
            if masks:                                 # a pessoa passa na frente da arte
                from PIL import ImageChops
                q.putalpha(ImageChops.multiply(q.getchannel('A'), ImageChops.invert(masks[k])))
        elif modo == 'flutuando':
            q = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            dy = math.sin(k / FPS * 1.6) * H * 0.008; dx = (1 - min(1, (k + 1) / max(f_in, 1))) * W * 0.06 * (1 if lado else -1)
            q.alpha_composite(base, (int(cx - base.width / 2 + dx), int(cy - base.height / 2 + dy)))
        else:
            q = Image.open(fontes[k]).convert('RGBA') if video else _cover(img, W, H, 1.0 + 0.06 * k / n)
        if a < 1: q.putalpha(q.getchannel('A').point(lambda v: int(v * a)))
        q.save(os.path.join(pasta, f'l{k:04d}.png'), compress_level=1)
    if video: shutil.rmtree(pasta + '_v', ignore_errors=True)
    return pasta

def aplicar(base, saida, pl, tokens, dur, anexos, pasta, hdr, here=os.path.dirname(os.path.abspath(__file__)), prog=None):
    """Devolve o vídeo com as inserções; se não houver nenhuma válida, devolve a base."""
    W, H = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                    '-of', 'csv=p=0:s=x', base], capture_output=True, text=True).stdout.strip().split('\n')[0].strip(',').split('x')[:2])
    cams = []
    for j, ins in enumerate(pl.get('insercoes') or []):
        k = int(ins.get('anexo', 0)) - 1
        if not (0 <= k < len(anexos)) or not os.path.exists(anexos[k]['caminho']): continue
        t = _tempo(tokens, int(ins['palavra_inicio']), int(ins['palavra_fim']), dur)
        if not t: continue
        cams.append((camada(ins, anexos[k], t[0], t[1], W, H, os.path.join(pasta, f'_ins{j}_{H}'), j % 2 == 0, base, hdr), t[0]))
    _cache_masc.clear()
    global APLICADAS
    APLICADAS = len(cams)
    if not cams: return base
    if hdr:
        env = {**os.environ, 'BORA_PRESET': 'veryfast', 'BORA_HDR_CODEC': os.environ.get('BORA_INTERMEDIARIO', 'x265'), 'CAMADAS': ','.join(f'{p}:{t0:.3f}' for p, t0 in cams), 'BRILHO_TEXTO': '0.40'}
        import montagem
        with montagem.pesado(H):
            arq = saida + '.progresso'; env['BORA_PROGRESSO'] = arq
            rc, msg, mb = montagem.rodar(['python3', os.path.join(here, 'hdr_texto.py'), base, '-', saida, '14'], 'inserções', env=env,
                                         prog=(arq, montagem.quadros(base), prog) if prog else None)
            if os.path.exists(arq): os.remove(arq)
        if montagem.oom(rc, msg): raise montagem.SemMemoria(f'memória insuficiente ao encaixar os anexos ({mb} MB)')
        if rc: raise RuntimeError('inserções: ' + (msg or f'código {rc}')[:150])
    else:
        args = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', base]; fc, ult = [], '0:v'
        for j, (p, t0) in enumerate(cams, 1):
            args += ['-framerate', '30000/1001', '-i', os.path.join(p, 'l%04d.png')]
            fc.append(f'[{j}:v]setpts=PTS+{t0}/TB[c{j}];[{ult}][c{j}]overlay=eof_action=pass[o{j}]'); ult = f'o{j}'
        subprocess.run(args + ['-filter_complex', ';'.join(fc), '-map', f'[{ult}]', '-map', '0:a', '-c:v', 'libx265', '-crf', '14',
                               '-pix_fmt', 'yuv420p10le', '-tag:v', 'hvc1', '-c:a', 'copy', saida], check=True)
    for p, _ in cams: shutil.rmtree(p, ignore_errors=True)
    return saida
