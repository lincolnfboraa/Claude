"""Diagnóstico de enquadramento dos takes de fala: quantas pessoas aparecem e onde (rostos por OpenCV), com uma folha de quadros com as caixas desenhadas.
FASE 1 (só mede e mostra, não muda nenhum corte): o resultado vai pra original_meta.enquadramento e a folha pro bucket previas (diag_enquadramento.jpg).
Nunca derruba a edição: sem OpenCV, sem quadros ou qualquer erro, devolve None.
"""
import json, os, subprocess, sys, tempfile
import numpy as np

ULTIMO_ERRO = ['']
LIB = os.path.join(os.environ.get('BORA_TRABALHO', '/trabalho'), '_pylib')
N_QUADROS = 6

def _cv2():
    """OpenCV que funciona de verdade (com CascadeClassifier). Um 'cv2' quebrado no caminho (pasta solta, instalação pela metade) é ignorado
    e o OpenCV é instalado de novo no volume de trabalho."""
    import importlib, shutil as _sh
    def bom():
        sys.modules.pop('cv2', None); importlib.invalidate_caches()
        try:
            import cv2
            if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'): return cv2
            ULTIMO_ERRO[0] = 'cv2 sem CascadeClassifier em ' + str(getattr(cv2, '__file__', None) or list(getattr(cv2, '__path__', [])))[:120]
        except Exception as e: ULTIMO_ERRO[0] = 'cv2: ' + str(e)[:120]
        return None
    c = bom()
    if c: return c
    if LIB in sys.path: sys.path.remove(LIB)
    sys.path.insert(0, LIB); c = bom()
    if c: return c
    try:
        _sh.rmtree(os.path.join(LIB, 'cv2'), ignore_errors=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-cache-dir', '--upgrade', '--target', LIB, 'opencv-python-headless==4.10.0.84'], capture_output=True, timeout=600, check=True)
    except Exception as e:
        ULTIMO_ERRO[0] = 'instalação do OpenCV falhou: ' + str(e)[:100]; print('enquadramento:', ULTIMO_ERRO[0], flush=True); return None
    c = bom()
    if not c: print('enquadramento: OpenCV continua sem funcionar:', ULTIMO_ERRO[0], flush=True)
    return c

def _duracao(v):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', v], capture_output=True, text=True).stdout.strip() or 0)


def _ler_png(cv2, arq):
    img = cv2.imread(arq) if os.path.exists(arq) else None
    return img

def _quadro(video, t, largura=540):
    """Quadro em SDR (tone map só pra detectar), largura fixa, via PNG temporário. Devolve array BGR ou None (motivo em ULTIMO_ERRO)."""
    cv2 = _cv2()
    if cv2 is None: return None
    hdr = 'arib-std-b67' in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=color_transfer', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if hdr else ''
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, 'q.png')
        for f in (tm, ''):
            r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1', '-vf', f'{f}scale={largura}:-2', arq], capture_output=True)
            img = _ler_png(cv2, arq)
            if img is not None: return img
            ULTIMO_ERRO[0] = (r.stderr.decode(errors='ignore')[-200:] or f'ffmpeg {r.returncode}').strip()
    return None

def rostos(cv2, img):
    """Caixas [x, y, w, h] normalizadas (0 a 1) dos rostos achados: frontal e perfil, sem repetir o mesmo rosto."""
    cinza = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)); H, W = cinza.shape; caixas = []
    for nome in ('haarcascade_frontalface_alt2.xml', 'haarcascade_profileface.xml'):
        c = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, nome))
        for im, espelho in ((cinza, False), (cv2.flip(cinza, 1), True)) if 'profile' in nome else ((cinza, False),):
            for (x, y, w, h) in c.detectMultiScale(im, 1.08, 5, minSize=(int(W * 0.05), int(W * 0.05))):
                if espelho: x = W - x - w
                caixas.append([x, y, w, h])
    final = []
    for b in sorted(caixas, key=lambda b: -b[2] * b[3]):         # tira duplicados (caixas que se sobrepõem a uma maior)
        if all(_iou(b, f) < 0.3 for f in final): final.append(b)
    if final:                                                   # falsos positivos: muito menores que o maior rosto ou lá embaixo no quadro
        maior = max(w * h for _, _, w, h in final); final = [b for b in final if b[2] * b[3] >= 0.25 * maior and b[1] < 0.75 * H]
    return [[round(float(x) / W, 3), round(float(y) / H, 3), round(float(w) / W, 3), round(float(h) / H, 3)] for x, y, w, h in final]

def _iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix, iy = max(0, min(ax + aw, bx + bw) - max(ax, bx)), max(0, min(ay + ah, by + bh) - max(ay, by)); i = ix * iy
    return i / (aw * ah + bw * bh - i + 1e-9)

