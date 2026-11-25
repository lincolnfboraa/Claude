"""Quem fala, pelo SOM: altura da voz (F0) de cada palavra. Voz grave e voz aguda separadas por agrupamento; o mapa e a transcrição
passam a dizer quem fala com base no áudio, não num chute pelo texto."""
import subprocess
import numpy as np

SR = 16000

def _audio(video):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)

def _f0(seg):
    """Altura média (Hz) de um pedaço de voz por autocorrelação em janelas de 40 ms; None se não houver voz clara."""
    n = int(0.04 * SR); fs = []
    for i in range(0, len(seg) - n, n // 2):
        w = seg[i:i + n] * np.hanning(n)
        if np.sqrt((w ** 2).mean()) < 0.01: continue
        ac = np.correlate(w, w, 'full')[n - 1:]
        lo, hi = int(SR / 350), int(SR / 70)                    # 70 a 350 Hz
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.35 * ac[0]: fs.append(SR / k)
    return float(np.median(fs)) if len(fs) >= 2 else None

def alturas(videos, palavras):
    """F0 de cada palavra (lista por arquivo; None onde não deu pra medir)."""
    out = []
    for v, pw in zip(videos, palavras):
        try: a = _audio(v)
        except Exception: out.append([None] * len(pw)); continue
        out.append([_f0(a[int(w['s'] * SR):int(w['e'] * SR)]) for w in pw])
    return out

def separar(f0s):
    """Divide as palavras medidas em voz grave e aguda (k-means em log F0). Devolve o limiar em Hz ou None se só houver uma voz."""
    xs = np.log([f for fl in f0s for f in fl if f])
    if len(xs) < 20: return None
    a, b = np.percentile(xs, 20), np.percentile(xs, 80)
    for _ in range(20):
        lim = (a + b) / 2; g, ag = xs[xs < lim], xs[xs >= lim]
        if not len(g) or not len(ag): return None
        a, b = g.mean(), ag.mean()
    if np.exp(b) / np.exp(a) < 1.35 or min(len(g), len(ag)) < 0.08 * len(xs): return None     # uma voz só (diferença pequena ou grupo minúsculo)
    return float(np.exp((a + b) / 2))

def quem_fala(f0s_trecho, limiar):
    """'voz grave', 'voz aguda' ou 'as duas' pela maioria das palavras medidas do trecho."""
    vs = [f for f in f0s_trecho if f]
    if not vs or not limiar: return None
    agudas = sum(1 for f in vs if f >= limiar) / len(vs)
    return 'voz aguda' if agudas >= 0.7 else 'voz grave' if agudas <= 0.3 else 'as duas vozes'
