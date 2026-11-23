"""Teste dos cortes: começo e fim de cada trecho achados pelo som, pausas mais curtas e nenhuma palavra cortada.
Áudio sintético com palavras de posição conhecida; o 'Whisper' é simulado com erros (começo tardio, fim adiantado)."""
import os, sys, tempfile, wave
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
os.environ['BORA_TRABALHO'] = tempfile.mkdtemp()
import montagem
R = []; SR = 16000; T = tempfile.mkdtemp()
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
rng = np.random.default_rng(7)
# 3 frases de 4 palavras (0,35 s cada, 0,08 s entre palavras); pausa de 0,60 s entre frases; na frase 2 há uma pausa interna de 0,50 s
verd, t = [], 0.4
for fr in range(3):
    for k in range(4):
        verd.append((t, t + 0.35, fr)); t += 0.35 + (0.50 if (fr == 1 and k == 1) else 0.08)
    t += 0.60 - 0.08
x = rng.normal(0, 0.0003, int((t + 0.5) * SR)).astype(np.float32)                       # ruído de sala (-70 dB)
for ts, te, _ in verd:
    n = int((te - ts) * SR); env = np.minimum(np.linspace(0, 1, n) * (0.35 / 0.03), 1) * np.minimum(np.linspace(1, 0, n) * (0.35 / 0.05), 1)
    x[int(ts * SR):int(ts * SR) + n] += (rng.normal(0, 0.12, n) * env).astype(np.float32)
arq = os.path.join(T, 'fala.wav')
with wave.open(arq, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
def pausa_entre(ints, te_a, ts_b):
    """Silêncio que sobra na linha do tempo montada entre o fim da palavra A e o começo da B (a pausa inteira se nenhum corte caiu nela)."""
    if any(a <= te_a + 0.001 and b >= ts_b - 0.001 for a, b in ints): return ts_b - te_a
    fim = max(b for a, b in ints if a < te_a and b <= ts_b + 0.001); ini = min(a for a, b in ints if b > ts_b and a >= te_a - 0.001)
    return (fim - te_a) + (ts_b - ini)
def pal(erro_ini=0.0, erro_fim=0.0, estica=0.0):
    out = []
    for i, (ts, te, _) in enumerate(verd):
        prox = verd[i + 1][0] if i + 1 < len(verd) else te + 1
        out.append({'w': f'p{i}', 's': round(ts + erro_ini, 3), 'e': round(min(te + erro_fim + estica, prox - 0.01), 3)})   # fim esticado até a pausa, sem passar do próximo começo
    return out
plano = {'segmentos': [{'palavra_inicio': 4 * f, 'palavra_fim': 4 * f + 3, 'quadro': 'medio'} for f in range(3)]}
def rodar(erro_ini, erro_fim, antigo=False, estica=0.0):
    montagem.BORDA_PELO_SOM = not antigo; montagem.PROTEGE_PELO_SOM = not antigo
    montagem.PAUSA.update(min_s=0.30, mantem_s=0.10, borda_s=0.18) if antigo else montagem.PAUSA.update(min_s=0.25, mantem_s=0.04, borda_s=0.08)
    out, tokens, dur = montagem.pecas(plano, [arq], [pal(erro_ini, erro_fim, estica)], T)
    ints = [(fa / montagem.FPS, fb / montagem.FPS) for _, fa, fb, _ in out]
    cortadas = []
    for i, (ts, te, _) in enumerate(verd):
        if not any(a <= ts + 0.03 and b >= te - 0.03 for a, b in ints): cortadas.append(i)
    juncoes = []
    for f in (0, 1):                                                          # pausa entre a frase f e a f+1 na linha do tempo montada
        ult = max(b for a, b in ints if a < verd[4 * f + 3][1]); prim = min(a for a, b in ints if b > verd[4 * f + 4][0])
        juncoes.append(round((ult - verd[4 * f + 3][1]) + (verd[4 * f + 4][0] - prim), 3))
    return round(dur, 2), cortadas, juncoes, ints
for nome, ei, ef in (('Whisper exato', 0.0, 0.0), ('Whisper marca o começo 120 ms tarde', 0.12, 0.0), ('Whisper marca o fim 220 ms cedo', 0.0, -0.22)):
    d0, c0, j0, _ = rodar(ei, ef, antigo=True); d1, c1, j1, _ = rodar(ei, ef)
    print(f'  [{nome}] antigo: {d0} s, palavras cortadas {c0}, pausa entre frases {j0} | novo: {d1} s, cortadas {c1}, pausas {j1}')
    ok(f'{nome}: nenhuma palavra cortada (novo)', not c1, str(c1))
    ok(f'{nome}: pausa entre frases até 0,25 s (novo)', all(j <= 0.25 for j in j1), str(j1))
    if ei == 0 and ef == 0: ok(f'{nome}: mais curto que o corte antigo', d1 < d0, f'{d0} -> {d1} s')
    else: ok(f'{nome}: o corte antigo comia palavras (por isso era mais curto)', bool(c0), str(c0))
_, _, _, ints = rodar(0.0, 0.0)
p5, p6 = verd[5], verd[6]                                                    # a pausa interna de 0,50 s fica entre essas duas palavras
resto = pausa_entre(ints, p5[1], p6[0])
ok('pausa interna de 0,50 s encolhe pra no máximo 0,27 s', resto <= 0.27, f'{resto:.3f} s')
# Whisper estica o fim de cada palavra 0,30 s por cima da pausa: a pausa interna de 0,50 s tem que encolher mesmo assim
_, _, _, ints = rodar(0.0, 0.0, estica=0.30)
esticado = pausa_entre(ints, p5[1], p6[0])
_, _, _, ints0 = rodar(0.0, 0.0, antigo=True, estica=0.30)
antigo_esticado = pausa_entre(ints0, p5[1], p6[0])
ok('Whisper esticando o fim das palavras: a pausa de 0,50 s encolhe (antes ficava inteira)', esticado <= 0.30 and antigo_esticado > 0.40, f'antigo {antigo_esticado:.2f} s -> novo {esticado:.2f} s')
c_est = rodar(0.0, 0.0, estica=0.30)[1]
ok('Whisper esticando o fim das palavras: nenhuma palavra cortada', not c_est, str(c_est))
montagem.BORDA_PELO_SOM = True; montagem.PROTEGE_PELO_SOM = True; montagem.PAUSA.update(min_s=0.25, mantem_s=0.04, borda_s=0.08)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