def diagnosticar(arquivos, nomes, saida_jpg, papeis=None):
    """arquivos: caminhos dos originais; nomes: nomes enviados. Devolve [{nome, rostos_por_quadro, max_rostos, caixa_grupo}] e grava a folha em saida_jpg."""
    try:
        cv2 = _cv2()
        if cv2 is None: return None
        linhas, resumo = [], []
        for i, v in enumerate(arquivos):
            if papeis and papeis[i] != 'fala': continue
            dur = _duracao(v); quadros, conts, uniao = [], [], None
            for k in range(N_QUADROS):
                img = _quadro(v, dur * (k + 0.5) / N_QUADROS)
                if img is None: continue
                cx = rostos(cv2, img); conts.append(len(cx)); H, W = img.shape[:2]
                for x, y, w, h in cx:
                    cv2.rectangle(img, (int(x * W), int(y * H)), (int((x + w) * W), int((y + h) * H)), (0, 255, 0), 3)
                    uniao = [x, y, x + w, y + h] if uniao is None else [min(uniao[0], x), min(uniao[1], y), max(uniao[2], x + w), max(uniao[3], y + h)]
                cv2.putText(img, f'{len(cx)}', (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)
                quadros.append(cv2.resize(img, (270, int(270 * H / W))))
            if quadros: linhas.append(np.hstack([q[:quadros[0].shape[0]] for q in quadros]))
            resumo.append({'nome': nomes[i], 'erro': '' if conts else ULTIMO_ERRO[0], 'rostos_por_quadro': conts, 'max_rostos': max(conts) if conts else 0,
                           'caixa_grupo': [round(float(u), 3) for u in uniao] if uniao else None})
        if linhas:
            L = max(l.shape[1] for l in linhas); cv2.imwrite(saida_jpg, np.vstack([np.pad(l, ((0, 0), (0, L - l.shape[1]), (0, 0))) for l in linhas]), [cv2.IMWRITE_JPEG_QUALITY, 80])
        return resumo
    except Exception as e:
        print('enquadramento: falhou (segue sem):', str(e)[:120], flush=True); return None

# ---------------- Fase 2: rostos ao longo do take e recorte que não corta ninguém ----------------
def rostos_no_tempo(video, largura=360, passo=1.0):
    """Rostos ao longo do take, um quadro por segundo (passo). Devolve [[t, [[x, y, w, h], ...]], ...] normalizado no quadro em pé, ou [] (motivo em ULTIMO_ERRO)."""
    try:
        cv2 = _cv2()
        if cv2 is None: ULTIMO_ERRO[0] = 'OpenCV não carregou'; return []
        import montagem
        W0, H0, transf, _ = montagem.sondar(video); dur = _duracao(video)
        tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if transf in ('arib-std-b67', 'smpte2084') else ''
        with tempfile.TemporaryDirectory() as d:
            for f in (tm, ''):
                r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-an', '-vf', f'fps=1/{passo:g},{f}scale={largura}:-2', os.path.join(d, 'q%04d.png')],
                                   capture_output=True, timeout=900)
                arqs = sorted(x for x in os.listdir(d) if x.endswith('.png'))
                if arqs: break
                ULTIMO_ERRO[0] = (r.stderr.decode(errors='ignore')[-200:] or f'ffmpeg {r.returncode}').strip()
            out = []
            for i, a in enumerate(arqs):
                img = cv2.imread(os.path.join(d, a))
                if img is not None: out.append([round(min(dur, (i + 0.5) * passo), 2), rostos(cv2, img)])
            return out
    except Exception as e:
        ULTIMO_ERRO[0] = str(e)[:200]; print('rostos no tempo:', str(e)[:120], flush=True); return []

RESPIRO = float(os.environ.get('BORA_RESPIRO', '0.12'))       # espaço livre acima da cabeça: 12% da altura do quadro (Fabiola: ~270 px em 1920 = 14%)

def recorte(W, H, z, fy, caixas):
    """Recorte (cw, ch, x, y) em pixels do original em pé. Sem rostos: o de sempre (centro, zoom z).
    Com rostos: o zoom cai até caber todo mundo com folga dos lados e respiro em cima; o recorte centra no grupo."""
    cw0, ch0 = (H * 9 / 16, H) if W / H > 9 / 16 else (W, W * 16 / 9)
    def tam(zz): return round(cw0 / zz / 2) * 2, round(ch0 / zz / 2) * 2
    def lim(v, a, b): return int(min(max(v, a), b))
    if not caixas:
        cw, ch = tam(z); return cw, ch, lim(0.5 * W - cw / 2, 0, W - cw), lim(0.40 * H - fy * ch, 0, H - ch)
    fh = max(c[3] for c in caixas) * H; fw = max(c[2] for c in caixas) * W
    ux0, ux1 = min(c[0] for c in caixas) * W, max(c[0] + c[2] for c in caixas) * W
    topo = min(c[1] for c in caixas) * H - 0.30 * fh                  # alto da cabeça (o rosto detectado começa na testa)
    folga = max(0.6 * fw, 0.04 * W)
    zz = z
    while True:
        cw, ch = tam(zz)
        y = lim(min(0.40 * H - fy * ch, topo - RESPIRO * ch), 0, H - ch)
        cabe = (ux1 - ux0 + 2 * folga) <= cw and (topo - y) >= RESPIRO * ch * 0.98
        if cabe or zz <= 1.0: break
        zz = max(1.0, zz - 0.02)
    meio = (ux0 + ux1) / 2
    return cw, ch, lim(meio - cw / 2, 0, W - cw), y

def caixas_do_trecho(rostos_take, t0, t1):
    """Rostos do take entre t0 e t1 (com meio segundo de folga), sem os muito menores que o maior (falso positivo)."""
    cx = [c for t, cs in rostos_take if t0 - 0.5 <= t <= t1 + 0.5 for c in cs]
    if not cx: return []
    maior = max(c[2] * c[3] for c in cx)
    return [c for c in cx if c[2] * c[3] >= 0.3 * maior]
