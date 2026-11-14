#!/usr/bin/env python3
"""Detecta pausas longas dentro de cada segmento e grava em timeline.json (campo 'pausas').
Uso: python3 apara_pausas.py <pasta_wav_16k_mono>   (um <fonte>.wav por arquivo original)
Regra (timeline.json -> pausas_auto): trechos abaixo de limiar_db por pelo menos min_s viram
uma pausa de 2*mantem_s; o início e o fim de cada segmento ficam com no máximo mantem_s de silêncio."""
import json, sys, os, wave
import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
tl_path = os.path.join(here, 'timeline.json')
t = json.load(open(tl_path))
cfg = t['pausas_auto']
LIM, MIN, KEEP = cfg['limiar_db'], cfg['min_s'], cfg['mantem_s']
BORDA = cfg.get('borda_s', 0.18)   # margem maior no início/fim de cada trecho: protege finais fracos de palavra ('s', 'f', 'x')
SR, HOP = 16000, 0.02
cache = {}

def env(fonte):
    if fonte not in cache:
        a = np.frombuffer(wave.open(os.path.join(sys.argv[1], fonte + '.wav')).readframes(10**9), dtype=np.int16).astype(np.float32)/32768
        n = int(HOP*SR); k = len(a)//n
        cache[fonte] = 20*np.log10(np.sqrt((a[:k*n].reshape(k, n)**2).mean(1)) + 1e-9)
    return cache[fonte]

for s in t['segmentos']:
    e = env(s['fonte'])
    # partes mantidas = [in,out] menos cortes manuais
    partes, cur = [], s['in']
    for c in sorted(s.get('cortes', []), key=lambda c: c['de']):
        partes.append([cur, c['de']]); cur = c['ate']
    partes.append([cur, s['out']])
    pausas = []
    for a, b in partes:
        i0, i1 = int(a/HOP), int(b/HOP)
        quiet = e[i0:i1] < LIM
        # início/fim do trecho
        j = 0
        while j < len(quiet) and quiet[j]: j += 1
        if j*HOP > BORDA: pausas.append([round(a, 3), round(a + j*HOP - BORDA, 3)])
        k = len(quiet)
        while k > 0 and quiet[k-1]: k -= 1
        if (len(quiet)-k)*HOP > BORDA and not (s.get('manter_respiro_final') and b == s['out']): pausas.append([round(a + k*HOP + BORDA, 3), round(b, 3)])
        # pausas internas
        r = j
        while r < k:
            if quiet[r]:
                q = r
                while q < k and quiet[q]: q += 1
                if (q-r)*HOP >= MIN:
                    pausas.append([round(a + r*HOP + KEEP, 3), round(a + q*HOP - KEEP, 3)])
                r = q
            else:
                r += 1
    s['pausas'] = sorted(pausas)
    print(s['id'], s['fonte'], f"{len(pausas)} pausas, {sum(p[1]-p[0] for p in pausas):.2f}s removidos")
json.dump(t, open(tl_path, 'w'), ensure_ascii=False, indent=1)
